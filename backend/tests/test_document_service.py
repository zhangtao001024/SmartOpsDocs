from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import Document
import app.services.document_service as document_service
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


@pytest.fixture(autouse=True)
def disable_real_embeddings(monkeypatch):
    monkeypatch.setattr(
        document_service,
        "_resolve_embedding_config",
        lambda _db: {"api_key": "", "base_url": None, "model": "text-embedding-3-small"},
    )


def test_split_text_uses_overlap():
    chunks = split_text("a" * 1200, chunk_size=500, overlap=100)
    assert len(chunks) == 3
    assert chunks[1].startswith("a" * 20)


def test_split_text_keeps_markdown_heading_context():
    markdown = "# 部署\n\n" + ("kubectl apply 后等待工作负载就绪。" * 4) + "\n\n## 验证\n\nkubectl get pods"
    chunks = split_text(markdown, chunk_size=90, overlap=20)

    assert chunks[0].startswith("# 部署")
    assert any("## 验证\n\nkubectl get pods" in chunk for chunk in chunks)


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


def test_search_chunks_handles_fts_reserved_terms_with_title_fallback():
    db = make_session()
    exact = Document(title="OR", file_path=str(Path("or.md")), project="default")
    later = Document(title="Later OR Runbook", file_path=str(Path("later.md")), project="default")
    db.add_all([exact, later])
    db.commit()
    db.refresh(exact)
    db.refresh(later)

    rebuild_document_chunks(db, exact, "plain content")
    rebuild_document_chunks(db, later, "plain content")
    db.commit()

    hits = search_chunks(db, "default", "OR", limit=3)

    assert hits[0].document_id == exact.id


def test_search_chunks_uses_vector_hits_when_keywords_do_not_match(monkeypatch):
    def fake_embed(texts, _config):
        vectors = []
        for text in texts:
            if any(term in text for term in ["工作负载", "Pending", "调度"]):
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return vectors

    monkeypatch.setattr(
        document_service,
        "_resolve_embedding_config",
        lambda _db: {"api_key": "sk-test", "base_url": None, "model": "fake-embedding"},
    )
    monkeypatch.setattr(document_service, "_embed_texts", fake_embed)

    db = make_session()
    pending = Document(title="Pod Pending 排查", file_path=str(Path("pending.md")), project="default")
    docker = Document(title="Docker 清理", file_path=str(Path("docker.md")), project="default")
    db.add_all([pending, docker])
    db.commit()
    db.refresh(pending)
    db.refresh(docker)

    rebuild_document_chunks(db, pending, "节点资源不足导致 Pod Pending，调度器无法绑定节点。")
    rebuild_document_chunks(db, docker, "清理无用镜像和悬空 volume。")
    db.commit()

    hits = search_chunks(db, "default", "工作负载无法启动", limit=2)

    assert hits[0].document_id == pending.id


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
