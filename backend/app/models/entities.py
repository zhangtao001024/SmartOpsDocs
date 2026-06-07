from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ServerAsset(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    hostname: Mapped[str] = mapped_column(String(128), default="")
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    ssh_username: Mapped[str] = mapped_column(String(128), default="root")
    ssh_password: Mapped[str] = mapped_column(Text, default="")
    ssh_private_key: Mapped[str] = mapped_column(Text, default="")
    project: Mapped[str] = mapped_column(String(128), default="default", index=True)
    environment: Mapped[str] = mapped_column(String(32), default="dev")
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    tags: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class KubeCluster(Base):
    __tablename__ = "kube_clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    kubeconfig: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    file_path: Mapped[str] = mapped_column(Text)
    project: Mapped[str] = mapped_column(String(128), default="default", index=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    revisions: Mapped[list["DocumentRevision"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    tasks: Mapped[list["DocumentTask"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(255), default="")
    project: Mapped[str] = mapped_column(String(128), default="default", index=True)
    document: Mapped[Document] = relationship(back_populates="chunks")
    embedding: Mapped["DocumentChunkEmbedding"] = relationship(back_populates="chunk", cascade="all, delete-orphan", uselist=False)


class DocumentChunkEmbedding(Base):
    __tablename__ = "document_chunk_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("document_chunks.id", ondelete="CASCADE"), unique=True, index=True)
    model: Mapped[str] = mapped_column(String(128), default="", index=True)
    dimension: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    vector: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    chunk: Mapped[DocumentChunk] = relationship(back_populates="embedding")


class DocumentRevision(Base):
    __tablename__ = "document_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    document: Mapped[Document] = relationship(back_populates="revisions")


class DocumentTask(Base):
    __tablename__ = "document_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    task_type: Mapped[str] = mapped_column(String(32), default="parse")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    document: Mapped[Document] = relationship(back_populates="tasks")


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    project: Mapped[str] = mapped_column(String(128), default="default", index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    references: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
