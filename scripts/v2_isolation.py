"""Online read-only baseline copy, also usable in the relocated release bundle."""
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[1]


def copy_baseline(destination):
    registered=ROOT/'artifacts/next-phase/baseline/workbench-v01.sqlite'
    source=registered if registered.exists() else ROOT/'data/workbench.sqlite'
    if not source.exists():
        raise FileNotFoundError('没有基线或已导入的目录库；请先运行工作簿导入。')
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as original, sqlite3.connect(destination) as copied:
        original.backup(copied)
        assert copied.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
