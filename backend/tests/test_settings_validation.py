import sys
from types import ModuleType

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routers.settings import AgentRuntimeConfig, ModelConfig, _load_agent_config, _save_agent_config, _test_model_config
from app.core.database import Base


def install_fake_openai(monkeypatch, *, list_error: Exception, chat_error: Exception):
    module = ModuleType("openai")

    class FakeModels:
        def list(self):
            raise list_error

    class FakeCompletions:
        def create(self, **_kwargs):
            raise chat_error

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        models = FakeModels()
        chat = FakeChat()

        def __init__(self, **_kwargs):
            pass

    module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", module)


def test_model_validation_probe_block_returns_warning(monkeypatch):
    install_fake_openai(
        monkeypatch,
        list_error=RuntimeError("models endpoint is not available"),
        chat_error=RuntimeError("Your request was blocked."),
    )

    result = _test_model_config(ModelConfig(api_key="sk-test", base_url="https://example.test/v1", model="ops-model"))

    assert result.ok is True
    assert result.level == "warning"
    assert "验证探针被服务商策略拦截" in result.message
    assert "ops-model" in result.message


def test_model_validation_non_policy_error_still_fails(monkeypatch):
    install_fake_openai(
        monkeypatch,
        list_error=RuntimeError("models endpoint is not available"),
        chat_error=RuntimeError("model does not exist"),
    )

    with pytest.raises(HTTPException) as exc:
        _test_model_config(ModelConfig(api_key="sk-test", base_url="https://example.test/v1", model="missing-model"))

    assert exc.value.status_code == 400
    assert "模型验证失败" in exc.value.detail


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_agent_config_persists_selected_web_skills():
    db = make_session()

    _save_agent_config(
        db,
        AgentRuntimeConfig(
            runtime="openclaw",
            endpoint="http://openclaw.local/api/agent/run",
            api_key="",
            agent="main",
            web_skills=["browser-automation", "summarize", "browser-automation", "bad skill name"],
        ),
    )
    db.commit()

    loaded = _load_agent_config(db)

    assert loaded.runtime == "openclaw"
    assert loaded.endpoint == "http://openclaw.local/api/agent/run"
    assert loaded.agent == "main"
    assert loaded.web_skills == ["browser-automation", "summarize"]


def test_openclaw_agent_config_requires_gateway_url():
    db = make_session()

    with pytest.raises(HTTPException) as exc:
        _save_agent_config(
            db,
            AgentRuntimeConfig(
                runtime="openclaw",
                endpoint="",
                api_key="",
                agent="main",
                web_skills=["browser-automation"],
            ),
        )

    assert exc.value.status_code == 400
    assert "Gateway URL" in exc.value.detail
