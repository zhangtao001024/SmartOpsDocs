"""系统设置路由."""

from fastapi import APIRouter, Depends
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


class SettingsRequest(BaseModel):
    chat: ModelConfig = ModelConfig()
    optimize: ModelConfig = ModelConfig()
    pull: ModelConfig = ModelConfig()


class SettingsResponse(BaseModel):
    chat: ModelConfig
    optimize: ModelConfig
    pull: ModelConfig


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


@router.get("/settings", response_model=SettingsResponse)
def get_settings_api(db: Session = Depends(get_db), _: User = Depends(current_user)):
    env = get_settings()
    return SettingsResponse(
        chat=_load_config(db, "chat", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model}),
        optimize=_load_config(db, "optimize", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model, "vision_model": env.openai_vision_model or ""}),
        pull=_load_config(db, "pull", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model}),
    )


@router.put("/settings", response_model=SettingsResponse)
def update_settings_api(payload: SettingsRequest, db: Session = Depends(get_db), _: User = Depends(current_user)):
    _save_config(db, "chat", payload.chat)
    _save_config(db, "optimize", payload.optimize)
    _save_config(db, "pull", payload.pull)
    db.commit()
    env = get_settings()
    return SettingsResponse(
        chat=_load_config(db, "chat", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model}),
        optimize=_load_config(db, "optimize", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model, "vision_model": env.openai_vision_model or ""}),
        pull=_load_config(db, "pull", {"api_key": env.openai_api_key or "", "base_url": env.openai_base_url or "", "model": env.openai_model}),
    )
