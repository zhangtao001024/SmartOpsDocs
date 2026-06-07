"""add chunk embeddings

Revision ID: 20260607_0001
Revises:
Create Date: 2026-06-07 00:01:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260607_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_chunk_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("vector", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id"),
    )
    op.create_index(op.f("ix_document_chunk_embeddings_chunk_id"), "document_chunk_embeddings", ["chunk_id"], unique=True)
    op.create_index(op.f("ix_document_chunk_embeddings_content_hash"), "document_chunk_embeddings", ["content_hash"], unique=False)
    op.create_index(op.f("ix_document_chunk_embeddings_model"), "document_chunk_embeddings", ["model"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_chunk_embeddings_model"), table_name="document_chunk_embeddings")
    op.drop_index(op.f("ix_document_chunk_embeddings_content_hash"), table_name="document_chunk_embeddings")
    op.drop_index(op.f("ix_document_chunk_embeddings_chunk_id"), table_name="document_chunk_embeddings")
    op.drop_table("document_chunk_embeddings")
