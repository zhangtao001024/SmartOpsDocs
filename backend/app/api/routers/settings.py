"""系统设置路由."""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import AppSetting, User
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["settings"])


class ModelConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"
    vision_model: str = ""


class AgentRuntimeConfig(BaseModel):
    runtime: str = "local-openclaw"
    endpoint: str = ""
    api_key: str = ""
    agent: str = "smartopsdocs-ops-agent"


class SettingsRequest(BaseModel):
    chat: ModelConfig = ModelConfig()
    optimize: ModelConfig = ModelConfig()
    pull: ModelConfig = ModelConfig()
    agent: AgentRuntimeConfig = AgentRuntimeConfig()


class SettingsResponse(BaseModel):
    chat: ModelConfig
    optimize: ModelConfig
    pull: ModelConfig
    agent: AgentRuntimeConfig


class SettingsTestRequest(BaseModel):
    scope: str
    config: dict = {}


class SettingsTestResponse(BaseModel):
    ok: bool
    message: str
    latency_ms: int | None = None
    level: str = "ok"


def _load_config(db: Session, prefix: str, env_fallback: dict) -> ModelConfig:
    keys = [f"{prefix}_api_key", f"{prefix}_base_url", f"{prefix}_model", f"{prefix}_vision_model"]
    db_vals = {}
    for row in db.query(AppSetting).filter(AppSetting.key.in_(keys)).all():
        db_vals[row.key] = row.value
    return ModelConfig(
        api_key=db_vals.get(f"{prefix}_api_key") or env_fallback.get("api_key", ""),
        base_url=db_vals.get(f"{prefix}_base_url") or env_fallback.get("base_url", ""),
        model=db_vals.get(f"{prefix}_model") or env_fallback.get("model", "gpt-4o-mini"),
        vision_model=db_vals.get(f"{prefix}_vision_model") or env_fallback.get("vision_model", ""),
    )


def _save_config(db: Session, prefix: str, cfg: ModelConfig) -> None:
    overrides = {
        f"{prefix}_api_key": cfg.api_key,
        f"{prefix}_base_url": cfg.base_url,
        f"{prefix}_model": cfg.model,
        f"{prefix}_vision_model": cfg.vision_model,
    }
    for key, value in overrides.items():
        row = db.get(AppSetting, key)
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=key, value=value))


def _load_agent_config(db: Session) -> AgentRuntimeConfig:
    env = get_settings()
    keys = ["agent_runtime", "openclaw_endpoint", "openclaw_api_key", "openclaw_agent"]
    db_vals = {}
    for row in db.query(AppSetting).filter(AppSetting.key.in_(keys)).all():
        db_vals[row.key] = row.value
    return AgentRuntimeConfig(
        runtime=db_vals.get("agent_runtime") or env.agent_runtime,
        endpoint=db_vals.get("openclaw_endpoint") or env.openclaw_endpoint or "",
        api_key=db_vals.get("openclaw_api_key") or env.openclaw_api_key or "",
        agent=db_vals.get("openclaw_agent") or env.openclaw_agent,
    )


def _save_agent_config(db: Session, cfg: AgentRuntimeConfig) -> None:
    if cfg.runtime == "openclaw":
        endpoint = cfg.endpoint.strip()
        if endpoint and not endpoint.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="OpenClaw Endpoint 必须是完整 URL，例如 http://127.0.0.1:3000/api/agent/run；留空则使用本机 openclaw CLI")
    overrides = {
        "agent_runtime": cfg.runtime,
        "openclaw_endpoint": cfg.endpoint.strip(),
        "openclaw_api_key": cfg.api_key,
        "openclaw_agent": cfg.agent,
    }
    for key, value in overrides.items():
        row = db.get(AppSetting, key)
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=key, value=value))


def _redact_error(message: str, *secrets: str) -> str:
    redacted = message
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted[:600]


def _is_validation_probe_blocked(message: str) -> bool:
    normalized = message.lower()
    markers = (
        "your request was blocked",
        "request was blocked",
        "content filter",
        "content_filter",
        "content policy",
        "policy violation",
        "blocked by policy",
        "moderation",
    )
    return any(marker in normalized for marker in markers)


