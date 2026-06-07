import io
import posixpath
import stat

import paramiko

from app.models.entities import ServerAsset


def _connect(server: ServerAsset) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: dict = {
        "hostname": server.ip,
        "port": server.ssh_port,
        "username": server.ssh_username,
        "timeout": 8,
    }
    if server.ssh_private_key:
        pkey = _load_private_key(server.ssh_private_key)
        kwargs["pkey"] = pkey
    else:
        kwargs["password"] = server.ssh_password
    client.connect(**kwargs)
    return client


def _load_private_key(key_text: str) -> paramiko.PKey:
    """尝试多种私钥格式，支持 RSA / Ed25519 / ECDSA."""
    errors: list[str] = []
    for cls_name, cls in [
        ("RSA", paramiko.RSAKey),
        ("Ed25519", paramiko.Ed25519Key),
        ("ECDSA", paramiko.ECDSAKey),
    ]:
        try:
            return cls.from_private_key(io.StringIO(key_text))
        except paramiko.SSHException as exc:
            errors.append(f"{cls_name}: {exc}")
    raise paramiko.SSHException(f"无法解析私钥（尝试了 {' / '.join(e.split(':')[0] for e in errors)}）")


def run_command(server: ServerAsset, command: str, timeout: int = 30) -> dict:
    client = _connect(server)
    try:
        stdin, stdout, stderr = client.exec_command(command, get_pty=False, timeout=timeout)
        code = stdout.channel.recv_exit_status()
        return {
            "exit_code": code,
            "stdout": stdout.read().decode("utf-8", errors="replace"),
            "stderr": stderr.read().decode("utf-8", errors="replace"),
        }
    finally:
        client.close()


def _remote_path(path: str | None) -> str:
    value = (path or ".").strip() or "."
    if "\x00" in value or len(value) > 4096:
        raise ValueError("远程路径不合法")
    return value


def _file_type(mode: int) -> str:
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "link"
    if stat.S_ISREG(mode):
        return "file"
    return "other"


def list_remote_files(server: ServerAsset, path: str = ".") -> dict:
    """列出远程目录，给前端文件管理器使用。"""
    target = _remote_path(path)
    client = _connect(server)
    try:
        sftp = client.open_sftp()
        try:
            attrs = sftp.listdir_attr(target)
            files = []
            for item in attrs:
                item_type = _file_type(item.st_mode)
                full_path = posixpath.join(target.rstrip("/") or "/", item.filename)
                files.append(
                    {
                        "name": item.filename,
                        "path": full_path,
                        "type": item_type,
                        "size": item.st_size,
                        "mtime": item.st_mtime,
                        "permissions": stat.filemode(item.st_mode),
                    }
                )
            files.sort(key=lambda item: (item["type"] != "directory", item["name"].lower()))
            return {
                "path": target,
                "parent": posixpath.dirname(target.rstrip("/")) or "/",
                "files": files,
            }
        finally:
            sftp.close()
    finally:
        client.close()


def read_remote_file(server: ServerAsset, path: str, max_bytes: int = 1024 * 1024) -> dict:
    target = _remote_path(path)
    limit = min(max(int(max_bytes or 0), 1024), 5 * 1024 * 1024)
    client = _connect(server)
    try:
        sftp = client.open_sftp()
        try:
            with sftp.open(target, "rb") as handle:
                data = handle.read(limit + 1)
            truncated = len(data) > limit
            text = data[:limit].decode("utf-8", errors="replace")
            return {"path": target, "content": text, "truncated": truncated, "bytes": min(len(data), limit)}
        finally:
            sftp.close()
    finally:
        client.close()


def write_remote_file(server: ServerAsset, path: str, content: str) -> dict:
    target = _remote_path(path)
    data = content.encode("utf-8")
    client = _connect(server)
    try:
        sftp = client.open_sftp()
        try:
            with sftp.open(target, "wb") as handle:
                handle.write(data)
            return {"ok": True, "path": target, "bytes": len(data)}
        finally:
            sftp.close()
    finally:
        client.close()


def mkdir_remote(server: ServerAsset, path: str) -> dict:
    target = _remote_path(path)
    client = _connect(server)
    try:
        sftp = client.open_sftp()
        try:
            sftp.mkdir(target)
            return {"ok": True, "path": target}
        finally:
            sftp.close()
    finally:
        client.close()


def delete_remote_path(server: ServerAsset, path: str) -> dict:
    target = _remote_path(path)
    client = _connect(server)
    try:
        sftp = client.open_sftp()
        try:
            attrs = sftp.stat(target)
            if stat.S_ISDIR(attrs.st_mode):
                sftp.rmdir(target)
            else:
                sftp.remove(target)
            return {"ok": True, "path": target}
        finally:
            sftp.close()
    finally:
        client.close()


def test_connection(server: ServerAsset) -> dict:
    result = run_command(server, "echo smartopsdocs-ok")
    return {"ok": result["exit_code"] == 0, "detail": result}


def server_overview(server: ServerAsset) -> dict:
    commands = {
        "hostname": "hostname",
        "system": "uname -srmo",
        "uptime": "uptime -p || uptime",
        "load": "cat /proc/loadavg",
        "memory": "free -m",
        "disks": "df -h -x tmpfs -x devtmpfs",
        "processes": "ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 10",
        "docker": "command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}} {{.Status}}' | head -n 10 || true",
    }
    data = {}
    for key, command in commands.items():
        try:
            data[key] = run_command(server, command, timeout=10)
        except Exception as exc:
            data[key] = {"exit_code": 1, "stdout": "", "stderr": str(exc)}
    return data


def create_shell(server: ServerAsset) -> tuple[paramiko.SSHClient, paramiko.Channel]:
    """创建交互式 Shell 会话，返回 (client, channel)."""
    client = _connect(server)
    channel = client.invoke_shell(term="xterm-256color")
    channel.settimeout(0.05)
    return client, channel


def create_command_shell(server: ServerAsset, command: str, term: str = "xterm-256color") -> tuple[paramiko.SSHClient, paramiko.Channel]:
    """创建带 PTY 的交互式命令会话，适合 docker exec / kubectl exec 等场景。"""
    client = _connect(server)
    channel = client.get_transport().open_session()
    channel.get_pty(term=term)
    channel.exec_command(command)
    channel.settimeout(0.05)
    return client, channel
