"""服务器资产管理路由."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.entities import Document, DocumentChunk, KubeCluster, ServerAsset, User
from app.schemas.dto import ServerCommandRequest, ServerCreate, ServerOut, ServerTestSchema, ServerUpdate
from app.services.ssh_service import create_shell, run_command, server_overview, test_connection

router = APIRouter(prefix="/api", tags=["servers"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return {
        "servers": db.query(ServerAsset).count(),
        "servers_online": db.query(ServerAsset).filter(ServerAsset.status == "online").count(),
        "clusters": db.query(KubeCluster).count(),
        "documents": db.query(Document).count(),
        "documents_parsing": db.query(Document).filter(Document.status.in_(["uploaded", "parsing"])).count(),
        "documents_failed": db.query(Document).filter(Document.status == "failed").count(),
        "chunks": db.query(DocumentChunk).count(),
    }


@router.get("/servers", response_model=list[ServerOut])
def servers(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return db.query(ServerAsset).order_by(ServerAsset.id.desc()).all()


@router.post("/servers", response_model=ServerOut)
def create_server(payload: ServerCreate, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = ServerAsset(**payload.model_dump())
    db.add(server)
    db.commit()
    db.refresh(server)
    return server


@router.put("/servers/{server_id}", response_model=ServerOut)
def update_server(server_id: int, payload: ServerUpdate, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    update_data = payload.model_dump(exclude_unset=True)
    for secret_field in ("ssh_password", "ssh_private_key"):
        if update_data.get(secret_field) == "":
            update_data.pop(secret_field)
    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")
    for key, value in update_data.items():
        setattr(server, key, value)
    db.commit()
    db.refresh(server)
    return server


@router.delete("/servers/{server_id}")
def delete_server(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    db.delete(server)
    db.commit()
    return {"ok": True}


@router.post("/servers/test-connection")
def test_server_connection(payload: ServerTestSchema, db: Session = Depends(get_db), _: User = Depends(current_user)):
    data = payload.model_dump()
    server_id = data.pop("server_id", None)
    existing = db.get(ServerAsset, server_id) if server_id is not None else None
    if existing:
        if not data.get("ssh_password"):
            data["ssh_password"] = existing.ssh_password
        if not data.get("ssh_private_key"):
            data["ssh_private_key"] = existing.ssh_private_key
    data.setdefault("project", "default")
    data.setdefault("environment", "dev")
    data.setdefault("tags", "")
    server = ServerAsset(**data)
    try:
        result = test_connection(server)
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}

    if existing:
        existing.status = "online" if result["ok"] else "offline"
        db.commit()
    return result


@router.get("/servers/{server_id}/overview")
def server_asset_overview(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    try:
        return server_overview(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/servers/{server_id}/command")
def server_asset_command(
    server_id: int,
    payload: ServerCommandRequest,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    command = payload.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="命令不能为空")
    timeout = min(max(payload.timeout, 1), 120)
    try:
        return run_command(server, command, timeout=timeout)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.websocket("/servers/{server_id}/ssh")
async def ssh_terminal(websocket: WebSocket, server_id: int):
    await websocket.accept()
    try:
        msg = await asyncio.wait_for(websocket.receive_text(), timeout=5)
        if not msg.startswith("auth:"):
            await websocket.close(code=4001)
            return
        token = msg[5:]
        decode_access_token(token)
    except Exception:
        await websocket.close(code=4001)
        return

    db = SessionLocal()
    client = None
    loop = asyncio.get_event_loop()
    try:
        server = db.get(ServerAsset, server_id)
        if not server:
            await websocket.close(code=4004)
            return

        client, channel = create_shell(server)
        await websocket.send_text("shell:ready")

        async def reader():
            while not channel.closed:
                if channel.recv_ready():
                    data = await loop.run_in_executor(None, channel.recv, 4096)
                    if data:
                        await websocket.send_bytes(data)
                await asyncio.sleep(0.02)

        async def writer():
            while True:
                try:
                    data = await websocket.receive_bytes()
                    await loop.run_in_executor(None, channel.send, data)
                except WebSocketDisconnect:
                    break

        await asyncio.gather(reader(), writer())
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        db.close()
        if client:
            try:
                client.close()
            except Exception:
                pass