def _test_model_config(cfg: ModelConfig) -> SettingsTestResponse:
    api_key = cfg.api_key.strip()
    model = cfg.model.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 为空，无法验证模型")
    if not model:
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    started = time.perf_counter()
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=cfg.base_url.strip() or None, timeout=30.0)
        models = client.models.list()
        model_ids = [item.id for item in getattr(models, "data", []) if getattr(item, "id", "")]
        latency_ms = int((time.perf_counter() - started) * 1000)
        if model_ids and model not in model_ids:
            return SettingsTestResponse(ok=True, message=f"API 连接可用；模型列表未返回 {model}，请确认模型名由服务商支持", latency_ms=latency_ms)
        return SettingsTestResponse(ok=True, message=f"API 连接可用，{model} 可用于请求", latency_ms=latency_ms)
    except Exception as list_exc:
        list_error = _redact_error(str(list_exc), api_key)
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=cfg.base_url.strip() or None, timeout=30.0)
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=8,
        )
        answer = (completion.choices[0].message.content or "").strip()
    except Exception as exc:
        detail = _redact_error(str(exc), api_key)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if _is_validation_probe_blocked(detail):
            return SettingsTestResponse(
                ok=True,
                level="warning",
                message=f"API 已连接到模型服务，但验证探针被服务商策略拦截；请用实际问答确认 {model}",
                latency_ms=latency_ms,
            )
        raise HTTPException(status_code=400, detail=f"模型验证失败：{detail}；模型列表检查也失败：{list_error}") from exc
    latency_ms = int((time.perf_counter() - started) * 1000)
    suffix = f"，返回：{answer[:40]}" if answer else ""
    return SettingsTestResponse(ok=True, message=f"{model} 可用{suffix}", latency_ms=latency_ms)


def _test_agent_config(cfg: AgentRuntimeConfig) -> SettingsTestResponse:
    if cfg.runtime != "openclaw":
        return SettingsTestResponse(ok=True, message="本地兼容模式可用；实际回答能力取决于 Chat 模型配置")
    endpoint = cfg.endpoint.strip()
    if endpoint and not endpoint.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="OpenClaw Endpoint 必须是完整 URL；留空则使用本机 openclaw CLI")
    started = time.perf_counter()
    runtime = {
        "runtime": cfg.runtime,
        "endpoint": endpoint,
        "api_key": cfg.api_key,
        "agent": cfg.agent.strip() or "main",
    }
    payload = {
        "agent": runtime["agent"],
        "project": "default",
        "session_id": "settings-test",
        "goal": "只回答 OK",
        "history": "无",
        "context": {},
        "tool_calls": [],
        "references": [],
        "policy": {"source": "SmartOpsDocs settings test", "dry_run_enforced": True},
    }
    try:
        from app.services.agent_service import _call_openclaw_cli, _call_openclaw_endpoint

        _call_openclaw_endpoint(runtime, payload) if endpoint else _call_openclaw_cli(runtime, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="OpenClaw 验证失败：" + _redact_error(str(exc), cfg.api_key)) from exc
    latency_ms = int((time.perf_counter() - started) * 1000)
    return SettingsTestResponse(ok=True, message=f"OpenClaw Agent {runtime['agent']} 可用", latency_ms=latency_ms)


@router.get("/settings", response_model=SettingsResponse)
def get_settings_api(db: Session = Depends(get_db), _: User = Depends(current_user)):
    env = get_settings()
    return SettingsResponse(
        chat=_load_config(db, "chat", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model}),
        optimize=_load_config(db, "optimize", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model, "vision_model": env.openai_vision_model or ""}),
        pull=_load_config(db, "pull", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model}),
        agent=_load_agent_config(db),
    )


@router.post("/settings/test", response_model=SettingsTestResponse)
def test_settings_api(payload: SettingsTestRequest, _: User = Depends(current_user)):
    scope = payload.scope.strip()
    if scope in {"chat", "optimize", "pull"}:
        return _test_model_config(ModelConfig(**payload.config))
    if scope == "agent":
        return _test_agent_config(AgentRuntimeConfig(**payload.config))
    raise HTTPException(status_code=400, detail="未知配置类型")


@router.put("/settings", response_model=SettingsResponse)
def update_settings_api(payload: SettingsRequest, db: Session = Depends(get_db), _: User = Depends(current_user)):
    _save_config(db, "chat", payload.chat)
    _save_config(db, "optimize", payload.optimize)
    _save_config(db, "pull", payload.pull)
    _save_agent_config(db, payload.agent)
    db.commit()
    env = get_settings()
    return SettingsResponse(
        chat=_load_config(db, "chat", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model}),
        optimize=_load_config(db, "optimize", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model, "vision_model": env.openai_vision_model or ""}),
        pull=_load_config(db, "pull", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model}),
        agent=_load_agent_config(db),
    )
