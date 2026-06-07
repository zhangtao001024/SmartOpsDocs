from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routers.documents import documents as list_documents
from app.api.routers.documents import knowledge_tree
from app.api.routers.servers import servers as list_servers
from app.core.database import Base
from app.models.entities import Document, DocumentChunk, ServerAsset, User


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_servers_filter_by_query_project_and_environment():
    db = make_session()
    db.add(ServerAsset(ip="10.0.0.1", hostname="api-prod", project="core", environment="prod", tags="gateway"))
    db.add(ServerAsset(ip="10.0.0.2", hostname="worker-dev", project="core", environment="dev", tags="batch"))
    db.add(ServerAsset(ip="10.0.0.3", hostname="docs-prod", project="docs", environment="prod", tags="wiki"))
    db.commit()

    rows = list_servers(
        q="api",
        project="core",
        environment="prod",
        status=None,
        offset=0,
        limit=None,
        db=db,
        _=User(username="admin", password_hash="x", role="admin"),
    )

    assert len(rows) == 1
    assert rows[0].hostname == "api-prod"


def test_documents_and_knowledge_tree_filter_by_query_and_status():
    db = make_session()
    runbook = Document(title="K8s Runbook", file_path=str(Path("k8s.md")), project="ops", status="completed")
    draft = Document(title="Docker Draft", file_path=str(Path("docker.md")), project="ops", status="uploaded")
    db.add_all([runbook, draft])
    db.commit()
    db.refresh(runbook)
    db.add(DocumentChunk(document_id=runbook.id, chunk_index=0, content="restart pod", project="ops"))
    db.commit()

    document_rows = list_documents(
        project="ops",
        q="runbook",
        status="completed",
        offset=0,
        limit=None,
        db=db,
        _=User(username="admin", password_hash="x", role="admin"),
    )
    tree_rows = knowledge_tree(
        project="ops",
        q="runbook",
        status="completed",
        offset=0,
        limit=None,
        db=db,
        _=User(username="admin", password_hash="x", role="admin"),
    )

    assert [row.title for row in document_rows] == ["K8s Runbook"]
    assert len(tree_rows) == 1
    assert tree_rows[0]["title"] == "K8s Runbook"
    assert tree_rows[0]["chunk_count"] == 1
