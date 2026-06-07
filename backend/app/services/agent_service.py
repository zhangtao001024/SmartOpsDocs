import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib import error as url_error
from urllib import parse as url_parse
from urllib import request as url_request

from sqlalchemy.orm import Session

from app.models.entities import ChatHistory, KubeCluster, ServerAsset
from app.core.config import get_settings
from app.models.entities import AppSetting
from app.services.ai_service import _recent_history, _resolve_llm, optimize_document
from app.services.document_service import create_knowledge_draft, search_chunks
from app.services.openclaw_service import normalize_skill_names
from app.services.prompts import ops_agent_system_prompt
from app.services.docker_service import (
    container_action,
    docker_dashboard,
    get_logs as docker_logs,
    inspect_container,
    list_container_stats,
    list_containers,
    list_images,
    list_networks,
    list_volumes,
    prune_docker,
    pull_image,
)
from app.services.k8s_service import (
    cluster_overview,
    delete_pod,
    list_events,
    list_pods,
    pod_describe,
    pod_logs,
    restart_workload,
    scale_workload,
)
from app.services.ssh_service import list_remote_files, read_remote_file, run_command, server_overview

ToolHandler = Callable[[Session, dict[str, Any], dict[str, Any]], Any]


@dataclass(frozen=True)
class AgentTool:
    name: str
    module: str
    description: str
    read_only: bool
    handler: ToolHandler
    risk_level: str = "read"


def _require_server(db: Session, context: dict[str, Any]) -> ServerAsset:
    server_id = context.get("server_id")
    if not server_id:
        raise ValueError("缺少 server_id")
    server = db.get(ServerAsset, int(server_id))
    if not server:
        raise ValueError("服务器不存在")
    return server


def _require_cluster(db: Session, context: dict[str, Any]) -> KubeCluster:
    cluster_id = context.get("cluster_id")
    if not cluster_id:
        raise ValueError("缺少 cluster_id")
    cluster = db.get(KubeCluster, int(cluster_id))
    if not cluster:
        raise ValueError("集群不存在")
    return cluster


def _knowledge_search(db: Session, args: dict[str, Any], context: dict[str, Any]) -> list[dict]:
    query = args["goal"]
    project = args["project"]
    limit = min(max(int(context.get("limit", 5)), 1), 20)
    return [
        {
            "document_id": chunk.document_id,
            "source": chunk.source,
            "content": chunk.content[:1200],
        }
        for chunk in search_chunks(db, project, query, limit)
    ]


