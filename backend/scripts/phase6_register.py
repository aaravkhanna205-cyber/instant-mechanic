"""Idempotently registers Phase 6 with the EXISTING FastAPI app. Backs up main.py."""
from pathlib import Path
import ast, shutil, sys, os, datetime
main=Path(__file__).resolve().parents[1]/'app'/'main.py'
if not main.exists():raise SystemExit('Missing backend/app/main.py')
src=main.read_text(encoding='utf-8-sig')
if 'app.include_router(phase6_router)' in src:
    print('Phase 6 API already registered');sys.exit(0)
if 'app = FastAPI(' not in src and 'app=FastAPI(' not in src:
    raise SystemExit('Cannot find expected FastAPI app variable; no modifications made')
patch='\n# Phase 6: authenticated automation endpoints\nfrom app.phase6_agents.api import router as phase6_router\napp.include_router(phase6_router)\n'
try:ast.parse(src+patch)
except SyntaxError as exc:raise SystemExit(f'Would produce invalid Python: {exc}')
backup_dir=Path(os.getenv('PHASE6_BACKUP_DIR',str(Path.home()/'InstantMechanicPhase6Backups')))
backup_dir.mkdir(parents=True,exist_ok=True)
backup=backup_dir/('main.py.'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.bak')
shutil.copy2(main,backup)
try:main.write_text(src+patch,encoding='utf-8')
except Exception:
    shutil.copy2(backup,main);raise
print('Phase 6 routes registered; original main.py backed up')
