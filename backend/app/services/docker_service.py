import json
import re
import shlex

from app.models.entities import ServerAsset
from app.services.ssh_service import run_command

CONTAINER_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")


def _container_ref(value: str) -> str:
    if not CONTAINER_REF_RE.fullmatch(value):
        raise ValueError("容器标识不合法")
    return shlex.quote(value)


def _tail(value: int, default: int = 200, maximum: int = 5000) -> int:
    try:
        tail = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(tail, 1), maximum)


def list_containers(server: ServerAsset) -> list[dict]:
    fmt = "{{json .}}"
    result = run_command(server, f"docker ps -a --format '{fmt}'")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker ps 执行失败")
    containers = []
    for line in result["stdout"].splitlines():
        if line.strip():
            item = json.loads(line)
            containers.append(
                {
                    "id": item.get("ID"),
                    "name": item.get("Names"),
                    "image": item.get("Image"),
                    "status": item.get("Status"),
                    "ports": item.get("Ports"),
                }
            )
    return containers


def container_action(server: ServerAsset, container_id: str, action: str) -> dict:
    if action not in {"start", "stop", "restart"}:
        raise ValueError("不支持的容器操作")
    return run_command(server, f"docker {action} {_container_ref(container_id)}")


def get_logs(server: ServerAsset, container_id: str, tail: int = 200) -> str:
    result = run_command(server, f"docker logs --tail {_tail(tail)} {_container_ref(container_id)}")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker logs 执行失败")
    return result["stdout"]


def inspect_container(server: ServerAsset, container_id: str) -> dict:
    result = run_command(server, f"docker inspect {_container_ref(container_id)}")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker inspect 执行失败")
    data = json.loads(result["stdout"] or "[]")
    if not data:
        raise RuntimeError("容器不存在")
    item = data[0]
    state = item.get("State") or {}
    config = item.get("Config") or {}
    host_config = item.get("HostConfig") or {}
    network_settings = item.get("NetworkSettings") or {}
    return {
        "id": item.get("Id"),
        "name": (item.get("Name") or "").lstrip("/"),
        "image": config.get("Image"),
        "created": item.get("Created"),
        "state": {
            "status": state.get("Status"),
            "running": state.get("Running"),
            "started_at": state.get("StartedAt"),
            "finished_at": state.get("FinishedAt"),
            "exit_code": state.get("ExitCode"),
            "error": state.get("Error"),
        },
        "restart_policy": host_config.get("RestartPolicy"),
        "ports": network_settings.get("Ports"),
        "mounts": item.get("Mounts") or [],
        "env": config.get("Env") or [],
        "command": config.get("Cmd") or [],
        "entrypoint": config.get("Entrypoint") or [],
    }


def list_images(server: ServerAsset) -> list[dict]:
    result = run_command(server, "docker images --format '{{json .}}'")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker images 执行失败")
    images = []
    for line in result["stdout"].splitlines():
        if line.strip():
            item = json.loads(line)
            images.append({
                "repository": item.get("Repository"),
                "tag": item.get("Tag"),
                "image_id": item.get("ID"),
                "size": item.get("Size"),
                "created": item.get("CreatedSince") or item.get("CreatedAt", ""),
            })
    return images


def list_networks(server: ServerAsset) -> list[dict]:
    result = run_command(server, "docker network ls --format '{{json .}}'")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker network ls 执行失败")
    networks = []
    for line in result["stdout"].splitlines():
        if line.strip():
            item = json.loads(line)
            networks.append({
                "id": item.get("ID"),
                "name": item.get("Name"),
                "driver": item.get("Driver"),
                "scope": item.get("Scope"),
                "ipv6": item.get("IPv6", ""),
                "internal": item.get("Internal", ""),
            })
    return networks


def list_volumes(server: ServerAsset) -> list[dict]:
    result = run_command(server, "docker volume ls --format '{{json .}}'")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker volume ls 执行失败")
    volumes = []
    for line in result["stdout"].splitlines():
        if line.strip():
            item = json.loads(line)
            volumes.append({
                "name": item.get("Name"),
                "driver": item.get("Driver"),
                "scope": item.get("Scope", ""),
                "mountpoint": item.get("Mountpoint", ""),
            })
    return volumes


def container_top(server: ServerAsset, container_id: str) -> dict:
    result = run_command(server, f"docker top {_container_ref(container_id)}")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker top 执行失败")
    lines = [line for line in result["stdout"].splitlines() if line.strip()]
    return {
        "header": lines[0] if lines else "",
        "rows": lines[1:],
        "raw": result["stdout"],
    }


def list_container_stats(server: ServerAsset) -> list[dict]:
    fmt = "{{json .}}"
    result = run_command(server, f"docker stats --no-stream --format '{fmt}'")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker stats 执行失败")
    stats = []
    for line in result["stdout"].splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        stats.append(
            {
                "id": item.get("ID"),
                "name": item.get("Name"),
                "cpu": item.get("CPUPerc"),
                "memory": item.get("MemUsage"),
                "memory_percent": item.get("MemPerc"),
                "net_io": item.get("NetIO"),
                "block_io": item.get("BlockIO"),
                "pids": item.get("PIDs"),
            }
        )
    return stats
