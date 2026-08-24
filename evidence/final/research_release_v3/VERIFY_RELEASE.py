import hashlib,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parent
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for l in (R/'SHA256SUMS.txt').read_text().splitlines():
 s,p=l.split('  ',1);assert h(R/p)==s
subprocess.run([r'C:\Program Files\PostgreSQL\17\bin\pg_restore.exe','--list',str(R/'database'/'judgelab-research-release-v3.dump')],check=True,stdout=subprocess.DEVNULL)
subprocess.run([sys.executable,str(R.parents[0]/'multijudge_consensus_v1'/'VERIFY_PACKAGE.py')],check=True)
print('RESEARCH_RELEASE_V3_VERIFIED')
