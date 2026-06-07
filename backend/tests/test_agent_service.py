import json
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.agent_service as agent_service
from app.core.database import Base
from app.models.entities import Document
from app.services.agent_service import run_agent
from app.services.document_service import create_knowledge_draft, read_document_markdown, search_chunks


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def use_tmp_knowledge_dir(monkeypatch, tmp_path):
    import app.services.document_service as document_service

    monkeypatch.setattr(document_service, "get_settings", lambda: SimpleNamespace(knowledge_dir=tmp_path))


def test_create_knowledge_draft_indexes_draft_content(monkeypatch, tmp_path):
    use_tmp_knowledge_dir(monkeypatch, tmp_path)
    db = make_session()
    draft = create_knowledge_draft(
        db,
        title="Agent 草稿",
        markdown="# Pod Pending 排查\n\n检查调度事件和节点资源。",
        project="default",
    )
    db.commit()

    assert draft.status == "draft"
    assert "Pod Pending" in read_document_markdown(draft.id)
    hits = search_chunks(db, "default", "调度事件", limit=3)
    assert hits[0].document_id == draft.id


def test_run_agent_dry_run_blocks_knowledge_draft_write(monkeypatch, tmp_path):
    use_tmp_knowledge_dir(monkeypatch, tmp_path)
    db = make_session()
    result = run_agent(
        db,
        project="default",
        goal="总结 Pod Pending 排查步骤",
        session_id="s1",
        tools=[],
        dry_run=True,
        context={"auto_knowledge": True},
    )

    draft_call = [call for call in result["tool_calls"] if call["tool"] == "knowledge.create_draft"][0]
    assert draft_call["status"] == "blocked_dry_run"
    assert db.query(Document).filter(Document.status == "draft").count() == 0


def test_run_agent_can_write_agent_knowledge_draft_when_dry_run_disabled(monkeypatch, tmp_path):
    use_tmp_knowledge_dir(monkeypatch, tmp_path)
    db = make_session()
    result = run_agent(
        db,
        project="default",
        goal="总结 Docker 容器异常排查步骤",
        session_id="s2",
        tools=[],
        dry_run=False,
        context={"auto_knowledge": True},
    )

    assert result["knowledge_drafts"]
    draft = db.get(Document, result["knowledge_drafts"][0]["document_id"])
    assert draft is not None
    assert draft.status == "draft"
    assert "Docker" in read_document_markdown(draft.id)


def test_openclaw_cli_call_extracts_payload_text(monkeypatch):
    calls = {}

    def fake_run(cmd, capture_output, text, timeout):
        calls["cmd"] = cmd
        assert capture_output is True
        assert text is True
        assert timeout == 120
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"status": "ok", "result": {"payloads": [{"text": "正常"}]}}),
            stderr="",
        )

    monkeypatch.setattr(agent_service.shutil, "which", lambda name: "/usr/local/bin/openclaw")
    monkeypatch.setattr(agent_service.subprocess, "run", fake_run)

    answer = agent_service._call_openclaw_cli(
        {"agent": "main"},
        {"project": "default", "session_id": "s 1", "goal": "检查状态"},
    )

    assert answer == "正常"
    assert calls["cmd"][:4] == ["/usr/local/bin/openclaw", "agent", "--agent", "main"]
    assert "agent:main:smartopsdocs-default-s-1" in calls["cmd"]
