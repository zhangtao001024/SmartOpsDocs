import sys
from types import ModuleType

import pytest
from fastapi import HTTPException

from app.api.routers.settings import ModelConfig, _test_model_config


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
