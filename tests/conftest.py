from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

from app.importer import import_workbook
from app.main import create_app
from app.settings import ROOT
from app.storage import initialize, make_engine


@pytest.fixture(scope='session')
def imported_db(tmp_path_factory):
    path = tmp_path_factory.mktemp('data')/'baseline.sqlite'
    engine = make_engine(path)
    initialize(engine)
    with Session(engine) as session:
        import_workbook(ROOT/'再生沥青混合料实验数据表.xlsx', session)
    engine.dispose()
    return path


@pytest.fixture
def database(imported_db, tmp_path):
    path = tmp_path/'test.sqlite'
    shutil.copyfile(imported_db, path)
    engine = make_engine(path)
    yield engine
    engine.dispose()


@pytest.fixture
def client(database):
    with TestClient(create_app(database)) as client:
        yield client
