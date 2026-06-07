import json
import posixpath
import re
import shlex
from uuid import uuid4

from app.models.entities import ServerAsset
from app.services.ssh_service import read_remote_file, run_command, write_remote_file

CONTAINER_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")
IMAGE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/+~-]{0,255}$")
DOCKER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$")
SHELLS = {"auto", "/bin/bash", "/bin/sh", "/bin/ash", "/usr/bin/bash", "/usr/bin/sh", "bash", "sh", "ash"}
COMPOSE_FILE_NAMES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")


def _container_ref(value: str) -> str:
    if not CONTAINER_REF_RE.fullmatch(value):
        raise ValueError("容器标识不合法")
    return shlex.quote(value)


def _image_ref(value: str) -> str:
    if not IMAGE_REF_RE.fullmatch(value):
        raise ValueError("镜像标识不合法")
    return shlex.quote(value)


def _docker_name(value: str) -> str:
    if not DOCKER_NAME_RE.fullmatch(value):
        raise ValueError("Docker 资源名称不合法")
    return shlex.quote(value)


def _container_path(value: str | None, default: str = "/") -> str:
    path = (value or default).strip() or default
    if "\x00" in path or len(path) > 4096:
        raise ValueError("容器路径不合法")
    return path


def _compose_path(value: str) -> str:
    path = (value or "").strip()
    if not path or "\x00" in path or len(path) > 4096:
        raise ValueError("Compose 路径不合法")
    return path


def _tail(value: int, default: int = 200, maximum: int = 5000) -> int:
    try:
        tail = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(tail, 1), maximum)


def docker_dashboard(server: ServerAsset) -> dict:
    version = run_command(server, "docker version --format '{{json .}}'", timeout=20)
    info = run_command(server, "docker info --format '{{json .}}'", timeout=20)
    disk = run_command(server, "docker system df --format '{{json .}}'", timeout=20)
    if version["exit_code"] != 0:
        raise RuntimeError(version["stderr"] or "docker version 执行失败")
    disk_rows = []
    for line in disk["stdout"].splitlines():
        if line.strip():
            disk_rows.append(json.loads(line))
    return {
        "version": json.loads(version["stdout"] or "{}"),
        "info": json.loads(info["stdout"] or "{}") if info["exit_code"] == 0 else {"error": info["stderr"]},
        "disk": disk_rows,
    }


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
    if action not in {"start", "stop", "restart", "pause", "unpause", "kill"}:
        raise ValueError("不支持的容器操作")
    return run_command(server, f"docker {action} {_container_ref(container_id)}")


def container_shell_command(container_id: str, shell: str = "/bin/sh") -> str:
    if shell not in SHELLS:
        raise ValueError("不支持的容器 Shell")
    ref = _container_ref(container_id)
    if shell == "auto":
        return (
            "for smartops_shell in /bin/bash /bin/sh /bin/ash; do "
            f"if docker exec {ref} \"$smartops_shell\" -c 'exit 0' >/dev/null 2>&1; then "
            f"exec docker exec -it {ref} \"$smartops_shell\"; "
            "fi; "
            "done; "
            "echo '容器内未找到可用 Shell（/bin/bash、/bin/sh、/bin/ash）' >&2; exit 127"
        )
    return f"docker exec -it {ref} {shlex.quote(shell)}"


def get_logs(server: ServerAsset, container_id: str, tail: int = 200) -> str:
    result = run_command(server, f"docker logs --tail {_tail(tail)} {_container_ref(container_id)}")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker logs 执行失败")
    return result["stdout"]


def inspect_container(server: ServerAsset, container_id: str) -> dict:
    item = inspect_container_raw(server, container_id)
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
        "labels": config.get("Labels") or {},
    }


def inspect_container_raw(server: ServerAsset, container_id: str) -> dict:
    result = run_command(server, f"docker inspect {_container_ref(container_id)}")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker inspect 执行失败")
    data = json.loads(result["stdout"] or "[]")
    if not data:
        raise RuntimeError("容器不存在")
    return data[0]


def _container_exec(server: ServerAsset, container_id: str, script: str, args: list[str] | None = None, timeout: int = 30) -> dict:
    ref = _container_ref(container_id)
    quoted_script = shlex.quote(script)
    quoted_args = " ".join(shlex.quote(str(arg)) for arg in (args or []))
    shells = ["/bin/sh", "/bin/ash", "/bin/bash"]
    tests = " ".join(
        f"if docker exec {ref} {shell} -c 'true' >/dev/null 2>&1; then "
        f"docker exec {ref} {shell} -c {quoted_script} smartopsdocs {quoted_args}; exit $?; fi;"
        for shell in shells
    )
    command = f"{tests} echo '容器内未找到 /bin/sh、/bin/ash 或 /bin/bash，无法执行该操作' >&2; exit 127"
    return run_command(server, command, timeout=timeout)


