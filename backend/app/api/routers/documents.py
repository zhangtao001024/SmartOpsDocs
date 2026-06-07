"""知识库文档路由."""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.models.entities import Document, DocumentChunk, DocumentTask, User
from app.services.document_service import (
    create_document_task,
    delete_document_files,
    delete_document_fts,
    list_document_revisions,
    markdown_for_api,
    process_document,
    read_document_markdown,
    restore_document_revision,
    search_chunks,
)

router = APIRouter(prefix="/api", tags=["documents"])
UPLOAD_CHUNK_SIZE = 1024 * 1024


class KnowledgeQuery(BaseModel):
    query: str
    project: str = "default"
    limit: int = 5


class MarkdownUpdate(BaseModel):
    content: str


class WebPullRequest(BaseModel):
    url: str
    project: str = "default"
    instruction: str = ""


def _document_source_kind(document: Document) -> str:
    source = (document.file_path or document.title or "").strip().lower()
    title = (document.title or "").strip().lower()
    if source.startswith(("http://", "https://")) or title.startswith(("http://", "https://")):
        return "web"
    suffix = Path(source or title).suffix.lower()
    if suffix in {".docx", ".doc"}:
        return "word"
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".md":
        return "markdown"
    if suffix == ".txt":
        return "text"
    if document.status == "draft":
        return "draft"
    return "document"


def _document_source_hint(document: Document) -> str:
    source = (document.file_path or "").strip()
    if source.startswith(("http://", "https://")):
        return source
    return ""


def _run_document_task(document_id: int, task_id: int | None = None) -> None:
    db = SessionLocal()
    try:
        process_document(db, document_id, task_id)
    finally:
        db.close()


def _run_web_pull_task(document_id: int, url: str, instruction: str, task_id: int | None = None) -> None:
    from app.services.web_pull_service import process_web_pull

    db = SessionLocal()
    try:
        process_web_pull(db, document_id, url, instruction, task_id)
    finally:
        db.close()


@router.post("/documents/upload")
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project: str = "default",
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".docx", ".md", ".pdf", ".txt"}:
        raise HTTPException(status_code=400, detail="仅支持 .docx, .md, .pdf, .txt")
    target = settings.upload_dir / f"{uuid4().hex}{suffix}"
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    written = 0
    try:
        with target.open("wb") as handle:
            while chunk := file.file.read(UPLOAD_CHUNK_SIZE):
                written += len(chunk)
                if max_bytes > 0 and written > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"文件不能超过 {settings.max_upload_size_mb} MB",
                    )
                handle.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    document = Document(title=file.filename or target.name, file_path=str(target), project=project, status="uploaded")
    db.add(document)
    db.commit()
    db.refresh(document)
    task = create_document_task(db, document, "parse")
    background_tasks.add_task(_run_document_task, document.id, task.id)
    return document


@router.post("/knowledge/pull-url")
def pull_url_to_knowledge(
    payload: WebPullRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL 不能为空")
    document = Document(title=url, file_path=url, project=payload.project or "default", status="uploaded")
    db.add(document)
    db.commit()
    db.refresh(document)
    task = create_document_task(db, document, "web-pull")
    background_tasks.add_task(_run_web_pull_task, document.id, url, payload.instruction, task.id)
    return _document_detail_payload(db, document)


@router.get("/documents")
def documents(
    project: str | None = None,
    q: str | None = Query(default=None, description="按标题、项目、状态搜索"),
    status: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    query = db.query(Document)
    if project:
        query = query.filter(Document.project == project)
    if status:
        query = query.filter(Document.status == status)
    if q:
        keyword = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Document.title.ilike(keyword),
                Document.project.ilike(keyword),
                Document.status.ilike(keyword),
            )
        )
    query = query.order_by(Document.id.desc()).offset(offset)
    if limit:
        query = query.limit(limit)
    return query.all()


@router.get("/knowledge/tree")
def knowledge_tree(
    project: str | None = None,
    q: str | None = Query(default=None, description="按标题、项目、状态搜索"),
    status: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    query = db.query(Document)
    if project:
        query = query.filter(Document.project == project)
    if status:
        query = query.filter(Document.status == status)
    if q:
        keyword = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Document.title.ilike(keyword),
                Document.project.ilike(keyword),
                Document.status.ilike(keyword),
            )
        )
    documents = query.order_by(Document.project.asc(), Document.title.asc()).offset(offset)
    if limit:
        documents = documents.limit(limit)
    documents = documents.all()
    document_ids = [doc.id for doc in documents]
    chunk_counts = {
        document_id: count
        for document_id, count in db.query(DocumentChunk.document_id, func.count(DocumentChunk.id))
        .filter(DocumentChunk.document_id.in_(document_ids))
        .group_by(DocumentChunk.document_id)
        .all()
    } if document_ids else {}
    task_updates = {
        document_id: updated_at
        for document_id, updated_at in db.query(DocumentTask.document_id, func.max(DocumentTask.updated_at))
        .filter(DocumentTask.document_id.in_(document_ids))
        .group_by(DocumentTask.document_id)
        .all()
    } if document_ids else {}
    return [
        {
            "id": doc.id,
            "title": doc.title,
            "project": doc.project,
            "status": doc.status,
            "source_kind": _document_source_kind(doc),
            "chunk_count": chunk_counts.get(doc.id, 0),
            "created_at": doc.created_at,
            "updated_at": task_updates.get(doc.id) or doc.created_at,
        }
        for doc in documents
    ]


