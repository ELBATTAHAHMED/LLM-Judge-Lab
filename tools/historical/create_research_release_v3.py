"""Provider-free additive v3 PostgreSQL snapshot including Multi-Judge evidence."""
from __future__ import annotations
import hashlib,json,subprocess,sys,uuid
from datetime import datetime,timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from backend.release.utils import PG_BIN, postgres_connection, run, sha256  # noqa: E402
from backend.core.database import DATABASE_URL,SessionLocal  # noqa: E402
from backend.core.controlled_models import AnalysisRun  # noqa: E402
from backend.core.final_evidence import CANONICAL_FINAL_ANALYSIS_RUNS  # noqa: E402

REL=ROOT/'evidence'/'final'/'research_release_v3'; PKG=ROOT/'evidence'/'final'/'multijudge_consensus_v1'; MJ='fc40faf1-b886-42f8-8faf-a616f61f3107'
def restore(snapshot,base,env):
 name='judgelab_v3_verify_'+uuid.uuid4().hex[:10];psql=str(PG_BIN/'psql.exe');restore=str(PG_BIN/'pg_restore.exe')
 try:
  run([psql,*base,'-d','postgres','-v','ON_ERROR_STOP=1','-c',f'CREATE DATABASE "{name}"'],env=env);run([restore,'--no-owner','--no-privileges','--dbname',name,*base,str(snapshot)],env=env)
  q=lambda sql:run([psql,*base,'-d',name,'-At','-v','ON_ERROR_STOP=1','-c',sql],env=env).strip()
  return {'status':'PASSED','analysis_runs':int(q('SELECT count(*) FROM analysis_runs')),'multijudge_analysis_runs':int(q("SELECT count(*) FROM analysis_runs WHERE analysis_version='multi-judge-consensus-analysis-v1'")),'slots':int(q('SELECT count(*) FROM multijudge_execution_slots')),'attempts':int(q('SELECT count(*) FROM multijudge_execution_attempts'))}
 finally: run([psql,*base,'-d','postgres','-v','ON_ERROR_STOP=1','-c',f'DROP DATABASE IF EXISTS "{name}"'],env=env)
def main():
 if not (PG_BIN/'pg_dump.exe').exists():raise RuntimeError('PostgreSQL tools unavailable')
 base,env=postgres_connection();REL.mkdir(parents=True,exist_ok=True);db=REL/'database';db.mkdir(exist_ok=True);snap=db/'judgelab-research-release-v3.dump'
 with SessionLocal() as s:
  r=s.get(AnalysisRun,uuid.UUID(MJ)); assert r and r.result_json['metrics']['retained_n']==1125 and r.result_json['mitigation_role']=='SECONDARY'; assert s.get(AnalysisRun,uuid.UUID(CANONICAL_FINAL_ANALYSIS_RUNS['RQ7'])); current=s.query(AnalysisRun).count()
 if current!=14:raise RuntimeError(f'unexpected AnalysisRun count {current}')
 run([str(PG_BIN/'pg_dump.exe'),'--format=custom','--no-owner','--no-privileges','--file',str(snap),*base,DATABASE_URL.rsplit('/',1)[-1].split('?',1)[0]],env=env)
 listing=run([str(PG_BIN/'pg_restore.exe'),'--list',str(snap)],env=env);(db/'pg_restore_list.txt').write_text(listing,encoding='utf-8');check=restore(snap,base,env)
 if check!={'status':'PASSED','analysis_runs':14,'multijudge_analysis_runs':1,'slots':6444,'attempts':6543}:raise RuntimeError(f'restore mismatch {check}')
 manifest={'release':'research_release_v3','created_at':datetime.now(timezone.utc).isoformat(),'source_commit':__import__('subprocess').check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'provider_calls':0,'database_snapshot':{'path':'database/'+snap.name,'sha256':sha256(snap),'size_bytes':snap.stat().st_size,'pg_restore_list':'database/pg_restore_list.txt','restore_validation':check},'analysis_runs':{'pre_multijudge_release_v2_count':13,'release_v3_count':14,'multijudge_secondary_id':MJ,'dualswap_primary_id':CANONICAL_FINAL_ANALYSIS_RUNS['RQ7']},'multijudge_package':{'path':'evidence/final/multijudge_consensus_v1','package_root_digest':json.loads((PKG/'package_manifest.json').read_text())['package_root_digest']},'statements':{'dualswap_remains_primary_rq7':True,'multijudge_is_secondary_rq7':True,'phase11_immutable':True,'research_release_v2_immutable':True,'api_unchanged':True}}
 (REL/'RELEASE_MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 files=sorted(p for p in REL.rglob('*') if p.is_file() and p.name not in {'SHA256SUMS.txt','VERIFY_RELEASE.py'});(REL/'SHA256SUMS.txt').write_text(''.join(f'{sha256(p)}  {p.relative_to(REL).as_posix()}\n' for p in files),encoding='utf-8')
 verifier="import hashlib,subprocess,sys\nfrom pathlib import Path\nR=Path(__file__).resolve().parent\ndef h(p):return hashlib.sha256(p.read_bytes()).hexdigest()\nfor l in (R/'SHA256SUMS.txt').read_text().splitlines():\n s,p=l.split('  ',1);assert h(R/p)==s\nsubprocess.run([r'C:\\Program Files\\PostgreSQL\\17\\bin\\pg_restore.exe','--list',str(R/'database'/'judgelab-research-release-v3.dump')],check=True,stdout=subprocess.DEVNULL)\nsubprocess.run([sys.executable,str(R.parents[0]/'multijudge_consensus_v1'/'VERIFY_PACKAGE.py')],check=True)\nprint('RESEARCH_RELEASE_V3_VERIFIED')\n";(REL/'VERIFY_RELEASE.py').write_text(verifier,encoding='utf-8')
 print(json.dumps({'dump_sha256':manifest['database_snapshot']['sha256'],'restore':check},sort_keys=True))
if __name__=='__main__':main()
