"""Administrative adaptation only: paths, starting commit and authorization."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ORIGINAL=HERE.with_name('perf391-a-functional-smoke-v1')
sys.path.insert(0,str(ORIGINAL))
source=(HERE/'preflight-adapted.txt').read_text()
exec(compile(source,str(ORIGINAL/'preflight.py'),'exec'),{'__file__':str(ORIGINAL/'preflight.py'),'__name__':'__main__'})
