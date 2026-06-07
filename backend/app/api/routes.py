"""路由总入口 — 聚合所有子路由."""

from fastapi import APIRouter

router = APIRouter()

from app.api.routers.auth import router as auth_router  # noqa: E402
from app.api.routers.servers import router as servers_router  # noqa: E402
from app.api.routers.docker import router as docker_router  # noqa: E402
from app.api.routers.k8s import router as k8s_router  # noqa: E402
from app.api.routers.documents import router as documents_router  # noqa: E402
from app.api.routers.ai import router as ai_router  # noqa: E402
from app.api.routers.settings import router as settings_router  # noqa: E402
from app.api.routers.system import router as system_router  # noqa: E402

router.include_router(auth_router)
router.include_router(settings_router)
router.include_router(system_router)
router.include_router(servers_router)
router.include_router(docker_router)
router.include_router(k8s_router)
router.include_router(documents_router)
router.include_router(ai_router)
