from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / 'data'
ARTIFACTS_DIR = ROOT / 'artifacts'
DATABASE_PATH = Path(os.environ.get('ASPHALT_DATABASE', str(DATA_DIR / 'workbench.sqlite')))
FRONTEND_DIST = ROOT / 'frontend' / 'dist'
VERSION = '0.1.0'

