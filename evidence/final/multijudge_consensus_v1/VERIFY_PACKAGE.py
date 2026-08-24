import hashlib,json,sys,uuid
from pathlib import Path
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parents[2]/'backend'))
from database import SessionLocal
from controlled_models import AnalysisRun
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((R/'package_manifest.json').read_text()); i=m['file_inventory']; a={x['path']:h(R/x['path']) for x in i}
assert all(a[x['path']]==x['sha256'] for x in i)
lines=''.join(x['sha256']+'  '+x['path']+'\n' for x in sorted(i,key=lambda x:x['path']))
assert hashlib.sha256(lines.encode()).hexdigest()==m['package_root_digest']
p=json.loads((R/'analysis_run.json').read_text())
with SessionLocal() as s: row=s.get(AnalysisRun,uuid.UUID(p['id'])); assert row and row.result_json['metrics']==p['metrics']
print('MULTI_JUDGE_CONSENSUS_PACKAGE_VERIFIED')
