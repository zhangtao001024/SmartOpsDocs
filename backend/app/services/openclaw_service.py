import json
import re
from typing import Any
from urllib import error as url_error
from urllib import request as url_request

SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def normalize_skill_names(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            raw_items = parsed if isinstance(parsed, list) else value.split(",")
        except json.JSONDecodeError:
            raw_items = value.split(",")
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []
    selected = []
    for item in raw_items:
        name = str(item or "").strip()
        if name and SKILL_NAME_RE.fullmatch(name) and name not in selected:
            selected.append(name)
    return selected[:20]


def _endpoint_headers(api_key: str = "") -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _probe_openclaw_endpoint(endpoint: str, api_key: str = "") -> dict[str, Any]:
    endpoint = endpoint.strip()
    if not endpoint:
        raise RuntimeError("OpenClaw endpoint 未配置")
    if not endpoint.startswith(("http://", "https://")):
        raise RuntimeError("OpenClaw endpoint 必须是完整 URL")
    started_url = endpoint.rstrip("/")
    req = url_request.Request(started_url, headers=_endpoint_headers(api_key), method="GET")
    try:
        with url_request.urlopen(req, timeout=10) as response:
            return {"reachable": True, "url": started_url, "status_code": response.status, "error": ""}
    except url_error.HTTPError as exc:
        if exc.code in {401, 403, 404, 405}:
            return {"reachable": True, "url": started_url, "status_code": exc.code, "error": ""}
        raise RuntimeError(f"HTTP {exc.code}") from exc
    except url_error.URLError as exc:
        raise RuntimeError(str(exc.reason or exc)) from exc


def get_openclaw_endpoint_status(endpoint: str, api_key: str = "") -> dict[str, Any]:
    probe = _probe_openclaw_endpoint(endpoint, api_key)
    return {
        "ok": probe["reachable"],
        "runtime_version": "",
        "default_agent_id": "",
        "gateway": {
            "url": probe["url"],
            "reachable": probe["reachable"],
            "latency_ms": None,
            "error": probe["error"],
        },
        "gateway_service": {
            "installed": False,
            "runtime_short": "endpoint",
        },
        "tasks": {
            "total": 0,
            "active": 0,
            "failures": 0,
        },
        "raw": {
            "mode": "endpoint",
            "status_code": probe.get("status_code"),
        },
    }
