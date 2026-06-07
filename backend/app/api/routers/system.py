"""系统状态与运行时信息路由."""

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import Document, DocumentChunk, DocumentTask, KubeCluster, ServerAsset, User

router = APIRouter(prefix="/api", tags=["system"])


def _path_status(path: Path) -> dict:
    resolved = path.resolve()
    exists = resolved.exists()
    probe = resolved if exists else resolved.parent
    can_create = not exists and resolved.parent.exists() and os.access(resolved.parent, os.W_OK)
    writable = os.access(probe, os.W_OK)
    ready = (exists and writable) or can_create
    return {
        "path": str(resolved),
        "exists": exists,
        "writable": writable,
        "can_create": can_create,
        "ready": ready,
    }


def _safe_count(label: str, query, issues: list[dict]) -> int:
    try:
        return query.count()
    except Exception as exc:
        issues.append({"scope": "counts", "name": label, "error": str(exc)})
        return 0


def collect_system_status(db: Session) -> dict:
    settings = get_settings()
    issues: list[dict] = []
    database_ok = True
    database_error = ""
    try:
        db.execute(text("select 1"))
    except Exception as exc:
        database_ok = False
        database_error = str(exc)
        issues.append({"scope": "database", "name": "connection", "error": database_error})

    upload = _path_status(settings.upload_dir)
    knowledge = _path_status(settings.knowledge_dir)
    storage_ok = upload["ready"] and knowledge["ready"]
    if not upload["ready"]:
        issues.append({"scope": "storage", "name": "upload_dir", "error": "目录不存在或不可写"})
    if not knowledge["ready"]:
        issues.append({"scope": "storage", "name": "knowledge_dir", "error": "目录不存在或不可写"})

    counts = {
        "servers": 0,
        "servers_online": 0,
        "clusters": 0,
        "documents": 0,
        "documents_parsing": 0,
        "documents_failed": 0,
        "chunks": 0,
        "tasks_active": 0,
    }
    if database_ok:
        counts = {
            "servers": _safe_count("servers", db.query(ServerAsset), issues),
            "servers_online": _safe_count("servers_online", db.query(ServerAsset).filter(ServerAsset.status == "online"), issues),
            "clusters": _safe_count("clusters", db.query(KubeCluster), issues),
            "documents": _safe_count("documents", db.query(Document), issues),
            "documents_parsing": _safe_count(
                "documents_parsing",
                db.query(Document).filter(Document.status.in_(["uploaded", "parsing"])),
                issues,
            ),
            "documents_failed": _safe_count("documents_failed", db.query(Document).filter(Document.status == "failed"), issues),
            "chunks": _safe_count("chunks", db.query(DocumentChunk), issues),
            "tasks_active": _safe_count(
                "tasks_active",
                db.query(DocumentTask).filter(DocumentTask.status.in_(["queued", "running"])),
                issues,
            ),
        }

    return {
        "status": "ok" if database_ok and storage_ok and not issues else "degraded",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "api": {"ok": True},
        "database": {
            "ok": database_ok,
            "driver": settings.database_url.split(":", 1)[0],
            "error": database_error,
        },
        "storage": {
            "upload_dir": upload,
            "knowledge_dir": knowledge,
        },
        "counts": counts,
        "issues": issues,
    }


def collect_health_status(db: Session) -> dict:
    settings = get_settings()
    issues: list[dict] = []
    database_ok = True
    database_error = ""
    try:
        db.execute(text("select 1"))
    except Exception as exc:
        database_ok = False
        database_error = str(exc)
        issues.append({"scope": "database", "name": "connection", "error": database_error})

    upload = _path_status(settings.upload_dir)
    knowledge = _path_status(settings.knowledge_dir)
    storage_ok = upload["ready"] and knowledge["ready"]
    if not upload["ready"]:
        issues.append({"scope": "storage", "name": "upload_dir", "error": "目录不存在或不可写"})
    if not knowledge["ready"]:
        issues.append({"scope": "storage", "name": "knowledge_dir", "error": "目录不存在或不可写"})

    return {
        "ok": database_ok and storage_ok and not issues,
        "status": "ok" if database_ok and storage_ok and not issues else "degraded",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "database": {"ok": database_ok, "driver": settings.database_url.split(":", 1)[0]},
        "storage": {"ok": storage_ok},
        "issues": issues,
    }


@router.get("/system/status")
def system_status(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return collect_system_status(db)
