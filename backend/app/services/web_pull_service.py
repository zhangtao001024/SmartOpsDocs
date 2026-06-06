from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.models.entities import AppSetting, Document
from app.services.document_service import (
    document_markdown_path,
    document_workspace,
    rebuild_document_chunks,
    create_document_revision,
    update_document_task,
)
from app.core.config import get_settings


class PageTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.parts: list[str] = []
        self._skip = 0
        self._in_title = False
        self._block = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg", "canvas"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "tr", "pre", "blockquote"}:
            self._block = True
        if tag in {"h1", "h2", "h3", "h4"}:
            level = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}[tag]
            self.parts.append(f"\n{level} ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "canvas"} and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "tr", "pre", "blockquote"}:
            self.parts.append("\n")
            self._block = False

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
            return
        if self._skip:
            return
        prefix = "\n" if self._block and self.parts and not self.parts[-1].endswith(("\n", " ")) else ""
        self.parts.append(f"{prefix}{text} ")

    @property
    def text(self) -> str:
        lines = []
        for line in "".join(self.parts).splitlines():
            clean = " ".join(line.split())
            if clean:
                lines.append(clean)
        return "\n".join(lines)


def _resolve_pull_llm(db: Session) -> dict:
    env = get_settings()
    keys = ["pull_api_key", "pull_base_url", "pull_model", "pull_vision_model"]
    db_cfg = {}
    for row in db.query(AppSetting).filter(AppSetting.key.in_(keys)).all():
        db_cfg[row.key] = row.value
    return {
        "api_key": db_cfg.get("pull_api_key") or env.openai_api_key,
        "base_url": db_cfg.get("pull_base_url") or env.openai_base_url or None,
        "model": db_cfg.get("pull_model") or env.openai_model,
    }


def fetch_webpage(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("只支持 http/https URL")
    request = Request(
        url,
        headers={
            "User-Agent": "SmartOpsDocs/0.1 (+https://github.com/zhangtao001024/SmartOpsDocs)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=25) as response:
        content_type = response.headers.get("content-type", "")
        charset = response.headers.get_content_charset() or "utf-8"
        raw = response.read(3 * 1024 * 1024)
    if "html" not in content_type.lower():
        raise ValueError(f"目标不是 HTML 页面: {content_type or 'unknown'}")
    parser = PageTextParser()
    parser.feed(raw.decode(charset, errors="ignore"))
    return {"title": parser.title or parsed.netloc, "text": parser.text}


def build_web_markdown(db: Session, url: str, title: str, text: str, instruction: str = "") -> tuple[str, str]:
    source_text = text[:30000]
    llm = _resolve_pull_llm(db)
    prompt = f"""请把下面网页内容整理成适合运维知识库的 Markdown。

要求：
1. 保留原文中的技术名词、命令、配置项、URL、表格信息和层级标题。
2. 删除导航、版权、广告、重复目录等噪声。
3. 不要编造原文没有的信息。
4. 结构尽量清晰，适合后续 RAG 检索。
5. 在末尾保留来源 URL。

用户补充要求：
{instruction or "无"}

标题：{title}
来源：{url}

网页正文：
{source_text}
"""
    if llm["api_key"]:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=llm["api_key"], base_url=llm["base_url"])
            completion = client.chat.completions.create(
                model=llm["model"],
                messages=[
                    {"role": "system", "content": "你是知识库采集器，擅长把网页内容清洗整理成准确、可检索的 Markdown。"},
                    {"role": "user", "content": prompt},
                ],
            )
            return completion.choices[0].message.content or "", "llm"
        except Exception as exc:
            fallback = _fallback_web_markdown(url, title, source_text)
            return f"<!-- LLM 拉取失败: {exc} -->\n\n{fallback}", "fallback"
    return _fallback_web_markdown(url, title, source_text), "local"


def _fallback_web_markdown(url: str, title: str, text: str) -> str:
    return f"""# {title}

> 来源：{url}

{text}
"""


def process_web_pull(db: Session, document_id: int, url: str, instruction: str = "", task_id: int | None = None) -> None:
    document = db.get(Document, document_id)
    if not document:
        return
    try:
        update_document_task(db, task_id, "running", 10, "开始抓取网页")
        document.status = "parsing"
        db.commit()
        page = fetch_webpage(url)
        document.title = page["title"]
        update_document_task(db, task_id, "running", 45, "整理网页内容")
        markdown, mode = build_web_markdown(db, url, page["title"], page["text"], instruction)
        workspace = document_workspace(document_id)
        workspace.mkdir(parents=True, exist_ok=True)
        document_markdown_path(document_id).write_text(markdown, encoding="utf-8")
        update_document_task(db, task_id, "running", 80, "重建知识库索引")
        rebuild_document_chunks(db, document, markdown)
        create_document_revision(db, document, markdown, note=f"web-pull:{mode}")
        document.status = "completed"
        document.error_message = ""
        update_document_task(db, task_id, "completed", 100, "网页拉取完成")
    except Exception as exc:
        document.status = "failed"
        document.error_message = str(exc)
        update_document_task(db, task_id, "failed", 100, str(exc))
    finally:
        db.commit()
