"""Local private development storage. Production must use approved private object storage."""
import os
from pathlib import Path
from uuid import UUID

def base_dir() -> Path:
    base=Path(os.getenv('PHASE4_PRIVATE_DIR',str(Path(__file__).resolve().parents[2]/'.private_phase4'))).resolve()
    base.mkdir(parents=True,exist_ok=True)
    return base

def path_for(id: UUID, ext: str) -> Path:
    if ext not in ('pdf','docx','txt'): raise ValueError('Invalid extension')
    return base_dir() / (str(id)+'.'+ext)

def save_bytes(id: UUID, ext: str, content: bytes) -> Path:
    path=path_for(id,ext)
    with path.open('xb') as f:
        os.chmod(path,0o600)
        f.write(content)
    return path
