"""Provider-free Phase 11 robustness analyses; Phase 8 remains primary."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.multijudge.consensus import JUDGES, VALID_VOTES, _reference_labels, consensus_for_four, consensus_for_three
from backend.core.database import SessionLocal
from backend.multijudge.models import MultiJudgeExecutionBatch, MultiJudgeExecutionSlot


ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST = ROOT / "evidence" / "multijudge_consensus" / "execution_manifest_v1.json"
PRIMARY = ROOT / "evidence" / "multijudge_consensus" / "primary_analysis_v1.json"
FAIR = ROOT / "evidence" / "multijudge_consensus" / "fair_baseline_comparison_v1.json"
DUAL = ROOT / "evidence" / "multijudge_consensus" / "dualswap_comparison_v1.json"
OUTPUT = ROOT / "evidence" / "multijudge_consensus" / "robustness_sensitivity_v1.json"
PROTOCOL_SHA = "819f2e2dea8fb32e4c32000551d6048a16ecc8d28f1bb32d2cce4d02a15c40ce"
MANIFEST_SHA = "6c2fa4a926e458c598c73604daa1b69d766bc5b2d04853e73c3a35bf9017e351"
PRIMARY_SHA = "c881c75b37fc80e4f3ba1e922e1aeba6a28f7125176f6183a38bd48597237693"
FAIR_SHA = "c362dee20f9d59f9e92ca77f206604b99878c7eaac93247bb346b125ed654bc3"
DUAL_SHA = "52bdec7ac98f845bc5e2d93a55daa8cc505c1d2c576029ca85468cd57789c2c8"
SEED, RESAMPLES = 20260823, 10_000


class RobustnessError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def boot(values: Iterable[float]) -> dict[str, float]:
    values = np.asarray(tuple(values), dtype=float)
    rng = np.random.default_rng(SEED)
    samples = np.empty(RESAMPLES)
    for i in range(RESAMPLES): samples[i] = values[rng.integers(0, len(values), size=len(values))].mean()
    lo, hi = np.percentile(samples, [2.5, 97.5])
    return {"low": float(lo), "high": float(hi)}


def evaluate(records: list[dict[str, Any]], judges: tuple[str, ...], *, rule: str, planned_n: int = 1611, label: str) -> dict[str, Any]:
    scored = []
    for record in records:
        values = [record["votes"][judge] for judge in judges]
        if rule == "three": decision = consensus_for_three(values).label
        elif rule == "four": decision = consensus_for_four(values).label
        elif rule == "unanimity": decision = values[0] if len(set(values)) == 1 else None
        else: raise RobustnessError("unknown sensitivity rule")
        if decision is not None: scored.append({**record, "decision": decision})
    if not scored: raise RobustnessError("empty sensitivity retention")
    correctness = [float(row["decision"] == row["human_reference"]) for row in scored]
    individual = [sum(row["votes"][judge] == row["human_reference"] for judge in judges) / len(judges) for row in scored]
    delta = [left - right for left, right in zip(correctness, individual)]
    return {"label": label, "eligible_n": len(records), "retained_n": len(scored), "coverage": len(scored) / planned_n, "agreement": float(np.mean(correctness)), "equal_weight_individual_baseline": float(np.mean(individual)), "delta": float(np.mean(delta)), "delta_ci_95_secondary": boot(delta), "judges": list(judges), "sensitivity_only": label != "PRIMARY"}


def analyze(session: Session) -> dict[str, Any]:
    if (sha(MANIFEST), sha(PRIMARY), sha(FAIR), sha(DUAL)) != (MANIFEST_SHA, PRIMARY_SHA, FAIR_SHA, DUAL_SHA): raise RobustnessError("frozen lineage checksum mismatch")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")); primary = json.loads(PRIMARY.read_text(encoding="utf-8"))
    batch = session.scalar(select(MultiJudgeExecutionBatch).where(MultiJudgeExecutionBatch.manifest_sha256 == MANIFEST_SHA))
    slots = list(session.scalars(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id))) if batch else []
    by_pair: dict[str, list[MultiJudgeExecutionSlot]] = defaultdict(list)
    for slot in slots: by_pair[slot.canonical_pair_id].append(slot)
    pairs = {pair["canonical_pair_id"]: pair for pair in manifest["pairs"]}
    if len(slots) != 6444 or set(by_pair) != set(pairs): raise RobustnessError("ledger population mismatch")
    labels = _reference_labels(manifest); four=[]; three=[]
    for pair_id, rows in by_pair.items():
        votes={row.judge_id:row.mapped_vote for row in rows if row.status=="COMPLETED" and row.mapped_vote in VALID_VOTES}
        record={"pair_id":pair_id,"category":pairs[pair_id]["category"],"votes":votes,"human_reference":labels[pair_id]}
        if len(votes)==4: four.append(record)
        elif len(votes)==3: three.append(record)
    if (len(four),len(three)) != (1473,130): raise RobustnessError("primary/sensitivity structural counts mismatch")
    primary_result=evaluate(four,JUDGES,rule="four",label="PRIMARY")
    expected=primary["primary"]
    if not (primary_result["retained_n"]==expected["covered_n"] and abs(primary_result["agreement"]-expected["agreement"]["agreement"])<1e-12 and abs(primary_result["equal_weight_individual_baseline"]-expected["individual_comparator"]["equal_weight_agreement"])<1e-12 and abs(primary_result["delta"]-expected["individual_comparator"]["delta"]["estimate"])<1e-12): raise RobustnessError("primary reproduction mismatch")
    primary_result["delta_ci_95_primary"] = primary_result.pop("delta_ci_95_secondary")
    # Each three-valid row has a different missing judge, so use exactly its observed voters.
    def three_eval(rows: list[dict[str,Any]]) -> dict[str,Any]:
        scored=[]
        for row in rows:
            decision=consensus_for_three(row["votes"].values()).label
            if decision is not None: scored.append({**row,"decision":decision})
        correct=[float(x["decision"]==x["human_reference"]) for x in scored]; base=[sum(v==x["human_reference"] for v in x["votes"].values())/3 for x in scored]; delta=[x-y for x,y in zip(correct,base)]
        return {"label":"THREE_VALID_SENSITIVITY","eligible_n":len(rows),"retained_n":len(scored),"coverage_within_eligible":len(scored)/len(rows),"coverage":len(scored)/1611,"agreement":float(np.mean(correct)),"equal_weight_three_judge_baseline":float(np.mean(base)),"delta":float(np.mean(delta)),"delta_ci_95_secondary":boot(delta),"sensitivity_only":True}
    three_result=three_eval(three)
    loo={f"OMIT_{judge}":evaluate(four,tuple(other for other in JUDGES if other != judge),rule="three",label=f"OMIT_{judge}") for judge in JUDGES}
    unanimity=evaluate(four,JUDGES,rule="unanimity",label="STRICT_UNANIMITY_SENSITIVITY")
    primary_scored=[{**row,"decision":consensus_for_four(row["votes"][judge] for judge in JUDGES).label} for row in four]; decisive=[row for row in primary_scored if row["decision"] in {"ORIGINAL_ANSWER_1","ORIGINAL_ANSWER_2"}]
    decisive_result=evaluate(decisive,JUDGES,rule="four",label="DECISIVE_ONLY_SENSITIVITY")
    category={}
    for name in sorted({row["category"] for row in four}): category[name]=evaluate([row for row in four if row["category"]==name],JUDGES,rule="four",planned_n=sum(pair["category"]==name for pair in manifest["pairs"]),label="CATEGORY_DESCRIPTIVE")
    strength={name:evaluate([row for row in four if consensus_for_four(row["votes"][judge] for judge in JUDGES).pattern==name],JUDGES,rule="four",label=f"VOTE_STRENGTH_{name}") for name in ("4-0","3-1")}
    all_sens=[three_result,*loo.values(),unanimity,decisive_result]
    return {"artifact_id":"multi-judge-robustness-sensitivity-v1","phase":"PHASE_11_ROBUSTNESS_SENSITIVITY","lineage":{"protocol_sha256":PROTOCOL_SHA,"manifest_sha256":MANIFEST_SHA,"primary_sha256":PRIMARY_SHA,"fair_baseline_sha256":FAIR_SHA,"dualswap_comparison_sha256":DUAL_SHA},"primary_reproduction":{"status":"PASS","result":primary_result},"three_valid_sensitivity":three_result,"leave_one_judge_out":loo,"strict_unanimity_sensitivity":unanimity,"decisive_only_sensitivity":decisive_result,"category_robustness":category,"vote_strength":strength,"sensitivity_delta_direction_counts":{"positive":sum(x["delta"]>0 for x in all_sens),"zero":sum(x["delta"]==0 for x in all_sens),"negative":sum(x["delta"]<0 for x in all_sens)},"bootstrap":{"unit":"canonical_answer_pair","method":"nonparametric_percentile","resamples":RESAMPLES,"confidence_level":.95,"seed":SEED,"all_sensitivity_cis_secondary":True},"constraints":{"primary_remains_frozen":True,"no_dualswap_direct_comparison":True,"no_rq7_promotion":True,"human_reference_not_ground_truth":True},"provider_activity":{"provider_calls":0,"spend_usd":"0"}}


def main(argv: list[str]|None=None)->int:
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=OUTPUT);args=parser.parse_args(argv)
    with SessionLocal() as session: result=analyze(session)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(f"WROTE {args.output}");print(f"SHA256 {sha(args.output)}");return 0
if __name__=="__main__": raise SystemExit(main())
