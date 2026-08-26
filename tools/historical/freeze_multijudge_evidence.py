"""Provider-free additive Multi-Judge evidence-package freezer."""
from __future__ import annotations
import hashlib, json, shutil, uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select
from backend.core.database import SessionLocal  # noqa: E402
from backend.core.controlled_models import AnalysisRun  # noqa: E402
from backend.core.final_evidence import CANONICAL_FINAL_ANALYSIS_RUNS  # noqa: E402
from backend.multijudge.models import MultiJudgeExecutionAttempt, MultiJudgeExecutionBatch, MultiJudgeExecutionSlot  # noqa: E402

SRC=ROOT/'evidence'/'multijudge_consensus'; OUT=ROOT/'evidence'/'final'/'multijudge_consensus_v1'
SHAS={'protocol_v1.json':'819f2e2dea8fb32e4c32000551d6048a16ecc8d28f1bb32d2cce4d02a15c40ce','execution_manifest_v1.json':'6c2fa4a926e458c598c73604daa1b69d766bc5b2d04853e73c3a35bf9017e351','postexecution_integrity_v1.json':'9e0273c0b51917ba2ea8358c1d29041f8ed3eacd93d33839b8ebafe6b7cf4ba3','primary_analysis_v1.json':'c881c75b37fc80e4f3ba1e922e1aeba6a28f7125176f6183a38bd48597237693','fair_baseline_comparison_v1.json':'c362dee20f9d59f9e92ca77f206604b99878c7eaac93247bb346b125ed654bc3','dualswap_comparison_v1.json':'52bdec7ac98f845bc5e2d93a55daa8cc505c1d2c576029ca85468cd57789c2c8','robustness_sensitivity_v1.json':'e11d258535e887a6ba929492a675d464e773fd927001746a42928aca6b1b8f81','promotion_decision_v1.json':'4682516428fe1206a072ad32efc0c638d7112d0b4396efe2e1ab86f5c0dba5f0'}
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,sort_keys=True,default=str)+'\n',encoding='utf-8')
def main():
 if any(h(SRC/n)!=s for n,s in SHAS.items()): raise RuntimeError('frozen source SHA mismatch')
 with SessionLocal() as s:
  dual=s.get(AnalysisRun,uuid.UUID(CANONICAL_FINAL_ANALYSIS_RUNS['RQ7'])); dual_hash=hsh=hashlib.sha256(json.dumps(dual.result_json,sort_keys=True,default=str).encode()).hexdigest(); primary=json.loads((SRC/'primary_analysis_v1.json').read_text())
  metrics={'planned_n':1611,'four_valid_n':1473,'retained_n':1125,'agreement':primary['primary']['agreement']['agreement'],'coverage':primary['primary']['coverage'],'equal_weight_individual_baseline':primary['primary']['individual_comparator']['equal_weight_agreement'],'matched_delta':primary['primary']['individual_comparator']['delta']['estimate'],'ci_low':primary['primary']['individual_comparator']['delta']['ci_95']['low'],'ci_high':primary['primary']['individual_comparator']['delta']['ci_95']['high']}
  payload={'evidence_class':'CONTROLLED','rq_code':'RQ7','analysis_identity':'multi-judge-consensus-analysis-v1','mitigation_role':'SECONDARY','primary_dual_swap_analysis_run_id':str(dual.id),'protocol_id':'multi-judge-consensus-v1','manifest_sha256':SHAS['execution_manifest_v1.json'],'package_id':'multijudge-consensus-v1','promotion_status':'PROMOTE_AS_OFFICIAL_SECONDARY_RQ7_MITIGATION','metrics':metrics,'bootstrap':primary['bootstrap'],'lineage_sha256':SHAS}
  rows=list(s.scalars(select(AnalysisRun).where(AnalysisRun.analysis_version=='multi-judge-consensus-analysis-v1')))
  if len(rows)>1: raise RuntimeError('multiple secondary AnalysisRuns')
  if rows: run=rows[0]; assert run.result_json==payload
  else: run=AnalysisRun(experiment_id=dual.experiment_id,manifest_id=dual.manifest_id,rq_code='RQ7',analysis_version='multi-judge-consensus-analysis-v1',analysis_seed=20260823,status='COMPLETED',result_json=payload);s.add(run);s.flush()
  batch=s.scalar(select(MultiJudgeExecutionBatch).where(MultiJudgeExecutionBatch.manifest_sha256==SHAS['execution_manifest_v1.json'])); slots=list(s.scalars(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id==batch.id))); attempts=list(s.scalars(select(MultiJudgeExecutionAttempt)))
  if (len(slots),len(attempts))!=(6444,6543): raise RuntimeError('ledger count mismatch')
  by={str(x.id):x for x in slots}; actual=sum((x.actual_usd or Decimal('0')) for x in attempts); reserved=sum(x.reserved_usd for x in attempts)
  if (actual,reserved)!=(Decimal('1.46018394'),Decimal('2.48550295')): raise RuntimeError('cost mismatch')
  per={j:sum((x.actual_usd or Decimal('0')) for x in attempts if by[str(x.slot_id)].judge_id==j) for j in ('gpt-4o-mini','anthropic/claude-3-haiku','deepseek/deepseek-chat','meta-llama/llama-3.3-70b-instruct')}
  slots_out=[{'slot_id':str(x.id),'pair_id':x.canonical_pair_id,'planned_pass_id':x.planned_pass_id,'idempotency_key':x.idempotency_key,'judge':x.judge_id,'requested_model':x.requested_model,'provider':x.provider,'route':x.route,'presentation':x.presentation,'original_answer_1_id':x.original_answer_1_id,'original_answer_2_id':x.original_answer_2_id,'displayed_a_answer_id':x.displayed_a_answer_id,'displayed_b_answer_id':x.displayed_b_answer_id,'status':x.status,'mapped_vote':x.mapped_vote,'final_outcome':x.final_outcome,'attempt_count':x.attempt_count} for x in slots]
  attempts_out=[{'attempt_id':x.attempt_id,'slot_id':str(x.slot_id),'attempt_index':x.attempt_index,'state':x.state,'failure_category':x.failure_category,'retry_decision':x.retry_decision,'input_tokens':x.input_tokens,'output_tokens':x.output_tokens,'reserved_usd':x.reserved_usd,'actual_usd':x.actual_usd,'effective_model':x.effective_model,'route_provenance':x.route_provenance_json,'started_at':x.started_at,'completed_at':x.completed_at} for x in attempts]
  s.commit();s.refresh(run); assert dual_hash==hashlib.sha256(json.dumps(dual.result_json,sort_keys=True,default=str).encode()).hexdigest()
 (OUT/'source').mkdir(parents=True,exist_ok=True)
 for n in SHAS: shutil.copy2(SRC/n,OUT/'source'/n)
 dump(OUT/'exports'/'execution_slots.json',slots_out);dump(OUT/'exports'/'attempts.json',attempts_out);dump(OUT/'execution_accounting.json',{'pairs':1611,'planned_slots':6444,'completed_slots':6390,'terminal_failures':52,'ambiguous_slots':2,'attempts':6543,'retries':99});dump(OUT/'cost_ledger.json',{'hard_cap_usd':'2.50','actual_spend_usd':str(actual),'reserved_spend_usd':str(reserved),'per_judge_actual_usd':{k:str(v) for k,v in per.items()},'reconciled':sum(per.values())==actual});dump(OUT/'analysis_run.json',{'id':str(run.id),'rq_code':'RQ7','role':'SECONDARY','host_manifest_id':str(run.manifest_id),'metrics':metrics,'result_json':run.result_json});dump(OUT/'provenance.json',{'package_id':'multijudge-consensus-v1','created_at':datetime.now(timezone.utc).isoformat(),'source_db':'current PostgreSQL ledger','phase11_unchanged':True,'research_release_v2_unchanged':True,'api_integration':False})
 verifier="import hashlib,json,sys,uuid\nfrom pathlib import Path\nR=Path(__file__).resolve().parent\nsys.path.insert(0,str(R.parents[2]/'backend'))\nfrom database import SessionLocal\nfrom controlled_models import AnalysisRun\ndef h(p): return hashlib.sha256(p.read_bytes()).hexdigest()\nm=json.loads((R/'package_manifest.json').read_text()); i=m['file_inventory']; a={x['path']:h(R/x['path']) for x in i}\nassert all(a[x['path']]==x['sha256'] for x in i)\nlines=''.join(x['sha256']+'  '+x['path']+'\\n' for x in sorted(i,key=lambda x:x['path']))\nassert hashlib.sha256(lines.encode()).hexdigest()==m['package_root_digest']\np=json.loads((R/'analysis_run.json').read_text())\nwith SessionLocal() as s: row=s.get(AnalysisRun,uuid.UUID(p['id'])); assert row and row.result_json['metrics']==p['metrics']\nprint('MULTI_JUDGE_CONSENSUS_PACKAGE_VERIFIED')\n"
 (OUT/'VERIFY_PACKAGE.py').write_text(verifier,encoding='utf-8')
 inv=[{'path':p.relative_to(OUT).as_posix(),'sha256':h(p)} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='package_manifest.json']; root=hashlib.sha256(''.join(f"{x['sha256']}  {x['path']}\n" for x in sorted(inv,key=lambda x:x['path'])).encode()).hexdigest()
 dump(OUT/'package_manifest.json',{'package_id':'multijudge-consensus-v1','version':1,'immutable_additive_package':True,'root_digest_algorithm':'SHA-256 of sorted UTF-8 SHA256<two spaces>relative_posix_path lines; manifest excluded to avoid self-reference','package_root_digest':root,'lineage_sha256':SHAS,'analysis_run_id':str(run.id),'execution_counts':{'pairs':1611,'slots':6444,'attempts':6543},'cost_totals':{'actual_usd':str(actual),'reserved_usd':str(reserved),'hard_cap_usd':'2.50'},'file_inventory':inv})
 print(f'PACKAGE {OUT}');print(f'ANALYSIS_RUN {run.id}');print(f'ROOT_DIGEST {root}')
if __name__=='__main__':main()