def list_container_files(server: ServerAsset, container_id: str, path: str = "/") -> dict:
    target = _container_path(path)
    script = r'''
p="$1"
[ -d "$p" ] || { echo "不是目录: $p" >&2; exit 2; }
for f in "$p"/* "$p"/.[!.]* "$p"/..?*; do
  [ -e "$f" ] || continue
  name=${f##*/}
  type=file
  [ -d "$f" ] && type=directory
  [ -L "$f" ] && type=link
  size=$(wc -c < "$f" 2>/dev/null || printf 0)
  mtime=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || printf 0)
  perm=$(ls -ld "$f" 2>/dev/null | awk '{print $1}')
  printf '%s\t%s\t%s\t%s\t%s\n' "$type" "$size" "$mtime" "$perm" "$name"
done
'''
    result = _container_exec(server, container_id, script, [target], timeout=30)
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "容器目录读取失败")
    files = []
    for line in result["stdout"].splitlines():
        parts = line.split("\t", 4)
        if len(parts) != 5:
            continue
        file_type, size, mtime, permissions, name = parts
        files.append(
            {
                "name": name,
                "path": posixpath.join(target.rstrip("/") or "/", name),
                "type": file_type,
                "size": int(size.strip() or 0) if size.strip().isdigit() else 0,
                "mtime": int(mtime.strip() or 0) if mtime.strip().isdigit() else 0,
                "permissions": permissions,
            }
        )
    files.sort(key=lambda item: (item["type"] != "directory", item["name"].lower()))
    return {"path": target, "parent": posixpath.dirname(target.rstrip("/")) or "/", "files": files}


def read_container_file(server: ServerAsset, container_id: str, path: str, max_bytes: int = 1024 * 1024) -> dict:
    target = _container_path(path)
    limit = min(max(int(max_bytes or 0), 1024), 5 * 1024 * 1024)
    script = 'p="$1"; limit="$2"; [ -f "$p" ] || { echo "不是普通文件: $p" >&2; exit 2; }; head -c "$limit" "$p"'
    result = _container_exec(server, container_id, script, [target, str(limit)], timeout=30)
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "容器文件读取失败")
    content = result["stdout"]
    return {"path": target, "content": content, "truncated": len(content.encode("utf-8")) >= limit, "bytes": len(content.encode("utf-8"))}


def write_container_file(server: ServerAsset, container_id: str, path: str, content: str) -> dict:
    target = _container_path(path)
    tmp_path = f"/tmp/smartopsdocs-container-file-{uuid4().hex}"
    write_remote_file(server, tmp_path, content)
    try:
        cp_result = run_command(server, f"docker cp {shlex.quote(tmp_path)} {_container_ref(container_id)}:{shlex.quote(target)}", timeout=60)
        if cp_result["exit_code"] != 0:
            raise RuntimeError(cp_result["stderr"] or "容器文件保存失败")
        return {"ok": True, "path": target, "bytes": len(content.encode("utf-8"))}
    finally:
        run_command(server, f"rm -f {shlex.quote(tmp_path)}", timeout=10)


def mkdir_container_path(server: ServerAsset, container_id: str, path: str) -> dict:
    target = _container_path(path)
    result = _container_exec(server, container_id, 'mkdir -p "$1"', [target], timeout=30)
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "容器目录创建失败")
    return {"ok": True, "path": target}


def delete_container_path(server: ServerAsset, container_id: str, path: str) -> dict:
    target = _container_path(path)
    script = 'p="$1"; [ "$p" = "/" ] && { echo "不能删除根目录" >&2; exit 2; }; if [ -d "$p" ]; then rmdir "$p"; else rm -f "$p"; fi'
    result = _container_exec(server, container_id, script, [target], timeout=30)
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "容器路径删除失败")
    return {"ok": True, "path": target}


def _compose_file_candidates(item: dict) -> list[str]:
    labels = (item.get("Config") or {}).get("Labels") or {}
    working_dir = labels.get("com.docker.compose.project.working_dir") or ""
    raw_files = labels.get("com.docker.compose.project.config_files") or ""
    candidates: list[str] = []
    for raw in raw_files.split(","):
        value = raw.strip()
        if not value:
            continue
        if value.startswith("/"):
            candidates.append(value)
        elif working_dir:
            candidates.append(posixpath.join(working_dir, value))
    for name in COMPOSE_FILE_NAMES:
        if working_dir:
            candidates.append(posixpath.join(working_dir, name))
    mounts = item.get("Mounts") or []
    for mount in mounts:
        source = mount.get("Source") or ""
        if posixpath.basename(source) in COMPOSE_FILE_NAMES:
            candidates.append(source)
    return list(dict.fromkeys(candidates))


