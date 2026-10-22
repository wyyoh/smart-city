"""Prepare a separate creative-demo database without changing the original database."""
from contextlib import closing
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def prepare():
    source = ROOT/'data/workbench.sqlite'
    destination = ROOT/'artifacts/polish-v7/ui-demo.sqlite'
    if destination.exists():
        return destination
    if not source.is_file():
        raise FileNotFoundError('Run scripts/setup.ps1 to restore the original database first.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)) as old, closing(sqlite3.connect(destination)) as new:
        old.backup(new)
        if new.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise RuntimeError('Creative demo database integrity check failed.')
    return destination


if __name__ == '__main__':
    print(prepare())
