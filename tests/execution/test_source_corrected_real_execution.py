"""Provider-free integration tests for the source-corrected paid executor."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.controlled_models import DatasetVersion
from backend.evaluation.engine import ProviderCallError
from backend.core.database import SessionLocal
from backend.core.model_registry import MODEL_REGISTRY
from backend.core.models import Prompt
from backend.historical.source_corrected_plan import DATASET_VERSION, RECONCILIATION_SHA256, mock_dry_run
from backend.historical.source_corrected_models import (SourceCorrectedExecutionAttempt, SourceCorrectedExecutionBatch,
                                               SourceCorrectedExecutionSlot)
from backend.historical.source_corrected_execution import (MockTransport, SourceCorrectedRunner, SourceCorrectedStore,
                                             render_dashboard, utc_now)


def _isolated_runner(*, cap: str | None = None, limit: int = 3, transport=None):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    for table in (DatasetVersion.__table__, Prompt.__table__, SourceCorrectedExecutionBatch.__table__, SourceCorrectedExecutionSlot.__table__, SourceCorrectedExecutionAttempt.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    template = SourceCorrectedRunner(SessionLocal, transport=MockTransport())
    manifest = template.manifest
    representative = []
    for rq in ("RQ2", "RQ4", "RQ5", "RQ7_SECONDARY"):
        representative.append(next(row for row in manifest["planned_passes"] if row["rq_code"] == rq))
    selected_rows = manifest["planned_passes"][:limit] if limit > len(representative) else representative[:limit]
    with SessionLocal() as source:
        prompts = list(source.execute(select(Prompt.id, Prompt.text, Prompt.category)))
    with factory() as session:
        version = DatasetVersion(id=uuid4(), source_name="isolated", version=DATASET_VERSION, source_checksum=RECONCILIATION_SHA256, import_status="SUCCEEDED")
        caps = dict(manifest["budget_metadata"]["provider_hard_caps_usd"])
        if cap is not None: caps = {"OPENAI": cap, "OPENROUTER": cap}
        batch = SourceCorrectedExecutionBatch(id=uuid4(), dataset_version_id=version.id, reconciliation_sha256=RECONCILIATION_SHA256, manifest_identity=manifest["manifest_identity"], manifest_sha256=manifest["manifest_sha256"], global_hard_cap_usd=Decimal(cap or manifest["budget_metadata"]["global_hard_cap_usd"]), provider_hard_caps_json=caps, status="MATERIALIZED", provenance_json={})
        session.add_all((version, batch)); session.add_all(Prompt(id=row.id, text=row.text, category=row.category) for row in prompts)
        session.add_all(SourceCorrectedExecutionSlot(id=uuid4(), batch_id=batch.id, planned_pass_id=row["planned_pass_id"], idempotency_key=row["idempotency_key"], rq_code=row["rq_code"], condition_code=row["condition_code"], judge_id=row["judge_id"], provider=row["provider"], requested_model=row.get("provider_model", MODEL_REGISTRY[row["judge_id"]].requested_model), route=row["route"], presentation=row["presentation"], corrected_record_key=row["corrected_record_key"], payload_sha256=row["rendered_payload_sha256"], state="PENDING", estimated_input_tokens=row["estimated_input_tokens"], estimated_output_tokens=row["estimated_output_tokens"]) for row in selected_rows)
        session.commit()
    active_transport = transport or MockTransport()
    return engine, factory, SourceCorrectedRunner(factory, transport=active_transport), active_transport


class FirstNetworkFailureThenSuccess(MockTransport):
    def __call__(self, endpoint, headers, payload):
        if not self.sent:
            self.sent.append("first-network-failure")
            raise ProviderCallError("NETWORK_CONNECTION", "fixture network failure")
        return super().__call__(endpoint, headers, payload)


class InvalidPayloadThenSuccess(MockTransport):
    def __call__(self, endpoint, headers, payload):
        if not self.sent:
            self.sent.append("first-invalid-payload")
            response = {"id": "invalid-first", "model": payload["model"], "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "choices": [{"message": {"content": "not valid verdict JSON"}}]}
            if payload.get("provider", {}).get("only"):
                response["provider"] = {"provider_slug": payload["provider"]["only"][0]}
            return response
        return super().__call__(endpoint, headers, payload)


def test_mock_executor_resumes_same_command_without_duplicates():
    engine, _factory, runner, transport = _isolated_runner()
    first = runner.execute(confirmation="I_CONFIRM_SOURCE_CORRECTED_PAID_EXECUTION", max_slots=100)
    assert first["completed"] == 3 and len(transport.sent) == 3
    final = runner.execute_mock_full()
    assert final["planned"] == final["completed"] == 3
    assert final["failed"] == final["ambiguous"] == 0
    assert len(transport.sent) == 3
    assert final["batch_status"] == "COMPLETED"
    dashboard = render_dashboard(final, {"OPENAI": "1", "OPENROUTER": "2", "GLOBAL": "3"}, elapsed=60, rate=1)
    assert "Overall" in dashboard and "Per judge:" in dashboard and "Per RQ:" in dashboard and "Global" in dashboard
    engine.dispose()


def test_full_6449_slot_mock_rehearsal_uses_frozen_manifest_without_network():
    engine, _factory, runner, transport = _isolated_runner(limit=6449)
    final = runner.execute_mock_full()
    assert final["planned"] == final["completed"] == final["attempts"] == 6449
    assert final["failed"] == final["ambiguous"] == 0 and len(transport.sent) == 6449
    assert mock_dry_run(runner.manifest)["mock_transport_calls"] == 6449
    dashboard = render_dashboard(final, {"OPENAI": "1", "OPENROUTER": "2", "GLOBAL": "3"}, elapsed=60, rate=1)
    assert "6449 / 6449" in dashboard and "100.0%" in dashboard
    engine.dispose()


def test_production_loop_continues_through_the_full_manifest_with_mock_transport():
    engine, _factory, runner, transport = _isolated_runner(limit=6449)
    final = runner.execute(confirmation="I_CONFIRM_SOURCE_CORRECTED_PAID_EXECUTION")
    assert final["planned"] == final["completed"] == final["attempts"] == 6449
    assert final["failed"] == final["ambiguous"] == 0 and len(transport.sent) == 6449
    engine.dispose()


def test_per_request_provider_error_retries_without_stopping_the_worker():
    transport = FirstNetworkFailureThenSuccess()
    engine, _factory, runner, _ = _isolated_runner(transport=transport)
    report = runner.execute(confirmation="I_CONFIRM_SOURCE_CORRECTED_PAID_EXECUTION", max_slots=10)
    assert report["completed"] == 3 and report["failed"] == report["ambiguous"] == 0
    assert report["attempts"] == 4 and len(transport.sent) == 4
    engine.dispose()


def test_parser_error_is_terminal_for_one_slot_but_does_not_stop_other_slots():
    transport = InvalidPayloadThenSuccess()
    engine, _factory, runner, _ = _isolated_runner(transport=transport)
    report = runner.execute(confirmation="I_CONFIRM_SOURCE_CORRECTED_PAID_EXECUTION", max_slots=10)
    assert report["completed"] == 2 and report["failed"] == 1 and report["ambiguous"] == 0
    assert report["attempts"] == 3 and len(transport.sent) == 3
    engine.dispose()


def test_persistence_failure_stops_with_a_durable_sent_slot_and_explicit_reason():
    engine, _factory, runner, _ = _isolated_runner()
    def fail_persist(*_args, **_kwargs):
        raise RuntimeError("fixture persistence failure")
    runner.store.persist = fail_persist
    report = runner.execute(confirmation="I_CONFIRM_SOURCE_CORRECTED_PAID_EXECUTION", max_slots=1)
    assert report["in_progress"] == 1
    assert report["stop_reason"] == "UNEXPECTED_EXECUTOR_ERROR: RuntimeError"
    dashboard = render_dashboard(report, {"OPENAI": "1", "OPENROUTER": "2", "GLOBAL": "3"})
    assert "EXECUTION STOPPED" in dashboard and "UNEXPECTED_EXECUTOR_ERROR" in dashboard
    engine.dispose()


def test_crash_after_sent_is_ambiguous_and_budget_stops_before_mock_transport():
    engine, factory, runner, transport = _isolated_runner(cap="0")
    report = runner.execute(confirmation="I_CONFIRM_SOURCE_CORRECTED_PAID_EXECUTION", max_slots=1)
    assert report["failed"] == 1 and not transport.sent
    engine.dispose()


def test_two_durable_claims_cannot_own_the_same_slot():
    engine, factory, runner, _transport = _isolated_runner()
    store = SourceCorrectedStore()
    with factory() as first:
        batch = runner.batch(first); one = store.claim(first, batch, owner="one"); first.commit()
    with factory() as second:
        batch = runner.batch(second); two = store.claim(second, batch, owner="two"); second.commit()
    assert one is not None and two is not None and one[0].planned_pass_id != two[0].planned_pass_id
    engine.dispose()


def test_stale_sent_is_ambiguous_not_resent_and_other_work_can_continue():
    engine, factory, runner, transport = _isolated_runner()
    with factory() as session:
        batch = runner.batch(session)
        slot = session.scalar(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id))
        attempt = SourceCorrectedExecutionAttempt(slot_id=slot.id, attempt_id="sent-crash", attempt_index=0, state="SENT", reserved_usd=Decimal("0.0001"))
        slot.state, slot.attempt_count, slot.execution_owner, slot.lease_expires_at = "SENT", 1, "dead", utc_now().replace(year=2000)
        session.add(attempt)
        session.commit()
    reconciled = runner.reconcile_stale_in_flight()
    assert reconciled["ambiguous"] == 1 and reconciled["in_progress"] == 0
    resumed = runner.execute(confirmation="I_CONFIRM_SOURCE_CORRECTED_PAID_EXECUTION", max_slots=1)
    with factory() as session:
        protected = session.get(SourceCorrectedExecutionSlot, slot.id)
        protected_attempts = session.query(SourceCorrectedExecutionAttempt).filter_by(slot_id=slot.id).count()
    assert protected.state == "AMBIGUOUS" and protected_attempts == 1
    assert resumed["ambiguous"] == 1 and resumed["completed"] == 1 and len(transport.sent) == 1
    engine.dispose()