def _knowledge_optimize_document(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    document_id = context.get("document_id")
    if not document_id:
        raise ValueError("缺少 document_id")
    instruction = context.get("instruction") or "优化为可执行运维知识库文档，保留来源中的命令、错误和环境信息。"
    result = optimize_document(db, int(document_id), instruction)
    optimized = result.get("optimized") or ""
    return {
        "document_id": int(document_id),
        "mode": result.get("mode"),
        "source_length": result.get("source_length"),
        "optimized_preview": optimized[:4000],
        "truncated": len(optimized) > 4000,
    }


def _knowledge_create_draft(db: Session, args: dict[str, Any], context: dict[str, Any]) -> dict:
    title = context.get("draft_title") or f"Agent 知识草稿 - {args['goal'][:60]}"
    markdown = context.get("draft_content")
    if not markdown:
        raise ValueError("缺少 draft_content")
    document = create_knowledge_draft(db, title=title, markdown=markdown, project=args["project"], note="agent-tool")
    return {
        "document_id": document.id,
        "title": document.title,
        "project": document.project,
        "status": document.status,
    }


def _ssh_overview(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    return server_overview(_require_server(db, context))


def _ssh_command(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    command = (context.get("command") or "").strip()
    if not command:
        raise ValueError("缺少 command")
    timeout = min(max(int(context.get("timeout", 30)), 1), 120)
    return run_command(_require_server(db, context), command, timeout=timeout)


def _ssh_files(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    path = context.get("path") or "."
    return list_remote_files(_require_server(db, context), path)


def _ssh_file_read(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    path = context.get("path")
    if not path:
        raise ValueError("缺少 path")
    return read_remote_file(_require_server(db, context), path)


def _docker_dashboard(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    return docker_dashboard(_require_server(db, context))


def _docker_containers(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> list[dict]:
    return list_containers(_require_server(db, context))


def _docker_stats(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> list[dict]:
    return list_container_stats(_require_server(db, context))


def _docker_images(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> list[dict]:
    return list_images(_require_server(db, context))


def _docker_networks(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> list[dict]:
    return list_networks(_require_server(db, context))


def _docker_volumes(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> list[dict]:
    return list_volumes(_require_server(db, context))


def _docker_logs(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    container_id = context.get("container_id")
    if not container_id:
        raise ValueError("缺少 container_id")
    tail = min(max(int(context.get("tail", 300)), 1), 5000)
    return {"logs": docker_logs(_require_server(db, context), container_id, tail)}


def _docker_inspect(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    container_id = context.get("container_id")
    if not container_id:
        raise ValueError("缺少 container_id")
    return inspect_container(_require_server(db, context), container_id)


def _docker_action(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    container_id = context.get("container_id")
    action = context.get("action")
    if not container_id or not action:
        raise ValueError("缺少 container_id 或 action")
    return container_action(_require_server(db, context), container_id, action)


def _docker_pull(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    image = context.get("image")
    if not image:
        raise ValueError("缺少 image")
    return pull_image(_require_server(db, context), image)


def _docker_prune(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    return prune_docker(_require_server(db, context), context.get("target", "system"))


def _k8s_overview(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    return cluster_overview(_require_cluster(db, context))


def _k8s_pods(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> list[dict]:
    return list_pods(_require_cluster(db, context), context.get("namespace"))


def _k8s_events(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> list[dict]:
    return list_events(_require_cluster(db, context), context.get("namespace"))


def _k8s_pod_logs(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    pod_name = context.get("pod_name")
    namespace = context.get("namespace")
    if not pod_name or not namespace:
        raise ValueError("缺少 pod_name 或 namespace")
    tail = min(max(int(context.get("tail", 300)), 1), 5000)
    return {"logs": pod_logs(_require_cluster(db, context), namespace, pod_name, tail)}


def _k8s_pod_describe(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    pod_name = context.get("pod_name")
    namespace = context.get("namespace")
    if not pod_name or not namespace:
        raise ValueError("缺少 pod_name 或 namespace")
    return pod_describe(_require_cluster(db, context), namespace, pod_name)


def _k8s_delete_pod(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    pod_name = context.get("pod_name")
    namespace = context.get("namespace")
    if not pod_name or not namespace:
        raise ValueError("缺少 pod_name 或 namespace")
    return delete_pod(_require_cluster(db, context), namespace, pod_name)


def _k8s_restart_workload(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    name = context.get("workload_name") or context.get("name")
    namespace = context.get("namespace")
    kind = context.get("kind", "deployment")
    if not name or not namespace:
        raise ValueError("缺少 workload_name 或 namespace")
    return restart_workload(_require_cluster(db, context), namespace, name, kind)


def _k8s_scale_workload(db: Session, _args: dict[str, Any], context: dict[str, Any]) -> dict:
    name = context.get("workload_name") or context.get("name")
    namespace = context.get("namespace")
    replicas = context.get("replicas")
    kind = context.get("kind", "deployment")
    if not name or not namespace or replicas is None:
        raise ValueError("缺少 workload_name、namespace 或 replicas")
    return scale_workload(_require_cluster(db, context), namespace, name, int(replicas), kind)


TOOLS: dict[str, AgentTool] = {
    "knowledge.search": AgentTool("knowledge.search", "knowledge", "检索本地知识库片段", True, _knowledge_search),
    "knowledge.optimize_document": AgentTool("knowledge.optimize_document", "knowledge", "生成知识库文档优化预览", True, _knowledge_optimize_document),
    "knowledge.create_draft": AgentTool("knowledge.create_draft", "knowledge", "把 Agent 总结写入知识草稿", False, _knowledge_create_draft, "knowledge-write"),
    "ssh.overview": AgentTool("ssh.overview", "ssh", "读取服务器系统概览", True, _ssh_overview),
    "ssh.command": AgentTool("ssh.command", "ssh", "执行受控 SSH 命令", False, _ssh_command, "ops-write"),
    "ssh.files": AgentTool("ssh.files", "ssh", "浏览远程目录", True, _ssh_files),
    "ssh.file_read": AgentTool("ssh.file_read", "ssh", "读取远程文本文件", True, _ssh_file_read),
    "docker.dashboard": AgentTool("docker.dashboard", "docker", "读取 Docker 版本、信息和磁盘占用", True, _docker_dashboard),
    "docker.containers": AgentTool("docker.containers", "docker", "列出 Docker 容器", True, _docker_containers),
    "docker.stats": AgentTool("docker.stats", "docker", "读取容器资源占用", True, _docker_stats),
    "docker.images": AgentTool("docker.images", "docker", "列出 Docker 镜像", True, _docker_images),
    "docker.networks": AgentTool("docker.networks", "docker", "列出 Docker 网络", True, _docker_networks),
    "docker.volumes": AgentTool("docker.volumes", "docker", "列出 Docker 卷", True, _docker_volumes),
    "docker.logs": AgentTool("docker.logs", "docker", "读取容器日志", True, _docker_logs),
    "docker.inspect": AgentTool("docker.inspect", "docker", "读取容器 Inspect 信息", True, _docker_inspect),
    "docker.action": AgentTool("docker.action", "docker", "启动、停止、重启、暂停容器", False, _docker_action, "ops-write"),
    "docker.pull": AgentTool("docker.pull", "docker", "拉取 Docker 镜像", False, _docker_pull, "ops-write"),
    "docker.prune": AgentTool("docker.prune", "docker", "清理 Docker 资源", False, _docker_prune, "ops-write"),
    "k8s.overview": AgentTool("k8s.overview", "k8s", "读取 Kubernetes 集群概览", True, _k8s_overview),
    "k8s.pods": AgentTool("k8s.pods", "k8s", "列出 Pod", True, _k8s_pods),
    "k8s.events": AgentTool("k8s.events", "k8s", "读取集群事件", True, _k8s_events),
    "k8s.pod_logs": AgentTool("k8s.pod_logs", "k8s", "读取 Pod 日志", True, _k8s_pod_logs),
    "k8s.pod_describe": AgentTool("k8s.pod_describe", "k8s", "读取 Pod 诊断详情", True, _k8s_pod_describe),
    "k8s.delete_pod": AgentTool("k8s.delete_pod", "k8s", "删除 Pod 触发重建", False, _k8s_delete_pod, "ops-write"),
    "k8s.restart_workload": AgentTool("k8s.restart_workload", "k8s", "重启工作负载", False, _k8s_restart_workload, "ops-write"),
    "k8s.scale_workload": AgentTool("k8s.scale_workload", "k8s", "伸缩工作负载", False, _k8s_scale_workload, "ops-write"),
}


def list_agent_tools() -> list[dict]:
    return [
        {
            "name": tool.name,
            "module": tool.module,
            "description": tool.description,
            "read_only": tool.read_only,
            "risk_level": tool.risk_level,
        }
        for tool in TOOLS.values()
    ]


def _infer_tools(goal: str, context: dict[str, Any], requested: list[str]) -> list[str]:
    if requested:
        return [name for name in requested if name in TOOLS]
    text = goal.lower()
    selected = ["knowledge.search"]
    if context.get("document_id") and any(word in text for word in ["优化", "整理", "润色", "知识库", "文档", "runbook"]):
        selected.append("knowledge.optimize_document")
    if context.get("server_id"):
        selected.append("ssh.overview")
        if "docker" in text or "容器" in text or "镜像" in text:
            selected.extend(["docker.dashboard", "docker.containers", "docker.stats"])
        if context.get("path"):
            selected.append("ssh.files")
        if context.get("command"):
            selected.append("ssh.command")
    if context.get("cluster_id"):
        selected.append("k8s.overview")
        if "pod" in text or "k8s" in text or "kubernetes" in text or "集群" in text:
            selected.extend(["k8s.pods", "k8s.events"])
        if context.get("pod_name"):
            selected.extend(["k8s.pod_describe", "k8s.pod_logs"])
    return list(dict.fromkeys(selected))


def _compact(value: Any, limit: int = 6000) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return value
    return {"truncated": True, "preview": text[:limit]}


def _local_agent_answer(goal: str, tool_calls: list[dict], references: list[dict]) -> str:
    lines = [
        "## Agent 执行结果",
        "",
        f"目标: {goal}",
        "",
        "### 工具调用",
    ]
    for call in tool_calls:
        status = call.get("status")
        suffix = ""
        if status == "blocked_dry_run":
            suffix = "（dry-run 已拦截写操作）"
        elif call.get("error"):
            suffix = f"（失败: {call['error']}）"
        lines.append(f"- {call['tool']}: {status}{suffix}")
    if references:
        lines.extend(["", "### 知识库引用"])
        for idx, ref in enumerate(references, 1):
            lines.append(f"- [{idx}] {ref.get('source')}")
    lines.extend(["", "未配置大模型 API Key 时，Agent 返回工具执行摘要。"])
    return "\n".join(lines)


def _resolve_agent_runtime(db: Session) -> dict[str, Any]:
    env = get_settings()
    keys = ["agent_runtime", "openclaw_endpoint", "openclaw_api_key", "openclaw_agent", "openclaw_web_skills"]
    db_cfg = {}
    for row in db.query(AppSetting).filter(AppSetting.key.in_(keys)).all():
        db_cfg[row.key] = row.value
    return {
        "runtime": db_cfg.get("agent_runtime") or env.agent_runtime,
        "endpoint": db_cfg.get("openclaw_endpoint") or env.openclaw_endpoint or "",
        "api_key": db_cfg.get("openclaw_api_key") or env.openclaw_api_key or "",
        "agent": db_cfg.get("openclaw_agent") or env.openclaw_agent,
        "web_skills": normalize_skill_names(db_cfg.get("openclaw_web_skills") or getattr(env, "openclaw_web_skills", "browser-automation")),
    }


def _openclaw_endpoint_candidates(endpoint: str) -> list[str]:
    endpoint = endpoint.strip().rstrip("/")
    parsed = url_parse.urlparse(endpoint)
    if parsed.path and parsed.path != "/":
        candidates = [endpoint]
        if not parsed.path.endswith("/run"):
            candidates.append(f"{endpoint}/run")
        return candidates
    return [
        endpoint,
        f"{endpoint}/api/agent/run",
        f"{endpoint}/api/agent",
        f"{endpoint}/agent/run",
        f"{endpoint}/agent",
        f"{endpoint}/run",
    ]


def _post_openclaw_endpoint(endpoint: str, runtime: dict[str, str], payload: dict[str, Any]) -> dict:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if runtime["api_key"]:
        headers["Authorization"] = f"Bearer {runtime['api_key']}"
    req = url_request.Request(endpoint, data=body, headers=headers, method="POST")
    with url_request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def _call_openclaw_endpoint(runtime: dict[str, str], payload: dict[str, Any]) -> str:
    endpoint = runtime["endpoint"].strip()
    if not endpoint:
        raise RuntimeError("OpenClaw endpoint 未配置")
    if not endpoint.startswith(("http://", "https://")):
        raise RuntimeError("OpenClaw endpoint 必须是完整 URL，API key/token 请填写到 API Key 字段")
    errors = []
    candidates = _openclaw_endpoint_candidates(endpoint)
    data = None
    used_endpoint = ""
    for candidate in candidates:
        try:
            data = _post_openclaw_endpoint(candidate, runtime, payload)
            used_endpoint = candidate
            break
        except url_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:300]
            errors.append(f"{candidate}: HTTP {exc.code} {detail}".strip())
            if exc.code not in {404, 405}:
                break
        except url_error.URLError as exc:
            errors.append(f"{candidate}: {exc}")
            break
        except Exception as exc:
            errors.append(f"{candidate}: {exc}")
            break
    if data is None:
        raise RuntimeError("; ".join(errors) or "OpenClaw endpoint 调用失败")
    answer = _extract_openclaw_cli_answer(data)
    if answer:
        return answer
    answer = data.get("answer") or data.get("content") or data.get("message")
    if not answer:
        raise RuntimeError(f"OpenClaw 响应缺少 answer/content/message: {used_endpoint}")
    return str(answer)


def _call_openclaw_runtime(runtime: dict[str, str], payload: dict[str, Any]) -> tuple[str, str]:
    if not runtime.get("endpoint"):
        raise RuntimeError("OpenClaw Gateway URL 未配置")
    return _call_openclaw_endpoint(runtime, payload), "openclaw-gateway"


def _extract_openclaw_cli_answer(data: dict[str, Any]) -> str:
    result = data.get("result")
    if isinstance(result, dict):
        payloads = result.get("payloads")
        if isinstance(payloads, list):
            texts = [
                str(item["text"]).strip()
                for item in payloads
                if isinstance(item, dict) and item.get("text")
            ]
            if texts:
                return "\n\n".join(texts)
        meta = result.get("meta")
        if isinstance(meta, dict):
            for key in ("finalAssistantVisibleText", "finalAssistantRawText", "text", "answer", "content"):
                if meta.get(key):
                    return str(meta[key]).strip()
        for key in ("text", "answer", "content", "message", "summary"):
            if result.get(key):
                return str(result[key]).strip()
    for key in ("answer", "content", "message", "summary"):
        if data.get(key):
            return str(data[key]).strip()
    return ""


def _generate_agent_answer(
    db: Session,
    project: str,
    goal: str,
    session_id: str,
    context: dict[str, Any],
    tool_calls: list[dict],
    references: list[dict],
) -> tuple[str, str]:
    runtime = _resolve_agent_runtime(db)
    history = _recent_history(db, project, session_id)
    history_text = "\n".join(
        f"用户: {item.question}\n助手: {(item.answer or '')[:800]}"
        for item in history
    )
    runtime_payload = {
        "agent": runtime["agent"],
        "project": project,
        "session_id": session_id,
        "goal": goal,
        "history": history_text or "无",
        "context": context,
        "tool_calls": tool_calls,
        "references": references,
        "policy": {
            "source": "SmartOpsDocs",
            "dry_run_enforced": True,
            "external_data_is_untrusted": True,
            "knowledge_writes_are_drafts": True,
        },
    }
    if runtime["runtime"] == "openclaw":
        try:
            return _call_openclaw_runtime(runtime, runtime_payload)
        except Exception as exc:
            fallback = _local_agent_answer(goal, tool_calls, references)
            return f"OpenClaw 调用失败: {exc}\n\n{fallback}", "local-openclaw-fallback"

    llm = _resolve_llm(db, "chat")
    if llm["api_key"]:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=llm["api_key"], base_url=llm["base_url"])
            completion = client.chat.completions.create(
                model=llm["model"],
                messages=[
                    {
                        "role": "system",
                        "content": ops_agent_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(runtime_payload, ensure_ascii=False, default=str),
                    },
                ],
            )
            return completion.choices[0].message.content or "", "local-openclaw"
        except Exception as exc:
            return f"AI 调用失败: {exc}\n\n" + _local_agent_answer(goal, tool_calls, references), "local-openclaw-fallback"

    return _local_agent_answer(goal, tool_calls, references), "local-openclaw"


def _render_knowledge_draft(goal: str, answer: str, tool_calls: list[dict], references: list[dict]) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    tool_lines = []
    for call in tool_calls:
        status = call.get("status")
        tool_lines.append(f"- `{call.get('tool')}`: {status}")
    ref_lines = []
    for index, ref in enumerate(references, 1):
        ref_lines.append(f"- [{index}] {ref.get('source') or 'unknown'}")
    return "\n".join(
        [
            f"# Agent 知识草稿：{goal[:80]}",
            "",
            "## 来源",
            "",
            f"- 生成时间：{timestamp}",
            "- 来源类型：SmartOpsDocs Agent 会话",
            "- 状态：草稿，需人工审核后作为正式知识使用",
            "",
            "## 问题",
            "",
            goal,
            "",
            "## Agent 回答",
            "",
            answer.strip() or "无回答内容",
            "",
            "## 工具调用",
            "",
            "\n".join(tool_lines) or "无工具调用",
            "",
            "## 知识库引用",
            "",
            "\n".join(ref_lines) or "无知识库引用",
            "",
            "## 审核清单",
            "",
            "- [ ] 验证命令、路径、IP、端口和集群/命名空间是否适用于当前环境",
            "- [ ] 删除会话中不应长期保存的敏感信息",
            "- [ ] 补充适用场景、前置条件和回滚方案",
        ]
    )


def _maybe_create_agent_knowledge_draft(
    db: Session,
    project: str,
    goal: str,
    answer: str,
    tool_calls: list[dict],
    references: list[dict],
    dry_run: bool,
    context: dict[str, Any],
) -> list[dict]:
    if not context.get("auto_knowledge", True):
        return []
    if any(call.get("tool") == "knowledge.create_draft" for call in tool_calls):
        return []
    call = {
        "tool": "knowledge.create_draft",
        "module": "knowledge",
        "read_only": False,
        "status": "pending",
        "result": None,
    }
    if dry_run:
        call["status"] = "blocked_dry_run"
        call["result"] = {"message": "已生成知识草稿内容，但 dry-run 拦截了写入。关闭 dry-run 后才会入库。"}
        tool_calls.append(call)
        return []
    try:
        markdown = _render_knowledge_draft(goal, answer, tool_calls, references)
        title = f"Agent 知识草稿 - {goal[:48]}"
        document = create_knowledge_draft(db, title=title, markdown=markdown, project=project, note="agent-auto-summary")
        result = {"document_id": document.id, "title": document.title, "project": project, "status": document.status}
        call["status"] = "ok"
        call["result"] = result
        tool_calls.append(call)
        return [result]
    except Exception as exc:
        call["status"] = "error"
        call["error"] = str(exc)
        tool_calls.append(call)
        return []


def run_agent(
    db: Session,
    project: str,
    goal: str,
    session_id: str,
    tools: list[str] | None = None,
    dry_run: bool = True,
    context: dict[str, Any] | None = None,
) -> dict:
    """OpenClaw-style Agent 内核：模型、记忆、工具、通道入口解耦。"""
    context = context or {}
    selected = _infer_tools(goal, context, tools or [])
    args = {"goal": goal, "project": project}
    tool_calls: list[dict] = []
    references: list[dict] = []
    plan = [
        "解析目标和上下文",
        "选择已注册工具",
        "执行只读工具并拦截未确认写操作",
        "汇总结果并写入会话记忆",
    ]

    for name in selected:
        tool = TOOLS[name]
        call = {
            "tool": name,
            "module": tool.module,
            "read_only": tool.read_only,
            "status": "pending",
            "result": None,
        }
        if not tool.read_only and dry_run:
            call["status"] = "blocked_dry_run"
            call["result"] = {"message": "写操作已拦截，设置 dry_run=false 后才会执行。"}
            tool_calls.append(call)
            continue
        try:
            result = tool.handler(db, args, context)
            call["status"] = "ok"
            call["result"] = _compact(result)
            if name == "knowledge.search":
                references = [
                    {
                        "document_id": item.get("document_id"),
                        "source": item.get("source"),
                        "content": (item.get("content") or "")[:240],
                    }
                    for item in result
                ]
        except Exception as exc:
            call["status"] = "error"
            call["error"] = str(exc)
        tool_calls.append(call)

    answer, mode = _generate_agent_answer(db, project, goal, session_id, context, tool_calls, references)
    knowledge_drafts = _maybe_create_agent_knowledge_draft(
        db,
        project=project,
        goal=goal,
        answer=answer,
        tool_calls=tool_calls,
        references=references,
        dry_run=dry_run,
        context=context,
    )

    db.add(
        ChatHistory(
            session_id=session_id,
            project=project,
            question=f"[agent] {goal}",
            answer=answer,
            references=json.dumps(references, ensure_ascii=False),
        )
    )
    db.commit()
    return {
        "answer": answer,
        "references": references,
        "tool_calls": tool_calls,
        "plan": plan,
        "mode": mode,
        "knowledge_drafts": knowledge_drafts,
    }
