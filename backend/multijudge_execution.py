"""Mock-only, resumable executor for the frozen multi-judge manifest.

This module intentionally contains no provider SDK/client imports.  The sole
transport permitted in Phase 4 is ``DeterministicMockTransport``; attempting to
construct a real transport raises before any network-capable object exists.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from math import ceil
from pathlib import Path
from typing import Any, Protocol

from build_multijudge_execution_manifest import _copy_rows
from controlled_prompt import build_messages
from execution_policy import FAILURE_POLICY_VERSION, RETRY_POLICY_VERSION, RETRY_RULES, retry_rule
from model_registry import MODEL_REGISTRY
from routing_policy import routing_config


class CrashPoint(StrEnum):
    BEFORE_TRANSPORT = "BEFORE_TRANSPORT"
    AFTER_TRANSPORT_BEFORE_PERSIST = "AFTER_TRANSPORT_BEFORE_PERSIST"
    DURING_PERSISTENCE = "DURING_PERSISTENCE"
    AFTER_PERSISTENCE_BEFORE_ACK = "AFTER_PERSISTENCE_BEFORE_ACK"


class SimulatedCrash(RuntimeError):
    pass


class RealTransportForbidden(PermissionError):
    pass


@dataclass(frozen=True)
class MockResponse:
    verdict: str
    input_tokens: int
    output_tokens: int
    estimated_usd: float


class MockTransportFailure(RuntimeError):
    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


class Transport(Protocol):
    is_mock: bool

    def execute(self, payload: dict[str, Any]) -> MockResponse: ...


class RealProviderTransport:
    """Permanent Phase-4 fail-closed guard; it cannot create SDK clients."""

    def __init__(self, *_: Any, **__: Any) -> None:
        raise RealTransportForbidden("Phase 4 permits deterministic mock transport only; real provider transport is unavailable")


class DeterministicMockTransport:
    is_mock = True

    def __init__(self, scripted: dict[str, list[MockResponse | MockTransportFailure]] | None = None) -> None:
        self.scripted = {key: list(values) for key, values in (scripted or {}).items()}
        self.calls = 0

    def execute(self, payload: dict[str, Any]) -> MockResponse:
        self.calls += 1
        key = str(payload["planned_pass_id"])
        sequence = self.scripted.get(key)
        if sequence:
            item = sequence.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        # This intentionally depends only on a frozen pass identity, never a
        # human-reference record, answer quality, or prior judge outcome.
        bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:2], 16) % 3
        verdict = ("A", "B", "TIE")[bucket]
        rendered = "\n".join(message["content"] for message in payload["messages"])
        return MockResponse(verdict, max(1, ceil(len(rendered) / 4)), 24, 0.0001)


class IsolatedLedger:
    """Isolated SQLite persistence; it never opens the project database.

    ``path`` may be a disposable on-disk location for an interrupted-process
    rehearsal.  The default is in-memory so ordinary unit tests cannot create
    project state accidentally.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.connection = sqlite3.connect(":memory:" if path is None else str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS slots (
                planned_pass_id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL, final_outcome TEXT, mapped_vote TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS attempts (
                attempt_id TEXT PRIMARY KEY, planned_pass_id TEXT NOT NULL,
                attempt_index INTEGER NOT NULL, state TEXT NOT NULL, category TEXT,
                input_tokens INTEGER, output_tokens INTEGER, estimated_usd REAL,
                actual_usd REAL NOT NULL DEFAULT 0, cost_kind TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                UNIQUE(planned_pass_id, attempt_index)
            );
            CREATE TABLE IF NOT EXISTS ledger_metadata (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
        """)

    def bind_manifest(self, manifest_sha256: str) -> None:
        row = self.connection.execute("SELECT value FROM ledger_metadata WHERE key='manifest_sha256'").fetchone()
        if row is not None and row[0] != manifest_sha256:
            raise ValueError("isolated ledger belongs to a different frozen manifest")
        self.connection.execute(
            "INSERT OR IGNORE INTO ledger_metadata(key,value) VALUES('manifest_sha256',?)",
            (manifest_sha256,),
        )
        self.connection.commit()

    def seed(self, passes: list[dict[str, Any]]) -> None:
        self.connection.executemany(
            "INSERT OR IGNORE INTO slots(planned_pass_id,idempotency_key,status) VALUES(?,?, 'PENDING')",
            [(item["planned_pass_id"], item["idempotency_key"]) for item in passes],
        )
        self.connection.commit()

    def slot(self, pass_id: str) -> sqlite3.Row:
        row = self.connection.execute("SELECT * FROM slots WHERE planned_pass_id=?", (pass_id,)).fetchone()
        if row is None:
            raise KeyError(pass_id)
        return row

    def begin(self, pass_id: str) -> tuple[str, int]:
        row = self.slot(pass_id)
        if row["status"] in {"COMPLETED", "FAILED_FINAL", "AMBIGUOUS"}:
            return "", int(row["attempts"])
        index = int(row["attempts"])
        attempt_id = hashlib.sha256(f"{pass_id}|attempt|{index}".encode("utf-8")).hexdigest()
        self.connection.execute("UPDATE slots SET status='RUNNING', attempts=? WHERE planned_pass_id=?", (index + 1, pass_id))
        self.connection.execute(
            "INSERT INTO attempts(attempt_id,planned_pass_id,attempt_index,state,category,input_tokens,output_tokens,estimated_usd,actual_usd,cost_kind) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (attempt_id, pass_id, index, "IN_FLIGHT", None, None, None, None, 0.0, "MOCK_ESTIMATED"),
        )
        self.connection.commit()
        return attempt_id, index

    def before_transport_abort(self, pass_id: str, attempt_id: str) -> None:
        self.connection.execute("UPDATE attempts SET state='ABORTED_BEFORE_TRANSPORT' WHERE attempt_id=?", (attempt_id,))
        self.connection.execute("UPDATE slots SET status='PENDING' WHERE planned_pass_id=?", (pass_id,))
        self.connection.commit()

    def ambiguous(self, pass_id: str, attempt_id: str, category: str) -> None:
        self.connection.execute("UPDATE attempts SET state='AMBIGUOUS', category=? WHERE attempt_id=?", (category, attempt_id))
        self.connection.execute("UPDATE slots SET status='AMBIGUOUS' WHERE planned_pass_id=?", (pass_id,))
        self.connection.commit()

    def record(self, pass_id: str, attempt_id: str, *, outcome: str, mapped_vote: str | None, category: str | None, response: MockResponse | None, final: bool) -> None:
        values = (None if response is None else response.input_tokens, None if response is None else response.output_tokens, None if response is None else response.estimated_usd, category, "SUCCEEDED" if response is not None else "FAILED", attempt_id)
        self.connection.execute("UPDATE attempts SET input_tokens=?, output_tokens=?, estimated_usd=?, category=?, state=?, completed_at=CURRENT_TIMESTAMP WHERE attempt_id=?", values)
        status = "FAILED_FINAL" if final and response is None else "COMPLETED" if final else "PENDING"
        if final:
            self.connection.execute("UPDATE slots SET status=?, final_outcome=?, mapped_vote=?, completed_at=CURRENT_TIMESTAMP WHERE planned_pass_id=?", (status, outcome, mapped_vote, pass_id))
        else:
            self.connection.execute("UPDATE slots SET status='PENDING', final_outcome=NULL, mapped_vote=NULL, completed_at=NULL WHERE planned_pass_id=?", (pass_id,))
        self.connection.commit()

    def counts(self) -> dict[str, int]:
        return {row["status"]: row["count"] for row in self.connection.execute("SELECT status, COUNT(*) AS count FROM slots GROUP BY status")}

    def total_mock_estimate(self) -> float:
        return float(self.connection.execute("SELECT COALESCE(SUM(estimated_usd),0) FROM attempts").fetchone()[0])

    def total_real_spend(self) -> float:
        return float(self.connection.execute("SELECT COALESCE(SUM(actual_usd),0) FROM attempts").fetchone()[0])

    def attempt_count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0])


class MultiJudgeDryRunExecutor:
    """Shared scheduling path with an explicit mock-only transport boundary."""

    def __init__(self, manifest_path: Path, transport: Transport, *, enforce_budget: bool = False, budget_cap_usd: float | None = None, ledger_path: Path | None = None) -> None:
        if not getattr(transport, "is_mock", False):
            raise RealTransportForbidden("dry-run execution rejects any non-mock transport")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if self.manifest.get("execution_authorized") is not False:
            raise PermissionError("frozen manifest must remain unauthorized during Phase 4")
        self.transport = transport
        self.ledger = IsolatedLedger(ledger_path)
        self.ledger.bind_manifest(hashlib.sha256(manifest_path.read_bytes()).hexdigest())
        self.ledger.seed(self.manifest["planned_passes"])
        self.by_pass = {item["planned_pass_id"]: item for item in self.manifest["planned_passes"]}
        self.pair_by_id = {item["canonical_pair_id"]: item for item in self.manifest["pairs"]}
        self.judges = {item["judge_id"]: item for item in self.manifest["scientific_configuration"]["judges"]}
        self.routes = routing_config()
        pricing_path = Path(__file__).with_name("pricing_config.json")
        self.pricing_by_judge = {row["judge"]: row for row in json.loads(pricing_path.read_text(encoding="utf-8"))["models"]}
        self._validate_frozen_routes()
        self._validate_frozen_execution_policy()
        self.prompts, self.answers = self._load_payload_source()
        self.enforce_budget = enforce_budget
        self.budget_cap_usd = float(budget_cap_usd if budget_cap_usd is not None else self.manifest["budget_metadata"]["hard_cap_usd"])
        self.estimated_request_usd = float(self.manifest["budget_metadata"]["expected_usd"]) / len(self.by_pass)
        self.real_provider_calls = 0

    def _validate_frozen_routes(self) -> None:
        for judge_id, frozen in self.judges.items():
            spec = MODEL_REGISTRY.get(judge_id)
            if spec is None or frozen["provider"] != spec.provider.value or frozen["requested_model"] != spec.requested_model:
                raise ValueError("unexpected model or provider in frozen manifest")
            if judge_id not in self.pricing_by_judge:
                raise ValueError("missing frozen pricing entry")
            if frozen["fallbacks_allowed"] is not False:
                raise ValueError("fallback activation is forbidden")
            if spec.provider.value == "OPENROUTER":
                route = self.routes["models"].get(judge_id)
                if route is None or frozen["route"] != route["upstream_provider"]:
                    raise ValueError("unexpected OpenRouter route in frozen manifest")
            elif frozen["route"] != "OPENAI_DIRECT":
                raise ValueError("unexpected OpenAI route in frozen manifest")

    def _validate_frozen_execution_policy(self) -> None:
        policy = self.manifest["scientific_configuration"]["retry_policy"]
        if policy["retry_policy_version"] != RETRY_POLICY_VERSION or policy["failure_policy_version"] != FAILURE_POLICY_VERSION:
            raise ValueError("unexpected retry/failure policy version")
        for category, frozen in policy["rules"].items():
            local = RETRY_RULES.get(category)
            if local is None or frozen != {"retryable": local.retryable, "max_retries": local.max_retries, "backoff_seconds": list(local.backoff_seconds)}:
                raise ValueError("retry policy drift")
        budget = self.manifest["budget_metadata"]
        if budget["hard_cap_usd"] != "2.50" or float(budget["expected_usd"]) <= 0:
            raise ValueError("unexpected frozen budget metadata")

    @staticmethod
    def _load_payload_source() -> tuple[dict[int, str], dict[int, str]]:
        # Deliberately reads only prompts and answers from the immutable dump;
        # no human_preferences row or outcome is loaded into execution memory.
        prompts = {int(row[0]): str(row[1]) for row in _copy_rows("prompts")}
        answers = {int(row[0]): str(row[3]) for row in _copy_rows("answers")}
        return prompts, answers

    def payload(self, pass_id: str) -> dict[str, Any]:
        item = self.by_pass[pass_id]; judge = self.judges[item["judge_id"]]
        prompt = self.prompts[item["canonical_pair_id"] and self._prompt_id(item["canonical_pair_id"])]
        answer_a, answer_b = self.answers[item["displayed_A_answer_id"]], self.answers[item["displayed_B_answer_id"]]
        payload = {
            "planned_pass_id": pass_id, "idempotency_key": item["idempotency_key"], "provider": judge["provider"],
            "model": judge["requested_model"], "route": judge["route"], "fallbacks_allowed": judge["fallbacks_allowed"],
            "temperature": self.manifest["scientific_configuration"]["prompt"]["temperature"], "top_p": self.manifest["scientific_configuration"]["prompt"]["top_p"],
            "max_output_tokens": judge["max_output_tokens"], "response_schema": self.manifest["scientific_configuration"]["prompt"]["response_schema"],
            "messages": build_messages(question=prompt, answer_a=answer_a, answer_b=answer_b),
            "displayed_A_answer_id": item["displayed_A_answer_id"], "displayed_B_answer_id": item["displayed_B_answer_id"],
        }
        self._validate_payload(item, payload)
        return payload

    def _prompt_id(self, canonical_pair_id: str) -> int:
        return int(self.pair_by_id[canonical_pair_id]["prompt_id"])

    def _validate_payload(self, item: dict[str, Any], payload: dict[str, Any]) -> None:
        judge = self.judges[item["judge_id"]]
        spec = MODEL_REGISTRY[item["judge_id"]]
        if payload["provider"] != spec.provider.value or payload["model"] != spec.requested_model or payload["fallbacks_allowed"] is not False:
            raise ValueError("provider/model/fallback payload drift")
        expected = (item["original_answer_1_id"], item["original_answer_2_id"]) if item["presentation"] == "AB" else (item["original_answer_2_id"], item["original_answer_1_id"])
        if (payload["displayed_A_answer_id"], payload["displayed_B_answer_id"]) != expected:
            raise ValueError("presentation mapping drift")
        if payload["temperature"] != 0 or payload["top_p"] != 1 or payload["max_output_tokens"] != 350:
            raise ValueError("frozen generation settings drift")
        if payload["response_schema"] != self.manifest["scientific_configuration"]["prompt"]["response_schema"]:
            raise ValueError("response-schema drift")
        if item["judge_id"] not in self.pricing_by_judge:
            raise ValueError("missing pricing entry")
        if judge["provider"] == "OPENROUTER" and judge["route"] != self.routes["models"][item["judge_id"]]["upstream_provider"]:
            raise ValueError("unexpected OpenRouter route")

    @staticmethod
    def map_vote(item: dict[str, Any], verdict: str) -> str | None:
        if verdict == "TIE":
            return "TIE"
        if verdict == "A":
            answer = item["displayed_A_answer_id"]
        elif verdict == "B":
            answer = item["displayed_B_answer_id"]
        else:
            return None
        return "ORIGINAL_ANSWER_1" if answer == item["original_answer_1_id"] else "ORIGINAL_ANSWER_2" if answer == item["original_answer_2_id"] else None

    def _budget_allowed(self, estimate: float) -> bool:
        return not self.enforce_budget or self.ledger.total_mock_estimate() + estimate <= self.budget_cap_usd

    def cost_ledger(self) -> dict[str, Any]:
        """Return clearly labelled mock estimates and zero real-spend totals."""
        per_model = {judge_id: {"mock_estimated_usd": 0.0, "real_actual_usd": 0.0} for judge_id in self.judges}
        for row in self.ledger.connection.execute("SELECT planned_pass_id, COALESCE(estimated_usd,0) AS estimated_usd, COALESCE(actual_usd,0) AS actual_usd FROM attempts"):
            judge_id = self.by_pass[row["planned_pass_id"]]["judge_id"]
            per_model[judge_id]["mock_estimated_usd"] += float(row["estimated_usd"])
            per_model[judge_id]["real_actual_usd"] += float(row["actual_usd"])
        openai = sum(values["mock_estimated_usd"] for judge, values in per_model.items() if self.judges[judge]["provider"] == "OPENAI")
        openrouter = sum(values["mock_estimated_usd"] for judge, values in per_model.items() if self.judges[judge]["provider"] == "OPENROUTER")
        return {
            "cost_kind": "MOCK_ESTIMATED",
            "per_model": per_model,
            "openai_mock_estimated_usd": openai,
            "openrouter_mock_estimated_usd": openrouter,
            "total_mock_estimated_usd": self.ledger.total_mock_estimate(),
            "total_real_actual_usd": self.ledger.total_real_spend(),
        }

    def execute_one(self, pass_id: str, *, crash_at: CrashPoint | None = None) -> str:
        current = self.ledger.slot(pass_id)
        if current["status"] in {"COMPLETED", "FAILED_FINAL", "AMBIGUOUS"}:
            return str(current["status"])
        item = self.by_pass[pass_id]
        while True:
            attempt_id, index = self.ledger.begin(pass_id)
            if not attempt_id:
                return str(self.ledger.slot(pass_id)["status"])
            if crash_at == CrashPoint.BEFORE_TRANSPORT:
                self.ledger.before_transport_abort(pass_id, attempt_id)
                raise SimulatedCrash(crash_at)
            payload = self.payload(pass_id)
            if not self._budget_allowed(self.estimated_request_usd):
                self.ledger.record(pass_id, attempt_id, outcome="MISSING_PASS", mapped_vote=None, category="BUDGET_EXCEEDED", response=None, final=True)
                return "FAILED_FINAL"
            try:
                response = self.transport.execute(payload)
            except MockTransportFailure as error:
                rule = retry_rule(error.category)
                final = not rule.retryable or index >= rule.max_retries
                self.ledger.record(pass_id, attempt_id, outcome="API_ERROR" if error.category != "TIMEOUT" else "TIMEOUT", mapped_vote=None, category=error.category, response=None, final=final)
                if final:
                    return "FAILED_FINAL"
                continue
            if crash_at in {CrashPoint.AFTER_TRANSPORT_BEFORE_PERSIST, CrashPoint.DURING_PERSISTENCE}:
                self.ledger.ambiguous(pass_id, attempt_id, crash_at)
                raise SimulatedCrash(crash_at)
            normalized = {"A": "ANSWER_A", "B": "ANSWER_B", "TIE": "TIE", "UNKNOWN": "UNKNOWN", "INVALID_JSON": "INVALID_RESPONSE"}.get(response.verdict, "INVALID_RESPONSE")
            mapped = self.map_vote(item, response.verdict)
            self.ledger.record(pass_id, attempt_id, outcome=normalized, mapped_vote=mapped, category=None if normalized in {"ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"} else "INVALID_RESPONSE", response=response, final=True)
            if crash_at == CrashPoint.AFTER_PERSISTENCE_BEFORE_ACK:
                raise SimulatedCrash(crash_at)
            return "COMPLETED"

    def run(self, *, limit: int | None = None) -> dict[str, int]:
        completed = 0
        for pass_id in self.by_pass:
            if self.ledger.slot(pass_id)["status"] != "PENDING":
                continue
            self.execute_one(pass_id)
            completed += 1
            if limit is not None and completed >= limit:
                break
        return self.ledger.counts()

    def summary(self) -> dict[str, Any]:
        counts = self.ledger.counts()
        return {
            "planned_pairs": len(self.manifest["pairs"]), "planned_passes": len(self.by_pass),
            "completed_scientific_outcomes": counts.get("COMPLETED", 0) + counts.get("FAILED_FINAL", 0),
            "duplicate_scientific_outcomes": 0, "missing_planned_outcomes": counts.get("PENDING", 0) + counts.get("RUNNING", 0) + counts.get("AMBIGUOUS", 0),
            "attempts": self.ledger.attempt_count(), "mock_estimated_usd": self.ledger.total_mock_estimate(),
            "real_spend_usd": self.ledger.total_real_spend(), "real_provider_calls": self.real_provider_calls,
        }
