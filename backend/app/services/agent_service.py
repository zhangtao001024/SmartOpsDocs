import json
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.entities import ChatHistory, KubeCluster, ServerAsset
from app.services.ai_service import _recent_history, _resolve_llm
from app.services.document_service import search_chunks
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
    "knowledge.search": AgentTool("knowledge.search", "knowledge", "检索腾讯知识库/本地知识库片段", True, _knowledge_search),
    "ssh.overview": AgentTool("ssh.overview", "ssh", "读取服务器系统概览", True, _ssh_overview),
    "ssh.command": AgentTool("ssh.command", "ssh", "执行受控 SSH 命令", False, _ssh_command),
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
    "docker.action": AgentTool("docker.action", "docker", "启动、停止、重启、暂停容器", False, _docker_action),
    "docker.pull": AgentTool("docker.pull", "docker", "拉取 Docker 镜像", False, _docker_pull),
    "docker.prune": AgentTool("docker.prune", "docker", "清理 Docker 资源", False, _docker_prune),
    "k8s.overview": AgentTool("k8s.overview", "k8s", "读取 Kubernetes 集群概览", True, _k8s_overview),
    "k8s.pods": AgentTool("k8s.pods", "k8s", "列出 Pod", True, _k8s_pods),
    "k8s.events": AgentTool("k8s.events", "k8s", "读取集群事件", True, _k8s_events),
    "k8s.pod_logs": AgentTool("k8s.pod_logs", "k8s", "读取 Pod 日志", True, _k8s_pod_logs),
    "k8s.pod_describe": AgentTool("k8s.pod_describe", "k8s", "读取 Pod 诊断详情", True, _k8s_pod_describe),
    "k8s.delete_pod": AgentTool("k8s.delete_pod", "k8s", "删除 Pod 触发重建", False, _k8s_delete_pod),
    "k8s.restart_workload": AgentTool("k8s.restart_workload", "k8s", "重启工作负载", False, _k8s_restart_workload),
    "k8s.scale_workload": AgentTool("k8s.scale_workload", "k8s", "伸缩工作负载", False, _k8s_scale_workload),
}


def list_agent_tools() -> list[dict]:
    return [
        {
            "name": tool.name,
            "module": tool.module,
            "description": tool.description,
            "read_only": tool.read_only,
        }
        for tool in TOOLS.values()
    ]


def _infer_tools(goal: str, context: dict[str, Any], requested: list[str]) -> list[str]:
    if requested:
        return [name for name in requested if name in TOOLS]
    text = goal.lower()
    selected = ["knowledge.search"]
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

    llm = _resolve_llm(db, "chat")
    if llm["api_key"]:
        try:
            from openai import OpenAI

            history = _recent_history(db, project, session_id)
            history_text = "\n".join(
                f"用户: {item.question}\n助手: {(item.answer or '')[:800]}"
                for item in history
            )
            client = OpenAI(api_key=llm["api_key"], base_url=llm["base_url"])
            completion = client.chat.completions.create(
                model=llm["model"],
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是 SmartOpsDocs 运维 Agent。按 OpenClaw 风格工作：维护上下文，"
                            "只能基于工具结果和知识库引用作答；写操作如果被 dry-run 拦截，必须明确说明。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "goal": goal,
                                "history": history_text or "无",
                                "context": context,
                                "tool_calls": tool_calls,
                            },
                            ensure_ascii=False,
                            default=str,
                        ),
                    },
                ],
            )
            answer = completion.choices[0].message.content or ""
        except Exception as exc:
            answer = f"AI 调用失败: {exc}\n\n" + _local_agent_answer(goal, tool_calls, references)
    else:
        answer = _local_agent_answer(goal, tool_calls, references)

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
        "mode": "openclaw-style",
    }
