import tempfile
from pathlib import Path
from datetime import datetime, timezone

from app.models.entities import KubeCluster


def _tail(value: int, default: int = 200, maximum: int = 5000) -> int:
    try:
        tail = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(tail, 1), maximum)


def _clients(cluster: KubeCluster):
    try:
        from kubernetes import client, config
    except ImportError as exc:
        raise RuntimeError("kubernetes Python Client 未安装，无法访问集群") from exc

    with tempfile.NamedTemporaryFile("w", delete=False) as handle:
        handle.write(cluster.kubeconfig)
        path = handle.name
    try:
        config.load_kube_config(config_file=path)
        return client.CoreV1Api(), client.AppsV1Api(), client.NetworkingV1Api(), client.BatchV1Api()
    finally:
        Path(path).unlink(missing_ok=True)


def list_namespaces(cluster: KubeCluster) -> list[str]:
    core, _, _, _ = _clients(cluster)
    return [item.metadata.name for item in core.list_namespace().items]


def list_pods(cluster: KubeCluster, namespace: str | None = None) -> list[dict]:
    core, _, _, _ = _clients(cluster)
    pods = core.list_namespaced_pod(namespace).items if namespace else core.list_pod_for_all_namespaces().items
    return [
        {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "node": pod.spec.node_name,
            "restarts": sum((cs.restart_count or 0) for cs in (pod.status.container_statuses or [])),
            "created_at": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else "",
        }
        for pod in pods
    ]


def pod_logs(cluster: KubeCluster, namespace: str, pod_name: str, tail: int = 200) -> str:
    core, _, _, _ = _clients(cluster)
    return core.read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=_tail(tail))


def pod_json(cluster: KubeCluster, namespace: str, pod_name: str) -> dict:
    try:
        from kubernetes import client
    except ImportError as exc:
        raise RuntimeError("kubernetes Python Client 未安装，无法访问集群") from exc
    core, _, _, _ = _clients(cluster)
    pod = core.read_namespaced_pod(name=pod_name, namespace=namespace)
    return client.ApiClient().sanitize_for_serialization(pod)


def pod_describe(cluster: KubeCluster, namespace: str, pod_name: str) -> dict:
    try:
        from kubernetes import client
    except ImportError as exc:
        raise RuntimeError("kubernetes Python Client 未安装，无法访问集群") from exc
    core, _, _, _ = _clients(cluster)
    api_client = client.ApiClient()
    pod = core.read_namespaced_pod(name=pod_name, namespace=namespace)
    pod_data = api_client.sanitize_for_serialization(pod)
    events = core.list_namespaced_event(
        namespace,
        field_selector=f"involvedObject.name={pod_name},involvedObject.kind=Pod",
    ).items
    return {
        "summary": {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "node": pod.spec.node_name,
            "pod_ip": pod.status.pod_ip,
            "host_ip": pod.status.host_ip,
            "created_at": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else "",
        },
        "containers": [
            {
                "name": status.name,
                "ready": status.ready,
                "restart_count": status.restart_count,
                "image": status.image,
                "state": api_client.sanitize_for_serialization(status.state),
            }
            for status in (pod.status.container_statuses or [])
        ],
        "conditions": pod_data.get("status", {}).get("conditions", []),
        "events": [
            {
                "type": item.type or "",
                "reason": item.reason or "",
                "message": item.message or "",
                "count": item.count or 0,
                "last_time": (item.last_timestamp or item.event_time or item.first_timestamp).isoformat()
                if (item.last_timestamp or item.event_time or item.first_timestamp)
                else "",
            }
            for item in sorted(
                events,
                key=lambda item: item.last_timestamp or item.event_time or item.first_timestamp or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )[:30]
        ],
    }


