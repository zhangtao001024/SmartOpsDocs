from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routers.system import collect_health_status, collect_system_status, system_status
from app.core.database import Base
from app.models.entities import Document, ServerAsset, User


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_system_status_reports_database_and_counts():
    db = make_session()
    db.add(ServerAsset(ip="127.0.0.1", status="online"))
    db.add(Document(title="Runbook", file_path=str(Path("runbook.md")), project="default", status="completed"))
    db.commit()

    payload = system_status(db=db, _=User(username="admin", password_hash="x", role="admin"))

    assert payload["status"] in {"ok", "degraded"}
    assert payload["database"]["ok"] is True
    assert payload["counts"]["servers"] == 1
    assert payload["counts"]["servers_online"] == 1
    assert payload["counts"]["documents"] == 1


def test_collect_health_status_reports_ready_runtime():
    db = make_session()

    payload = collect_health_status(db)

    assert payload["status"] in {"ok", "degraded"}
    assert payload["database"]["ok"] is True
    assert "counts" not in payload
    assert "issues" in payload


def test_collect_system_status_reports_degraded_when_count_query_fails():
    class BrokenQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def count(self):
            raise RuntimeError("count failed")

    class BrokenSession:
        def execute(self, _statement):
            return None

        def query(self, _model):
            return BrokenQuery()

    payload = collect_system_status(BrokenSession())

    assert payload["status"] == "degraded"
    assert payload["counts"]["servers"] == 0
    assert payload["issues"][0]["scope"] == "counts"