def discover_compose_project(server: ServerAsset, container_id: str) -> dict:
    item = inspect_container_raw(server, container_id)
    labels = (item.get("Config") or {}).get("Labels") or {}
    project = labels.get("com.docker.compose.project") or ""
    service = labels.get("com.docker.compose.service") or ""
    working_dir = labels.get("com.docker.compose.project.working_dir") or ""
    candidates = _compose_file_candidates(item)
    existing_files = []
    for path in candidates:
        result = run_command(server, f"test -f {shlex.quote(path)} && echo ok || true", timeout=10)
        if result["stdout"].strip() == "ok":
            existing_files.append(path)

    containers = []
    if project:
        project_filter = shlex.quote("label=com.docker.compose.project=" + project)
        result = run_command(
            server,
            f"docker ps -a --filter {project_filter} --format '{{{{json .}}}}'",
            timeout=20,
        )
        if result["exit_code"] == 0:
            for line in result["stdout"].splitlines():
                if line.strip():
                    row = json.loads(line)
                    containers.append(
                        {
                            "id": row.get("ID"),
                            "name": row.get("Names"),
                            "image": row.get("Image"),
                            "status": row.get("Status"),
                            "ports": row.get("Ports"),
                        }
                    )

    return {
        "project": project,
        "service": service,
        "working_dir": working_dir or (posixpath.dirname(existing_files[0]) if existing_files else ""),
        "config_files": existing_files,
        "candidates": candidates,
        "labels": labels,
        "containers": containers,
        "detected": bool(project or existing_files),
    }


def read_compose_file(server: ServerAsset, path: str) -> dict:
    target = _compose_path(path)
    data = read_remote_file(server, target, max_bytes=5 * 1024 * 1024)
    return data


def write_compose_file(server: ServerAsset, path: str, content: str) -> dict:
    target = _compose_path(path)
    if posixpath.basename(target) not in COMPOSE_FILE_NAMES and not target.endswith((".yml", ".yaml")):
        raise ValueError("只允许保存 YAML 文件")
    return write_remote_file(server, target, content)


def _compose_command(working_dir: str, config_files: list[str], args: str) -> str:
    files = [_compose_path(path) for path in config_files if path]
    if not files:
        raise ValueError("缺少 Compose YAML 文件路径")
    flags = " ".join(f"-f {shlex.quote(path)}" for path in files)
    cd = f"cd {shlex.quote(working_dir)} && " if working_dir else ""
    args = args.strip()
    return (
        f"{cd}"
        f"if docker compose version >/dev/null 2>&1; then docker compose {flags} {args}; "
        f"elif command -v docker-compose >/dev/null 2>&1; then docker-compose {flags} {args}; "
        f"else echo '未安装 docker compose 或 docker-compose' >&2; exit 127; fi"
    )


def compose_action(server: ServerAsset, working_dir: str, config_files: list[str], action: str, tail: int = 200) -> dict:
    actions = {
        "ps": "ps",
        "config": "config",
        "logs": f"logs --tail {_tail(tail)}",
        "restart": "restart",
        "up": "up -d",
        "down": "down",
        "pull": "pull",
        "stop": "stop",
        "start": "start",
    }
    compose_args = actions.get(action)
    if not compose_args:
        raise ValueError("不支持的 Compose 操作")
    timeout = 180 if action in {"up", "pull"} else 90
    return run_command(server, _compose_command(working_dir, config_files, compose_args), timeout=timeout)


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


def pull_image(server: ServerAsset, image: str) -> dict:
    return run_command(server, f"docker pull {_image_ref(image)}", timeout=180)


def remove_image(server: ServerAsset, image: str, force: bool = False) -> dict:
    flag = " -f" if force else ""
    return run_command(server, f"docker rmi{flag} {_image_ref(image)}", timeout=60)


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


def inspect_network(server: ServerAsset, name: str) -> dict:
    result = run_command(server, f"docker network inspect {_docker_name(name)}")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker network inspect 执行失败")
    data = json.loads(result["stdout"] or "[]")
    return data[0] if data else {}


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


def inspect_volume(server: ServerAsset, name: str) -> dict:
    result = run_command(server, f"docker volume inspect {_docker_name(name)}")
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or "docker volume inspect 执行失败")
    data = json.loads(result["stdout"] or "[]")
    return data[0] if data else {}


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


def prune_docker(server: ServerAsset, target: str) -> dict:
    commands = {
        "containers": "docker container prune -f",
        "images": "docker image prune -f",
        "volumes": "docker volume prune -f",
        "networks": "docker network prune -f",
        "system": "docker system prune -f",
    }
    command = commands.get(target)
    if not command:
        raise ValueError("不支持的清理类型")
    return run_command(server, command, timeout=120)