def list_events(cluster: KubeCluster, namespace: str | None = None, limit: int = 80) -> list[dict]:
    core, _, _, _ = _clients(cluster)
    events = core.list_namespaced_event(namespace).items if namespace else core.list_event_for_all_namespaces().items
    rows = sorted(
        events,
        key=lambda item: item.last_timestamp or item.event_time or item.first_timestamp or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return [
        {
            "namespace": item.metadata.namespace,
            "name": item.metadata.name,
            "type": item.type or "",
            "reason": item.reason or "",
            "message": item.message or "",
            "involved_object": f"{item.involved_object.kind}/{item.involved_object.name}",
            "count": item.count or 0,
            "last_time": (item.last_timestamp or item.event_time or item.first_timestamp).isoformat()
            if (item.last_timestamp or item.event_time or item.first_timestamp)
            else "",
        }
        for item in rows[:limit]
    ]


def list_deployments(cluster: KubeCluster, namespace: str | None = None) -> list[dict]:
    _, apps, _, _ = _clients(cluster)
    deps = apps.list_namespaced_deployment(namespace).items if namespace else apps.list_deployment_for_all_namespaces().items
    return [
        {
            "name": dep.metadata.name,
            "namespace": dep.metadata.namespace,
            "replicas": f"{dep.status.ready_replicas or 0}/{dep.status.replicas or 0}",
            "available": dep.status.ready_replicas or 0,
            "created_at": dep.metadata.creation_timestamp.isoformat() if dep.metadata.creation_timestamp else "",
        }
        for dep in deps
    ]


def list_services(cluster: KubeCluster, namespace: str | None = None) -> list[dict]:
    core, _, _, _ = _clients(cluster)
    svcs = core.list_namespaced_service(namespace).items if namespace else core.list_service_for_all_namespaces().items
    return [
        {
            "name": svc.metadata.name,
            "namespace": svc.metadata.namespace,
            "type": svc.spec.type or "ClusterIP",
            "cluster_ip": svc.spec.cluster_ip or "",
            "ports": ", ".join(f"{p.port}/{p.protocol}" for p in (svc.spec.ports or [])),
        }
        for svc in svcs
    ]


def list_nodes(cluster: KubeCluster) -> list[dict]:
    core, _, _, _ = _clients(cluster)
    nodes = core.list_node().items
    rows = []
    for node in nodes:
        conditions = {item.type: item.status for item in (node.status.conditions or [])}
        rows.append({
            "name": node.metadata.name,
            "ready": conditions.get("Ready") == "True",
            "roles": ",".join(node.metadata.labels.get(key, "").replace("true", key.rsplit("/", 1)[-1]) for key in node.metadata.labels if key.startswith("node-role.kubernetes.io/")).strip(","),
            "version": node.status.node_info.kubelet_version if node.status.node_info else "",
            "os": node.status.node_info.os_image if node.status.node_info else "",
            "internal_ip": next((addr.address for addr in (node.status.addresses or []) if addr.type == "InternalIP"), ""),
            "cpu": node.status.capacity.get("cpu", "") if node.status.capacity else "",
            "memory": node.status.capacity.get("memory", "") if node.status.capacity else "",
            "created_at": node.metadata.creation_timestamp.isoformat() if node.metadata.creation_timestamp else "",
        })
    return rows


def list_ingresses(cluster: KubeCluster, namespace: str | None = None) -> list[dict]:
    _, _, networking, _ = _clients(cluster)
    ingresses = networking.list_namespaced_ingress(namespace).items if namespace else networking.list_ingress_for_all_namespaces().items
    return [
        {
            "name": item.metadata.name,
            "namespace": item.metadata.namespace,
            "class_name": item.spec.ingress_class_name or "",
            "hosts": ", ".join(rule.host or "" for rule in (item.spec.rules or [])),
            "address": ", ".join(
                point.ip or point.hostname or ""
                for lb in (item.status.load_balancer.ingress or [])
                for point in [lb]
            ) if item.status and item.status.load_balancer else "",
            "created_at": item.metadata.creation_timestamp.isoformat() if item.metadata.creation_timestamp else "",
        }
        for item in ingresses
    ]


def list_statefulsets(cluster: KubeCluster, namespace: str | None = None) -> list[dict]:
    _, apps, _, _ = _clients(cluster)
    rows = apps.list_namespaced_stateful_set(namespace).items if namespace else apps.list_stateful_set_for_all_namespaces().items
    return [
        {
            "name": item.metadata.name,
            "namespace": item.metadata.namespace,
            "replicas": f"{item.status.ready_replicas or 0}/{item.status.replicas or 0}",
            "service_name": item.spec.service_name or "",
            "created_at": item.metadata.creation_timestamp.isoformat() if item.metadata.creation_timestamp else "",
        }
        for item in rows
    ]


def list_daemonsets(cluster: KubeCluster, namespace: str | None = None) -> list[dict]:
    _, apps, _, _ = _clients(cluster)
    rows = apps.list_namespaced_daemon_set(namespace).items if namespace else apps.list_daemon_set_for_all_namespaces().items
    return [
        {
            "name": item.metadata.name,
            "namespace": item.metadata.namespace,
            "desired": item.status.desired_number_scheduled or 0,
            "ready": item.status.number_ready or 0,
            "available": item.status.number_available or 0,
            "created_at": item.metadata.creation_timestamp.isoformat() if item.metadata.creation_timestamp else "",
        }
        for item in rows
    ]


def list_jobs(cluster: KubeCluster, namespace: str | None = None) -> list[dict]:
    _, _, _, batch = _clients(cluster)
    rows = batch.list_namespaced_job(namespace).items if namespace else batch.list_job_for_all_namespaces().items
    return [
        {
            "name": item.metadata.name,
            "namespace": item.metadata.namespace,
            "active": item.status.active or 0,
            "succeeded": item.status.succeeded or 0,
            "failed": item.status.failed or 0,
            "created_at": item.metadata.creation_timestamp.isoformat() if item.metadata.creation_timestamp else "",
        }
        for item in rows
    ]


def restart_deployment(cluster: KubeCluster, namespace: str, name: str) -> dict:
    _, apps, _, _ = _clients(cluster)
    body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "smartopsdocs/restarted-at": datetime.now(timezone.utc).isoformat()
                    }
                }
            }
        }
    }
    apps.patch_namespaced_deployment(name=name, namespace=namespace, body=body)
    return {"ok": True}


def scale_deployment(cluster: KubeCluster, namespace: str, name: str, replicas: int) -> dict:
    _, apps, _, _ = _clients(cluster)
    replicas = min(max(int(replicas), 0), 100)
    body = {"spec": {"replicas": replicas}}
    apps.patch_namespaced_deployment_scale(name=name, namespace=namespace, body=body)
    return {"ok": True, "replicas": replicas}
