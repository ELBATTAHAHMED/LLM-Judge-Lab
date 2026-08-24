from types import SimpleNamespace
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
from main import serialize_multi_judge_secondary

METRICS={'planned_n':1,'retained_n':1,'agreement':.7,'coverage':.7,'equal_weight_individual_baseline':.6,'matched_delta':.1,'ci_low':.01,'ci_high':.2}
def row(**changes):
 p={'rq_code':'RQ7','mitigation_role':'SECONDARY','package_id':'p','protocol_id':'x','metrics':dict(METRICS)};p.update(changes);return SimpleNamespace(id='id',rq_code=p.pop('run_rq','RQ7'),result_json=p)
def test_valid_secondary_serializes_without_direct_delta():
 x,e=serialize_multi_judge_secondary([row()]);assert e is None;v=x['multi_judge_consensus'];assert v['role']=='SECONDARY' and v['direct_dualswap_comparison']=='NOT_DEFENSIBLE' and 'dualswap_delta' not in v
def test_missing_and_duplicate_fail_closed():
 assert serialize_multi_judge_secondary([])[0] is None;assert serialize_multi_judge_secondary([row(),row()])[0] is None
def test_wrong_rq_and_role_fail_closed():
 assert serialize_multi_judge_secondary([row(run_rq='RQ6')])[0] is None;assert serialize_multi_judge_secondary([row(mitigation_role='PRIMARY')])[0] is None
def test_missing_metric_ci_and_provenance_fail_closed():
 for change in ({'metrics':{k:v for k,v in METRICS.items() if k!='agreement'}},{'metrics':{k:v for k,v in METRICS.items() if k!='ci_low'}},{'package_id':''},{'protocol_id':''}):assert serialize_multi_judge_secondary([row(**change)])[0] is None
