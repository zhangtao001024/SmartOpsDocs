from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import Document
from app.services.document_service import (
    create_document_revision,
    rebuild_document_chunks,
    restore_document_revision,
    search_chunks,
    split_text,
)


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_split_text_uses_overlap():
    chunks = split_text("a" * 1200, chunk_size=500, overlap=100)
    assert len(chunks) == 3
    assert chunks[1].startswith("a" * 20)


def test_search_chunks_uses_content_and_title_matches():
    db = make_session()
    document = Document(title="Pod CrashLoop 排查", file_path=str(Path("demo.md")), project="default")
    db.add(document)
    db.commit()
    db.refresh(document)

    rebuild_document_chunks(db, document, "检查 kubectl describe pod 和 events 中的 Warning")
    db.commit()

    content_hits = search_chunks(db, "default", "kubectl", limit=3)
    title_hits = search_chunks(db, "default", "CrashLoop", limit=3)

    assert content_hits[0].document_id == document.id
    assert title_hits[0].document_id == document.id


def test_restore_document_revision_rebuilds_chunks():
    db = make_session()
    document = Document(title="部署手册", file_path=str(Path("demo.md")), project="default")
    db.add(document)
    db.commit()
    db.refresh(document)

    revision = create_document_revision(db, document, "# v1\n\n旧内容", note="manual-edit")
    db.commit()
    restore_document_revision(db, document, revision.id)

    db.refresh(document)
    assert document.status == "completed"
    assert document.chunks[0].content.startswith("# v1")
