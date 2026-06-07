import json

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import AppSetting, ChatHistory, Document
from app.services.document_service import search_chunks

def _resolve_llm(db: Session, prefix: str) -> dict:
    """解析 LLM 配置：数据库优先，env 兜底."""
    env = get_settings()
    keys = [f"{prefix}_api_key", f"{prefix}_base_url", f"{prefix}_model", f"{prefix}_vision_model"]
    db_cfg = {}
    for row in db.query(AppSetting).filter(AppSetting.key.in_(keys)).all():
        db_cfg[row.key] = row.value
    return {
        "api_key": db_cfg.get(f"{prefix}_api_key") or env.openai_api_key,
        "base_url": db_cfg.get(f"{prefix}_base_url") or env.openai_base_url or None,
        "model": db_cfg.get(f"{prefix}_model") or env.openai_model,
        "vision_model": db_cfg.get(f"{prefix}_vision_model") or env.openai_vision_model or None,
    }


def build_reference_payload(chunks) -> list[dict]:
    return [
        {
            "document_id": chunk.document_id,
            "source": chunk.source,
            "content": chunk.content[:240],
        }
        for chunk in chunks
    ]


def _recent_history(db: Session, project: str, session_id: str, limit: int = 6) -> list[ChatHistory]:
    rows = (
        db.query(ChatHistory)
        .filter(ChatHistory.project == project, ChatHistory.session_id == session_id)
        .order_by(ChatHistory.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def answer_question(db: Session, project: str, question: str, session_id: str) -> dict:
    llm = _resolve_llm(db, "chat")
    chunks = search_chunks(db, project, question)
    references = build_reference_payload(chunks)
    context = "\n\n".join(f"[{idx + 1}] {chunk.source}\n{chunk.content}" for idx, chunk in enumerate(chunks))
    history = _recent_history(db, project, session_id)
    history_text = "\n".join(
        f"用户: {item.question}\n助手: {(item.answer or '')[:800]}"
        for item in history
    )
    mode = "local-openclaw"

    try:
        from app.services.agent_service import _call_openclaw_runtime, _resolve_agent_runtime

        runtime = _resolve_agent_runtime(db)
        if runtime.get("runtime") == "openclaw":
            payload = {
                "agent": runtime.get("agent") or "main",
                "project": project,
                "session_id": session_id,
                "goal": question,
                "response_format": "knowledge_agent_answer",
                "openclaw_timeout": 120,
                "history": history_text or "无",
                "context": {
                    "question": question,
                    "project": project,
                    "knowledge_context": context or "无匹配片段",
                    "references": references,
                    "answer_policy": [
                        "只基于 SmartOpsDocs 提供的知识库片段和当前会话历史回答。",
                        "如果知识库没有证据，直接说明缺少依据，并给出下一步检索建议。",
                        "回答末尾列出引用来源编号。",
                    ],
                },
                "tool_calls": [],
                "references": references,
                "policy": {
                    "source": "SmartOpsDocs knowledge agent",
                    "external_data_is_untrusted": True,
                    "do_not_fabricate": True,
                },
            }
            answer, mode = _call_openclaw_runtime(runtime, payload)
    except Exception as exc:
        answer = f"OpenClaw 知识库智能体调用失败: {exc}\n\n已检索到的上下文片段:\n{context or '无匹配片段'}"
        mode = "local-openclaw-fallback"
        history = ChatHistory(
            session_id=session_id,
            project=project,
            question=question,
            answer=answer,
            references=json.dumps(references, ensure_ascii=False),
        )
        db.add(history)
        db.commit()
        return {"answer": answer, "references": references, "mode": mode}
    else:
        if mode == "openclaw-gateway":
            history = ChatHistory(
                session_id=session_id,
                project=project,
                question=question,
                answer=answer,
                references=json.dumps(references, ensure_ascii=False),
            )
            db.add(history)
            db.commit()
            return {"answer": answer, "references": references, "mode": mode}

    if llm["api_key"]:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=llm["api_key"], base_url=llm["base_url"])
            completion = client.chat.completions.create(
                model=llm["model"],
                messages=[
                    {
                        "role": "system",
                        "content": "你是运维助手。只基于给定上下文回答，无法确认时直接说明，并在回答末尾列出引用来源编号。",
                    },
                    {
                        "role": "user",
                        "content": (
                            f"历史对话摘要:\n{history_text or '无'}\n\n"
                            f"知识库上下文:\n{context or '无'}\n\n"
                            f"当前问题: {question}"
                        ),
                    },
                ],
            )
            answer = completion.choices[0].message.content or ""
        except Exception as exc:
            answer = f"AI 调用失败: {exc}\n\n已检索到的上下文片段:\n{context or '无匹配片段'}"
    else:
        answer = "当前未配置大模型 API Key，请先在模型设置中配置。\n\n"
        answer += context or "没有找到相关文档片段。"

    history = ChatHistory(
        session_id=session_id,
        project=project,
        question=question,
        answer=answer,
        references=json.dumps(references, ensure_ascii=False),
    )
    db.add(history)
    db.commit()
    return {"answer": answer, "references": references, "mode": mode}


def optimize_document(db: Session, document_id: int, instruction: str | None = None) -> dict:
    llm = _resolve_llm(db, "optimize")
    document = db.get(Document, document_id)
    if not document:
        raise ValueError("文档不存在")
    chunks = sorted(document.chunks, key=lambda item: item.chunk_index)
    raw_text = "\n\n".join(chunk.content for chunk in chunks).strip()
    if not raw_text:
        raise ValueError("文档还没有解析内容")

    source_text = raw_text[:12000]
    instruction = instruction or "整理为清晰的运维知识库文档，保留关键命令、配置、排障步骤和注意事项。"
    prompt = f"""请优化下面的运维文档，输出 Markdown。

要求：
1. 不要编造原文没有的信息。
2. 保留 IP、端口、命令、配置项、路径、错误信息。
3. 按「适用场景、前置条件、操作步骤、验证方法、常见问题、注意事项」组织。
4. 对含糊表述做措辞优化，但不要改变技术含义。
5. 如果原文信息不足，在对应小节写「原文未提供」。

用户补充要求：
{instruction}

原文：
{source_text}
"""

    if llm["api_key"]:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=llm["api_key"], base_url=llm["base_url"])
            completion = client.chat.completions.create(
                model=llm["model"],
                messages=[
                    {"role": "system", "content": "你是资深 SRE 文档工程师，擅长把零散运维记录整理成可执行 Runbook。"},
                    {"role": "user", "content": prompt},
                ],
            )
            optimized = completion.choices[0].message.content or ""
            return {"optimized": optimized, "mode": "llm", "source_length": len(raw_text)}
        except Exception as exc:
            fallback = _local_document_outline(document.title, raw_text)
            return {"optimized": f"AI 调用失败: {exc}\n\n{fallback}", "mode": "fallback", "source_length": len(raw_text)}

    return {"optimized": _local_document_outline(document.title, raw_text), "mode": "local", "source_length": len(raw_text)}


def _local_document_outline(title: str, raw_text: str) -> str:
    preview = raw_text[:6000]
    return f"""# {title}

## 适用场景

原文未提供明确场景，请根据下面内容人工补充。

## 前置条件

原文未提供明确前置条件。

## 操作步骤

{preview}

## 验证方法

原文未提供明确验证方法。

## 常见问题

原文未提供明确常见问题。

## 注意事项

- 本内容为本地格式化草稿，未配置大模型 API Key，因此未经过大模型润色。
- 建议人工检查命令、路径、IP、端口和环境名称后再作为正式文档使用。
"""
