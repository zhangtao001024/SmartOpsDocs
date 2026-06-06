from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ServerBase(BaseModel):
    ip: str
    hostname: str = ""
    ssh_port: int = 22
    ssh_username: str = "root"
    ssh_password: str = ""
    ssh_private_key: str = ""
    project: str = "default"
    environment: str = "dev"
    tags: str = ""


class ServerCreate(ServerBase):
    pass


class ServerUpdate(BaseModel):
    """编辑服务器 — 全部可选，支持部分更新."""
    ip: str | None = None
    hostname: str | None = None
    ssh_port: int | None = None
    ssh_username: str | None = None
    ssh_password: str | None = None
    ssh_private_key: str | None = None
    project: str | None = None
    environment: str | None = None
    tags: str | None = None


class ServerTestSchema(BaseModel):
    """测试连接 — 仅需连接信息，可选 server_id 自动更新状态."""
    server_id: int | None = None
    ip: str
    hostname: str = ""
    ssh_port: int = 22
    ssh_username: str = "root"
    ssh_password: str = ""
    ssh_private_key: str = ""


class ServerCommandRequest(BaseModel):
    command: str
    timeout: int = 30


class ServerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ip: str
    hostname: str = ""
    ssh_port: int = 22
    ssh_username: str = "root"
    project: str = "default"
    environment: str = "dev"
    tags: str = ""
    status: str = "unknown"
    created_at: datetime
    updated_at: datetime


class KubeClusterCreate(BaseModel):
    name: str
    kubeconfig: str
    description: str = ""


class KubeClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    created_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    file_path: str
    project: str
    status: str
    error_message: str
    created_at: datetime


class LLMConfigRequest(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"
    vision_model: str = ""


class LLMConfigResponse(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"
    vision_model: str = ""
    has_key: bool = False


class ChatRequest(BaseModel):
    question: str
    project: str = "default"
    session_id: str = "default"
    stream: bool = False


class ChatResponse(BaseModel):
    answer: str
    references: list[dict]
