"""AI 问答路由."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import User
from app.schemas.dto import AgentRequest, AgentResponse, ChatRequest, ChatResponse
from app.services.agent_service import list_agent_tools, run_agent
from app.services.ai_service import answer_question

router = APIRouter(prefix="/api", tags=["ai"])


@router.post("/ai/chat", response_model=ChatResponse)
def ai_chat(payload: ChatRequest, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return answer_question(db, payload.project, payload.question, payload.session_id)


@router.get("/ai/agent/tools")
def ai_agent_tools(_: User = Depends(current_user)):
    return list_agent_tools()


@router.post("/ai/agent", response_model=AgentResponse)
def ai_agent(payload: AgentRequest, db: Session = Depends(get_db), _: User = Depends(current_user)):
    goal = payload.goal.strip()
    if not goal:
        raise HTTPException(status_code=400, detail="目标不能为空")
    return run_agent(
        db,
        project=payload.project,
        goal=goal,
        session_id=payload.session_id,
        tools=payload.tools,
        dry_run=payload.dry_run,
        context=payload.context,
    )


@router.post("/ai/chat/stream")
def ai_chat_stream(payload: ChatRequest, db: Session = Depends(get_db), _: User = Depends(current_user)):
    result = answer_question(db, payload.project, payload.question, payload.session_id)

    def emit():
        for line in result["answer"].splitlines():
            yield f"data: {line}\n\n"
        yield f"data: 引用: {result['references']}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(emit(), media_type="text/event-stream")
