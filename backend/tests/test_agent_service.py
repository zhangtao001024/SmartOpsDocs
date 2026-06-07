import json
import io
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.agent_service as agent_service
from app.core.database import Base
from app.models.entities import Document
from app.models.entities import AppSetting
from app.services.ai_service import answer_question
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


def test_openclaw_endpoint_tries_common_agent_paths(monkeypatch):
    attempts = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"answer": "endpoint ok"}).encode("utf-8")

    def fake_urlopen(req, timeout):
        attempts.append(req.full_url)
        assert timeout == 90
        if req.full_url.endswith("/api/agent/run"):
            return FakeResponse()
        raise agent_service.url_error.HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=io.BytesIO(b"missing"))

    monkeypatch.setattr(agent_service.url_request, "urlopen", fake_urlopen)

    answer = agent_service._call_openclaw_endpoint(
        {"endpoint": "http://openclaw.local", "api_key": "", "agent": "main"},
        {"project": "default", "session_id": "s1", "goal": "ping"},
    )

    assert answer == "endpoint ok"
    assert attempts[:2] == ["http://openclaw.local", "http://openclaw.local/api/agent/run"]


def test_openclaw_runtime_requires_gateway_endpoint():
    try:
        agent_service._call_openclaw_runtime(
            {"endpoint": "", "api_key": "", "agent": "main"},
            {"project": "default", "session_id": "s1", "goal": "ping"},
        )
    except RuntimeError as exc:
        assert "Gateway URL 未配置" in str(exc)
    else:
        raise AssertionError("expected missing gateway endpoint to fail")


def test_openclaw_runtime_uses_gateway_without_cli_fallback(monkeypatch):
    monkeypatch.setattr(agent_service, "_call_openclaw_endpoint", lambda _runtime, _payload: "gateway ok")

    answer, mode = agent_service._call_openclaw_runtime(
        {"endpoint": "http://openclaw.local", "api_key": "", "agent": "main"},
        {"project": "default", "session_id": "s1", "goal": "ping"},
    )

    assert answer == "gateway ok"
    assert mode == "openclaw-gateway"


def test_resolve_agent_runtime_includes_web_skills():
    db = make_session()

    db.add(AppSetting(key="agent_runtime", value="openclaw"))
    db.add(AppSetting(key="openclaw_agent", value="main"))
    db.add(AppSetting(key="openclaw_web_skills", value="browser-automation,summarize,bad skill"))
    db.commit()

    runtime = agent_service._resolve_agent_runtime(db)

    assert runtime["runtime"] == "openclaw"
    assert runtime["agent"] == "main"
    assert runtime["web_skills"] == ["browser-automation", "summarize"]


def test_knowledge_chat_uses_openclaw_gateway_runtime(monkeypatch, tmp_path):
    use_tmp_knowledge_dir(monkeypatch, tmp_path)
    db = make_session()
    db.add(AppSetting(key="agent_runtime", value="openclaw"))
    db.add(AppSetting(key="openclaw_endpoint", value="http://openclaw.local/api/agent/run"))
    db.add(AppSetting(key="openclaw_agent", value="knowledge-main"))
    db.commit()
    create_knowledge_draft(
        db,
        title="Docker 部署",
        markdown="# Docker 部署\n\n使用 docker compose up -d --build。",
        project="default",
    )
    db.commit()
    captured = {}

    def fake_call(runtime, payload):
        captured["runtime"] = runtime
        captured["payload"] = payload
        return "Gateway answer", "openclaw-gateway"

    monkeypatch.setattr(agent_service, "_call_openclaw_runtime", fake_call)

    result = answer_question(db, "default", "docker compose", "s-knowledge")

    assert result["answer"] == "Gateway answer"
    assert result["mode"] == "openclaw-gateway"
    assert captured["runtime"]["endpoint"] == "http://openclaw.local/api/agent/run"
    assert captured["payload"]["response_format"] == "knowledge_agent_answer"
    assert "docker compose" in captured["payload"]["context"]["knowledge_context"]