def _chunk_payload(chunk: DocumentChunk) -> dict:
    document = chunk.document
    return {
        "document_id": chunk.document_id,
        "document_title": document.title if document else "",
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "project": chunk.project,
        "source": chunk.source,
        "content": chunk.content,
        "preview": chunk.content[:300],
    }


@router.get("/knowledge/search")
def knowledge_search(
    q: str = Query(..., min_length=1),
    project: str = "default",
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    chunks = search_chunks(db, project, q, limit)
    return {"query": q, "project": project, "results": [_chunk_payload(chunk) for chunk in chunks]}


@router.post("/agent/knowledge/query")
def agent_knowledge_query(payload: KnowledgeQuery, db: Session = Depends(get_db), _: User = Depends(current_user)):
    limit = min(max(payload.limit, 1), 20)
    chunks = search_chunks(db, payload.project, payload.query, limit)
    return {
        "query": payload.query,
        "project": payload.project,
        "results": [_chunk_payload(chunk) for chunk in chunks],
    }


@router.get("/documents/{document_id}")
def document_detail(document_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return _document_detail_payload(db, document)


def _document_detail_payload(db: Session, document: Document) -> dict:
    document_id = document.id
    markdown = read_document_markdown(document_id)
    latest_task = (
        db.query(DocumentTask)
        .filter(DocumentTask.document_id == document_id)
        .order_by(DocumentTask.id.desc())
        .first()
    )
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )
    return {
        "id": document.id,
        "title": document.title,
        "project": document.project,
        "status": document.status,
        "source_kind": _document_source_kind(document),
        "source_hint": _document_source_hint(document),
        "error_message": document.error_message,
        "created_at": document.created_at,
        "latest_task": {
            "id": latest_task.id,
            "task_type": latest_task.task_type,
            "status": latest_task.status,
            "progress": latest_task.progress,
            "message": latest_task.message,
            "updated_at": latest_task.updated_at,
        } if latest_task else None,
        "content": markdown_for_api(document_id, markdown) if markdown else "\n\n".join(chunk.content for chunk in chunks),
        "raw_content": markdown,
        "chunks": [
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "source": chunk.source,
                "content": chunk.content,
            }
            for chunk in chunks
        ],
    }


@router.post("/documents/{document_id}/reprocess")
def reprocess_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    task = create_document_task(db, document, "reprocess")
    document.status = "uploaded"
    document.error_message = ""
    db.commit()
    background_tasks.add_task(_run_document_task, document_id, task.id)
    db.refresh(document)
    return _document_detail_payload(db, document)


@router.put("/documents/{document_id}/markdown")
def update_document_markdown(
    document_id: int,
    payload: MarkdownUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    from app.services.document_service import save_document_markdown

    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    save_document_markdown(db, document, payload.content)
    db.refresh(document)
    return _document_detail_payload(db, document)


@router.get("/documents/{document_id}/tasks")
def document_tasks(document_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    rows = (
        db.query(DocumentTask)
        .filter(DocumentTask.document_id == document_id)
        .order_by(DocumentTask.id.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": row.id,
            "task_type": row.task_type,
            "status": row.status,
            "progress": row.progress,
            "message": row.message,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


@router.get("/documents/{document_id}/revisions")
def document_revisions(document_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return [
        {
            "id": row.id,
            "version": row.version,
            "note": row.note,
            "created_at": row.created_at,
            "preview": row.content[:300],
        }
        for row in list_document_revisions(db, document_id)
    ]


@router.post("/documents/{document_id}/revisions/{revision_id}/restore")
def restore_revision(document_id: int, revision_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    try:
        restore_document_revision(db, document, revision_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.refresh(document)
    return _document_detail_payload(db, document)


@router.post("/documents/{document_id}/optimize")
def document_optimize(document_id: int, payload: dict | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    from app.services.ai_service import optimize_document

    try:
        return optimize_document(db, document_id, (payload or {}).get("instruction"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    delete_document_fts(db, document_id)
    delete_document_files(document_id)
    db.delete(document)
    db.commit()
    return {"ok": True}
