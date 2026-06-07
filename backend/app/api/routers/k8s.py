"""Kubernetes 管理路由."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import KubeCluster, User
from app.schemas.dto import KubeClusterCreate, KubeClusterOut
from app.services.k8s_service import (
    cluster_overview,
    delete_pod,
    list_deployments,
    list_daemonsets,
    list_events,
    list_ingresses,
    list_jobs,
    list_namespaces,
    list_nodes,
    list_pods,
    list_services,
    list_statefulsets,
    pod_describe,
    pod_json,
    pod_logs,
    resource_json,
    restart_deployment,
    restart_workload,
    scale_deployment,
    scale_workload,
)

router = APIRouter(prefix="/api", tags=["k8s"])


class DeploymentScaleRequest(BaseModel):
    replicas: int


class WorkloadScaleRequest(BaseModel):
    replicas: int
    kind: str = "deployment"


class WorkloadRestartRequest(BaseModel):
    kind: str = "deployment"


@router.get("/k8s/clusters", response_model=list[KubeClusterOut])
def kube_clusters(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return db.query(KubeCluster).order_by(KubeCluster.id.desc()).all()


@router.post("/k8s/clusters", response_model=KubeClusterOut)
def create_kube_cluster(payload: KubeClusterCreate, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = KubeCluster(**payload.model_dump())
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


@router.delete("/k8s/clusters/{cluster_id}")
def delete_kube_cluster(cluster_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    db.delete(cluster)
    db.commit()
    return {"ok": True}


@router.get("/k8s/clusters/{cluster_id}/namespaces")
def kube_namespaces(cluster_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return list_namespaces(cluster)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/clusters/{cluster_id}/overview")
def kube_cluster_overview(cluster_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return cluster_overview(cluster)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/clusters/{cluster_id}/nodes")
def kube_nodes(cluster_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return list_nodes(cluster)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/clusters/{cluster_id}/pods")
def kube_pods(cluster_id: int, namespace: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return list_pods(cluster, namespace)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/clusters/{cluster_id}/deployments")
def kube_deployments(cluster_id: int, namespace: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return list_deployments(cluster, namespace)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/clusters/{cluster_id}/services")
def kube_services(cluster_id: int, namespace: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return list_services(cluster, namespace)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/clusters/{cluster_id}/ingresses")
def kube_ingresses(cluster_id: int, namespace: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return list_ingresses(cluster, namespace)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/clusters/{cluster_id}/statefulsets")
def kube_statefulsets(cluster_id: int, namespace: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return list_statefulsets(cluster, namespace)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/clusters/{cluster_id}/daemonsets")
def kube_daemonsets(cluster_id: int, namespace: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return list_daemonsets(cluster, namespace)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/clusters/{cluster_id}/jobs")
def kube_jobs(cluster_id: int, namespace: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return list_jobs(cluster, namespace)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/pods/{pod_name}/logs")
def kube_pod_logs(pod_name: str, cluster_id: int, namespace: str, tail: int = 200, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return {"logs": pod_logs(cluster, namespace, pod_name, tail)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/pods/{pod_name}/json")
def kube_pod_json(pod_name: str, cluster_id: int, namespace: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return pod_json(cluster, namespace, pod_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/resources/{kind}/{name}/json")
def kube_resource_json(
    kind: str,
    name: str,
    cluster_id: int,
    namespace: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return resource_json(cluster, kind, namespace, name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/pods/{pod_name}/describe")
def kube_pod_describe(pod_name: str, cluster_id: int, namespace: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return pod_describe(cluster, namespace, pod_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/k8s/pods/{pod_name}")
def kube_pod_delete(pod_name: str, cluster_id: int, namespace: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return delete_pod(cluster, namespace, pod_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/k8s/clusters/{cluster_id}/events")
def kube_events(cluster_id: int, namespace: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return list_events(cluster, namespace)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/k8s/deployments/{name}/restart")
def kube_deployment_restart(name: str, cluster_id: int, namespace: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return restart_deployment(cluster, namespace, name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/k8s/workloads/{name}/restart")
def kube_workload_restart(
    name: str,
    payload: WorkloadRestartRequest,
    cluster_id: int,
    namespace: str,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return restart_workload(cluster, namespace, name, payload.kind)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/k8s/deployments/{name}/scale")
def kube_deployment_scale(
    name: str,
    payload: DeploymentScaleRequest,
    cluster_id: int,
    namespace: str,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return scale_deployment(cluster, namespace, name, payload.replicas)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/k8s/workloads/{name}/scale")
def kube_workload_scale(
    name: str,
    payload: WorkloadScaleRequest,
    cluster_id: int,
    namespace: str,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    cluster = db.get(KubeCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="集群不存在")
    try:
        return scale_workload(cluster, namespace, name, payload.replicas, payload.kind)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
