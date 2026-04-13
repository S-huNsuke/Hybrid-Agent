from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, MetaData
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

metadata = MetaData()


def upgrade() -> None:
    op.create_table(
        "documents",
        Column("id", String(36), primary_key=True),
        Column("filename", String(255), nullable=False),
        Column("file_path", String(512)),
        Column("file_size", Integer),
        Column("file_type", String(50)),
        Column("status", String(20), nullable=False, server_default="ready"),
        Column("chunk_count", Integer, nullable=False, server_default="0"),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
        Column("group_id", String(36), ForeignKey("groups.id"), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_documents_group_id", "documents", ["group_id"])

    op.create_table(
        "bm25_chunks",
        Column("id", String(36), primary_key=True),
        Column("doc_id", String(36), nullable=False),
        Column("group_id", String(36), ForeignKey("groups.id"), nullable=True),
        Column("content", Text, nullable=False),
        Column("tokens", Text),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_index("ix_bm25_chunks_doc_id", "bm25_chunks", ["doc_id"])
    op.create_index("ix_bm25_chunks_group_id", "bm25_chunks", ["group_id"])

    op.create_table(
        "conversation_summaries",
        Column("thread_id", String(255), primary_key=True),
        Column("summary", Text, nullable=False),
        Column("message_count", Integer, nullable=False, server_default="0"),
        Column("updated_at", DateTime),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "users",
        Column("id", String(36), primary_key=True),
        Column("username", String(150), nullable=False),
        Column("email", String(255)),
        Column("hashed_password", String(512)),
        Column("role", String(50), nullable=False, server_default="member"),
        Column("is_active", Boolean, nullable=False, server_default="1"),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "groups",
        Column("id", String(36), primary_key=True),
        Column("name", String(255), nullable=False),
        Column("description", Text),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_groups_name", "groups", ["name"], unique=True)

    op.create_table(
        "user_groups",
        Column("user_id", String(36), ForeignKey("users.id"), primary_key=True),
        Column("group_id", String(36), ForeignKey("groups.id"), primary_key=True),
        Column("role", String(50), nullable=False, server_default="member"),
        Column("assigned_at", DateTime),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "chat_sessions",
        Column("id", String(36), primary_key=True),
        Column("title", String(255), nullable=False),
        Column("user_id", String(36), ForeignKey("users.id"), nullable=True),
        Column("group_id", String(36), ForeignKey("groups.id"), nullable=True),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
        Column("last_message_at", DateTime),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_index("ix_chat_sessions_group_id", "chat_sessions", ["group_id"])

    op.create_table(
        "llm_usage_logs",
        Column("id", String(36), primary_key=True),
        Column("user_id", String(36), ForeignKey("users.id")),
        Column("group_id", String(36), ForeignKey("groups.id"), nullable=True),
        Column("model_name", String(255), nullable=False),
        Column("prompt_tokens", Integer, nullable=False, server_default="0"),
        Column("completion_tokens", Integer, nullable=False, server_default="0"),
        Column("total_tokens", Integer, nullable=False, server_default="0"),
        Column("created_at", DateTime),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_llm_usage_logs_user_id", "llm_usage_logs", ["user_id"])
    op.create_index("ix_llm_usage_logs_group_id", "llm_usage_logs", ["group_id"])

    op.create_table(
        "upload_tasks",
        Column("task_id", String(36), primary_key=True),
        Column("document_id", String(36), ForeignKey("documents.id")),
        Column("filename", String(255), nullable=False),
        Column("group_id", String(36), ForeignKey("groups.id")),
        Column("status", String(20), nullable=False, server_default="queued"),
        Column("progress", Integer, nullable=False, server_default="0"),
        Column("message", Text),
        Column("error", Text),
        Column("created_at", DateTime),
        Column("started_at", DateTime),
        Column("completed_at", DateTime),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_upload_tasks_document_id", "upload_tasks", ["document_id"])
    op.create_index("ix_upload_tasks_group_id", "upload_tasks", ["group_id"])

    op.create_table(
        "providers",
        Column("id", String(36), primary_key=True),
        Column("group_id", String(36), ForeignKey("groups.id"), nullable=True),
        Column("provider_type", String(50), nullable=False),
        Column("display_name", String(255), nullable=False),
        Column("base_url", String(512)),
        Column("api_key_ciphertext", Text, nullable=False),
        Column("api_key_hint", String(32)),
        Column("models", Text),
        Column("default_model", String(255)),
        Column("is_active", Boolean, nullable=False, server_default="1"),
        Column("created_by", String(36), ForeignKey("users.id"), nullable=True),
        Column("updated_by", String(36), ForeignKey("users.id"), nullable=True),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_providers_group_id", "providers", ["group_id"])
    op.create_index("ix_providers_provider_type", "providers", ["provider_type"])


def downgrade() -> None:
    op.drop_index("ix_providers_provider_type", table_name="providers")
    op.drop_index("ix_providers_group_id", table_name="providers")
    op.drop_table("providers")
    op.drop_index("ix_llm_usage_logs_user_id", table_name="llm_usage_logs")
    op.drop_index("ix_llm_usage_logs_group_id", table_name="llm_usage_logs")
    op.drop_table("llm_usage_logs")
    op.drop_index("ix_upload_tasks_group_id", table_name="upload_tasks")
    op.drop_index("ix_upload_tasks_document_id", table_name="upload_tasks")
    op.drop_table("upload_tasks")
    op.drop_table("user_groups")
    op.drop_index("ix_groups_name", table_name="groups")
    op.drop_table("groups")
    op.drop_index("ix_chat_sessions_group_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.drop_table("conversation_summaries")
    op.drop_index("ix_bm25_chunks_doc_id", table_name="bm25_chunks")
    op.drop_index("ix_bm25_chunks_group_id", table_name="bm25_chunks")
    op.drop_index("ix_documents_group_id", table_name="documents")
    op.drop_table("bm25_chunks")
    op.drop_table("documents")
