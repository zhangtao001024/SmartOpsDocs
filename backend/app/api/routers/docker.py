"""Docker 管理路由."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import SessionLocal, get_db
from app.core.security import decode_access_token
from app.models.entities import ServerAsset, User
from app.services.docker_service import (
    compose_action,
    container_action,
    container_shell_command,
    delete_container_path,
    discover_compose_project,
    docker_dashboard,
    get_logs,
    inspect_network,
    inspect_container,
    inspect_volume,
    container_top,
    list_container_stats,
    list_containers,
    list_container_files,
    list_images,
    list_networks,
    list_volumes,
    mkdir_container_path,
    prune_docker,
    pull_image,
    read_compose_file,
    read_container_file,
    remove_image,
    write_compose_file,
    write_container_file,
)
from app.services.ssh_service import create_command_shell

router = APIRouter(prefix="/api", tags=["docker"])


class DockerImageRequest(BaseModel):
    image: str
    force: bool = False


class DockerFileReadRequest(BaseModel):
    path: str
    max_bytes: int = 1024 * 1024


class DockerFileWriteRequest(BaseModel):
    path: str
    content: str


class DockerPathRequest(BaseModel):
    path: str


class ComposeFileWriteRequest(BaseModel):
    path: str
    content: str


class ComposeActionRequest(BaseModel):
    working_dir: str = ""
    config_files: list[str]
    action: str
    tail: int = 200


def _server(db: Session, server_id: int) -> ServerAsset:
    server = db.get(ServerAsset, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    return server


@router.get("/docker/{server_id}/dashboard")
def docker_server_dashboard(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return docker_dashboard(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/containers")
def docker_containers(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return list_containers(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/containers/{container_id}/files")
def docker_container_files(
    server_id: int,
    container_id: str,
    path: str = Query("/", min_length=1),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = _server(db, server_id)
    try:
        return list_container_files(server, container_id, path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/docker/{server_id}/containers/{container_id}/files/read")
def docker_container_file_read(
    server_id: int,
    container_id: str,
    payload: DockerFileReadRequest,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = _server(db, server_id)
    try:
        return read_container_file(server, container_id, payload.path, payload.max_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/docker/{server_id}/containers/{container_id}/files")
def docker_container_file_write(
    server_id: int,
    container_id: str,
    payload: DockerFileWriteRequest,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = _server(db, server_id)
    try:
        return write_container_file(server, container_id, payload.path, payload.content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/docker/{server_id}/containers/{container_id}/directories")
def docker_container_directory_create(
    server_id: int,
    container_id: str,
    payload: DockerPathRequest,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = _server(db, server_id)
    try:
        return mkdir_container_path(server, container_id, payload.path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/docker/{server_id}/containers/{container_id}/files")
def docker_container_file_delete(
    server_id: int,
    container_id: str,
    path: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = _server(db, server_id)
    try:
        return delete_container_path(server, container_id, path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/containers/{container_id}/compose")
def docker_container_compose(
    server_id: int,
    container_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = _server(db, server_id)
    try:
        return discover_compose_project(server, container_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/docker/{server_id}/containers/{container_id}/{action}")
def docker_action(server_id: int, container_id: str, action: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return container_action(server, container_id, action)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/containers/{container_id}/logs")
def docker_logs(server_id: int, container_id: str, tail: int = 200, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return {"logs": get_logs(server, container_id, tail)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/containers/{container_id}/inspect")
def docker_inspect(server_id: int, container_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return inspect_container(server, container_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/containers/{container_id}/top")
def docker_container_top(server_id: int, container_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return container_top(server, container_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/images")
def docker_images(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return list_images(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/docker/{server_id}/images/pull")
def docker_image_pull(
    server_id: int,
    payload: DockerImageRequest,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = _server(db, server_id)
    try:
        return pull_image(server, payload.image)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/docker/{server_id}/images")
def docker_image_remove(
    server_id: int,
    image: str = Query(..., min_length=1),
    force: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = _server(db, server_id)
    try:
        return remove_image(server, image, force)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/networks")
def docker_networks(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return list_networks(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/networks/{name}/inspect")
def docker_network_inspect(server_id: int, name: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return inspect_network(server, name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/volumes")
def docker_volumes(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return list_volumes(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/volumes/{name}/inspect")
def docker_volume_inspect(server_id: int, name: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return inspect_volume(server, name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/containers/stats")
def docker_container_stats(server_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return list_container_stats(server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/docker/{server_id}/compose/file")
def docker_compose_file(
    server_id: int,
    path: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = _server(db, server_id)
    try:
        return read_compose_file(server, path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/docker/{server_id}/compose/file")
def docker_compose_file_write(
    server_id: int,
    payload: ComposeFileWriteRequest,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = _server(db, server_id)
    try:
        return write_compose_file(server, payload.path, payload.content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/docker/{server_id}/compose/action")
def docker_compose_action(
    server_id: int,
    payload: ComposeActionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    server = _server(db, server_id)
    try:
        return compose_action(server, payload.working_dir, payload.config_files, payload.action, payload.tail)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/docker/{server_id}/prune/{target}")
def docker_prune(server_id: int, target: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    server = _server(db, server_id)
    try:
        return prune_docker(server, target)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.websocket("/docker/{server_id}/containers/{container_id}/shell")
async def docker_container_shell(websocket: WebSocket, server_id: int, container_id: str, shell: str = "auto"):
    await websocket.accept()
    try:
        msg = await asyncio.wait_for(websocket.receive_text(), timeout=5)
        if not msg.startswith("auth:"):
            await websocket.close(code=4001)
            return
        decode_access_token(msg[5:])
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

        try:
            command = container_shell_command(container_id, shell)
            client, channel = create_command_shell(server, command)
        except Exception as exc:
            await websocket.send_text(f"shell:error:{exc}")
            await websocket.close(code=1011)
            return
        await websocket.send_text("shell:ready")

        async def reader():
            while not channel.closed:
                if channel.recv_ready():
                    data = await loop.run_in_executor(None, channel.recv, 4096)
                    if data:
                        await websocket.send_bytes(data)
                if channel.exit_status_ready():
                    break
                await asyncio.sleep(0.02)
            while not channel.closed and channel.recv_ready():
                data = await loop.run_in_executor(None, channel.recv, 4096)
                if data:
                    await websocket.send_bytes(data)
            if channel.exit_status_ready():
                code = await loop.run_in_executor(None, channel.recv_exit_status)
                await websocket.send_text(f"shell:exit:{code}")

        async def writer():
            while not channel.closed:
                try:
                    data = await websocket.receive_bytes()
                    await loop.run_in_executor(None, channel.send, data)
                except WebSocketDisconnect:
                    break

        tasks = [asyncio.create_task(reader()), asyncio.create_task(writer())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*done, return_exceptions=True)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
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
