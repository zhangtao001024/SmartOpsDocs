"""Docker 管理路由."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import ServerAsset, User
from app.services.docker_service import (
    container_action,
    get_logs,
    inspect_container,
    container_top,
    list_container_stats,
    list_containers,
    list_images,
    list_networks,
    list_volumes,
)

router = APIRouter(prefix="/api", tags=["docker"])


@router.get("/docker/{server_id}/containers")
def docker_containers(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    try:
        return list_containers(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/docker/{server_id}/containers/{container_id}/{action}")
def docker_action(server_id: int, container_id: str, action: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    try:
        return container_action(server, container_id, action)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/containers/{container_id}/logs")
def docker_logs(server_id: int, container_id: str, tail: int = 200, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    try:
        return {"logs": get_logs(server, container_id, tail)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/containers/{container_id}/inspect")
def docker_inspect(server_id: int, container_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    try:
        return inspect_container(server, container_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/containers/{container_id}/top")
def docker_container_top(server_id: int, container_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    try:
        return container_top(server, container_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/images")
def docker_images(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    try:
        return list_images(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/networks")
def docker_networks(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    try:
        return list_networks(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/volumes")
def docker_volumes(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    try:
        return list_volumes(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/containers/stats")
def docker_container_stats(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    try:
        return list_container_stats(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
