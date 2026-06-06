import io

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
