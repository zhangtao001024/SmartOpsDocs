import base64
from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
import io
import mimetypes
import re
import shutil
from pathlib import Path
from urllib.parse import unquote_to_bytes, urljoin, urlparse
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.models.entities import AppSetting, Document
from app.services.document_service import (
    document_assets_dir,
    document_markdown_path,
    document_workspace,
    image_text_for_markdown,
    rebuild_document_chunks,
    create_document_revision,
    update_document_task,
)
from app.core.config import get_settings
from app.services.prompts import build_web_pull_prompt, web_pull_contract, web_pull_system_prompt


WEB_USER_AGENT = "SmartOpsDocs/0.1 (+https://github.com/zhangtao001024/SmartOpsDocs)"
MAX_WEBPAGE_BYTES = 5 * 1024 * 1024
MAX_WEB_IMAGES = 20
MAX_WEB_IMAGE_BYTES = 5 * 1024 * 1024
MAX_WEB_IMAGE_TOTAL_BYTES = 30 * 1024 * 1024
MIN_WEB_IMAGE_WIDTH = 120
MIN_WEB_IMAGE_HEIGHT = 80
WEB_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}


WEB_NOISE_PATTERNS = (
    r"^首页$",
    r"^登录$",
    r"^注册$",
    r"^搜索$",
    r"^菜单$",
    r"^导航$",
    r"^目录$",
    r"^上一页$",
    r"^下一页$",
    r"^上一篇$",
    r"^下一篇$",
    r"^返回顶部$",
    r"分享",
    r"评论",
    r"广告",
    r"赞助",
    r"cookie",
    r"copyright",
    r"版权所有",
    r"相关推荐",
    r"相关文章",
    r"热门文章",
    r"关注我们",
    r"订阅",
    r"newsletter",
)

WEB_KNOWLEDGE_SECTION_PATTERNS = (
    r"^##\s+摘要\b",
    r"^##\s+适用场景\b",
    r"^##\s+关键概念与组件职责\b",
    r"^##\s+(操作步骤\s*/\s*配置\s*/\s*命令|操作步骤.*命令|配置.*命令)\b",
    r"^##\s+排障线索与注意事项\b",
    r"^##\s+可检索关键词\b",
)

WEB_REPORT_PATTERNS = (
    r"^##\s*任务结论\b",
    r"^#+\s*输出文件\b",
    r"站点规模\s*[:：]",
    r"访问方式\s*[:：]",
    r"草稿建议",
    r"如果想继续完善",
)

WEB_IMAGE_NOISE_PATTERNS = (
    r"logo",
    r"avatar",
    r"icon",
    r"sprite",
    r"favicon",
    r"banner",
    r"ads?",
    r"tracking",
    r"analytics",
    r"pixel",
    r"beacon",
    r"share",
    r"social",
    r"wechat",
    r"weixin",
    r"qrcode",
)


@dataclass(frozen=True)
class WebImageCandidate:
    url: str
    alt: str
    caption: str
    order: int


@dataclass(frozen=True)
class WebImageAsset:
    source_url: str
    asset_name: str
    alt: str
    caption: str
    image_text: str
    width: int
    height: int


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
            "User-Agent": WEB_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=25) as response:
        content_type = response.headers.get("content-type", "")
        charset = response.headers.get_content_charset() or "utf-8"
        raw = response.read(MAX_WEBPAGE_BYTES)
    if "html" not in content_type.lower():
        raise ValueError(f"目标不是 HTML 页面: {content_type or 'unknown'}")
    html = raw.decode(charset, errors="ignore")
    return _extract_main_web_content(html, url, parsed.netloc)


def _extract_main_web_content(html: str, url: str, fallback_title: str) -> dict:
    images = _extract_web_image_candidates(html, url)
    article_markdown = _extract_article_markdown_with_remote_images(html, url)
    try:
        from trafilatura import extract
        from trafilatura.metadata import extract_metadata

        markdown = extract(
            html,
            url=url,
            output_format="markdown",
            include_comments=False,
            include_links=True,
            include_tables=True,
            favor_precision=True,
        )
        metadata = extract_metadata(html, default_url=url)
        title = getattr(metadata, "title", "") if metadata else ""
        if markdown and markdown.strip():
            return {
                "title": title or fallback_title,
                "text": markdown.strip(),
                "images": images,
                "article_markdown": article_markdown,
                "html": html,
            }
    except Exception:
        pass

    parser = PageTextParser()
    parser.feed(html)
    return {
        "title": parser.title or fallback_title,
        "text": parser.text,
        "images": images,
        "article_markdown": article_markdown,
        "html": html,
    }


def _parse_html_root(html: str):
    try:
        from lxml import html as lxml_html
    except ImportError:
        return None
    try:
        return lxml_html.fromstring(html)
    except Exception:
        return None


def _main_content_node(root):
    selectors = (
        "//article",
        "//main",
        "//*[contains(concat(' ', translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), ' '), ' markdown ')]",
        "//*[contains(concat(' ', translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), ' '), ' content ')]",
        "//*[contains(concat(' ', translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), ' '), ' doc ')]",
        "//*[contains(concat(' ', translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), ' '), ' post ')]",
        "//*[contains(concat(' ', translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), ' '), ' article ')]",
        "//*[contains(concat(' ', translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), ' '), ' content ')]",
        "//body",
    )
    best = None
    best_score = -1
    for selector in selectors:
        for node in root.xpath(selector):
            text = _clean_inline_text(node.text_content() if hasattr(node, "text_content") else "")
            images = len(node.xpath(".//img")) if hasattr(node, "xpath") else 0
            score = len(text) + images * 500
            if score > best_score:
                best = node
                best_score = score
        if best is not None and best_score > 200:
            return best
    return best if best is not None else root


def _extract_web_image_candidates(html: str, url: str) -> list[WebImageCandidate]:
    root = _parse_html_root(html)
    if root is None:
        return []
    main = _main_content_node(root)
    candidates: list[WebImageCandidate] = []
    seen: set[str] = set()
    for order, img in enumerate(main.xpath(".//img"), start=1):
        image_url = _image_url_from_node(img, url)
        if not image_url or image_url in seen:
            continue
        alt = _clean_inline_text(
            img.get("alt")
            or img.get("title")
            or img.get("aria-label")
            or ""
        )
        caption = _image_caption(img)
        if _is_noise_image_node(img, image_url, alt, caption):
            continue
        seen.add(image_url)
        candidates.append(WebImageCandidate(url=image_url, alt=alt, caption=caption, order=order))
        if len(candidates) >= MAX_WEB_IMAGES * 2:
            break
    return candidates


def _extract_article_markdown_with_remote_images(html: str, url: str) -> str:
    root = _parse_html_root(html)
    if root is None:
        return ""
    main = _main_content_node(root)
    blocks: list[str] = []
    seen_blocks: set[str] = set()
    seen_images: set[str] = set()

    def add_block(text: str) -> None:
        clean = text.strip()
        if not clean:
            return
        fingerprint = re.sub(r"\s+", " ", clean).lower()
        if fingerprint in seen_blocks:
            return
        seen_blocks.add(fingerprint)
        blocks.append(clean)

    def walk(node) -> None:
        tag = _node_tag(node)
        if not tag or tag in {"script", "style", "noscript", "svg", "canvas", "nav", "footer", "header", "form", "button"}:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            text = _clean_inline_text(node.text_content())
            if text:
                level = min(max(int(tag[1]), 1), 4)
                add_block(f"{'#' * level} {text.lstrip('#').strip()}")
            return
        if tag == "img":
            image_url = _image_url_from_node(node, url)
            alt = _clean_inline_text(node.get("alt") or node.get("title") or "网页截图")
            caption = _image_caption(node)
            if image_url and image_url not in seen_images and not _is_noise_image_node(node, image_url, alt, caption):
                seen_images.add(image_url)
                add_block(f"![{_escape_markdown_alt(alt or caption or '网页截图')}]({image_url})")
                if caption:
                    add_block(f"> 图片说明：{caption}")
            return
        if tag == "pre":
            code = (node.text_content() or "").strip()
            if code:
                add_block(f"```\n{code}\n```")
            return
        if tag == "table":
            table_markdown = _table_node_to_markdown(node)
            if table_markdown:
                add_block(table_markdown)
            return
        if tag in {"ul", "ol"}:
            ordered = tag == "ol"
            for item in node.xpath("./li"):
                text = _clean_inline_text(_text_without_child_blocks(item))
                if text:
                    add_block(f"{'1.' if ordered else '-'} {text}")
                for child in item:
                    if _node_tag(child) in {"img", "figure", "picture", "pre", "table", "ul", "ol"}:
                        walk(child)
            return
        if tag in {"p", "blockquote", "figcaption"}:
            text = _clean_inline_text(_text_without_child_blocks(node))
            if text:
                prefix = "> " if tag in {"blockquote", "figcaption"} else ""
                add_block(f"{prefix}{text}")
            for child in node:
                if _node_tag(child) in {"img", "picture", "figure"}:
                    walk(child)
            return

        children = list(node)
        if not children:
            text = _clean_inline_text(node.text_content() or "")
            if text:
                add_block(text)
            return
        for child in children:
            walk(child)

    walk(main)
    return "\n\n".join(blocks).strip()


def _node_tag(node) -> str:
    tag = getattr(node, "tag", "")
    return tag.lower() if isinstance(tag, str) else ""


def _text_without_child_blocks(node) -> str:
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        tag = _node_tag(child)
        if tag not in {"img", "figure", "picture", "pre", "table", "ul", "ol"}:
            if hasattr(child, "text_content"):
                parts.append(child.text_content())
        if child.tail:
            parts.append(child.tail)
    return " ".join(parts)


def _table_node_to_markdown(node) -> str:
    rows = []
    for row in node.xpath(".//tr"):
        cells = [
            _clean_inline_text(cell.text_content()).replace("|", "\\|")
            for cell in row.xpath("./th|./td")
        ]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    separator = ["---"] * width
    body = normalized[1:]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(separator) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def _image_url_from_node(img, base_url: str) -> str:
    for attr in ("srcset", "data-srcset", "data-original-set"):
        candidate = _best_srcset_candidate(img.get(attr) or "")
        if candidate:
            return _absolute_image_url(candidate, base_url)
    for attr in ("src", "data-src", "data-original", "data-lazy-src", "data-url", "data-image"):
        value = (img.get(attr) or "").strip()
        if value:
            return _absolute_image_url(value, base_url)
    return ""


def _best_srcset_candidate(srcset: str) -> str:
    choices = []
    for raw_part in srcset.split(","):
        part = raw_part.strip()
        if not part:
            continue
        pieces = part.split()
        image_url = pieces[0].strip()
        score = 1.0
        if len(pieces) > 1:
            descriptor = pieces[1].strip().lower()
            try:
                if descriptor.endswith("w"):
                    score = float(descriptor[:-1])
                elif descriptor.endswith("x"):
                    score = float(descriptor[:-1]) * 1000
            except ValueError:
                score = 1.0
        choices.append((score, image_url))
    if not choices:
        return ""
    choices.sort(key=lambda item: item[0], reverse=True)
    return choices[0][1]


def _absolute_image_url(value: str, base_url: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("data:image/"):
        return value
    absolute = urljoin(base_url, value)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return absolute


def _image_caption(img) -> str:
    parent = img.getparent()
    for _ in range(4):
        if parent is None:
            break
        if _node_tag(parent) == "figure":
            captions = [
                _clean_inline_text(node.text_content())
                for node in parent.xpath(".//figcaption")
            ]
            return " ".join(caption for caption in captions if caption).strip()
        parent = parent.getparent()
    sibling = img.getnext()
    if sibling is not None and _node_tag(sibling) in {"figcaption", "caption"}:
        return _clean_inline_text(sibling.text_content())
    return ""


def _is_noise_image_node(img, image_url: str, alt: str, caption: str) -> bool:
    if (img.get("role") or "").lower() == "presentation" or (img.get("aria-hidden") or "").lower() == "true":
        return True
    if _has_ignored_image_ancestor(img):
        return True
    width = _int_attr(img.get("width"))
    height = _int_attr(img.get("height"))
    if width and height and (width < MIN_WEB_IMAGE_WIDTH or height < MIN_WEB_IMAGE_HEIGHT):
        return True
    parsed = urlparse(image_url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".svg", ".ico"}:
        return True
    if suffix and suffix not in WEB_IMAGE_EXTENSIONS and not image_url.startswith("data:image/"):
        return True
    descriptor = " ".join([parsed.path.lower(), parsed.query.lower(), alt.lower(), caption.lower()])
    has_meaningful_text = len((alt + caption).strip()) >= 10
    return any(re.search(pattern, descriptor) for pattern in WEB_IMAGE_NOISE_PATTERNS) and not has_meaningful_text


def _has_ignored_image_ancestor(node) -> bool:
    parent = node.getparent()
    ignored = {"nav", "footer", "header", "aside"}
    while parent is not None:
        tag = _node_tag(parent)
        if tag in ignored:
            return True
        attrs = " ".join(str(parent.get(name) or "").lower() for name in ("class", "id", "role"))
        if re.search(r"\b(nav|menu|footer|header|sidebar|share|social|comment|advert|ads?)\b", attrs):
            return True
        parent = parent.getparent()
    return False


def _int_attr(value: str | None) -> int:
    if not value:
        return 0
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else 0


def _clean_inline_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def _escape_markdown_alt(text: str) -> str:
    return text.replace("]", "\\]").replace("\n", " ").strip()


def _prepare_web_source_markdown(db: Session | None, document_id: int, page: dict) -> tuple[str, list[WebImageAsset]]:
    candidates = page.get("images") or []
    assets_dir = document_assets_dir(document_id)
    shutil.rmtree(assets_dir, ignore_errors=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    image_assets = _download_web_image_assets(db, assets_dir, candidates)
    source = (page.get("article_markdown") or page.get("text") or "").strip()
    if image_assets:
        source = _replace_remote_images_with_assets(source, image_assets)
    if not source:
        source = (page.get("text") or "").strip()
    return source, image_assets


def _download_web_image_assets(
    db: Session | None,
    assets_dir: Path,
    candidates: list[WebImageCandidate],
) -> list[WebImageAsset]:
    assets: list[WebImageAsset] = []
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    total_bytes = 0
    image_state = {"index": 0, "vision_used": 0}

    for candidate in sorted(candidates, key=lambda item: item.order):
        if candidate.url in seen_urls or len(assets) >= MAX_WEB_IMAGES:
            continue
        seen_urls.add(candidate.url)
        image_payload = _read_web_image(candidate.url)
        if not image_payload:
            continue
        image_bytes, content_type = image_payload
        if len(image_bytes) > MAX_WEB_IMAGE_BYTES or total_bytes + len(image_bytes) > MAX_WEB_IMAGE_TOTAL_BYTES:
            continue
        image_info = _web_image_info(image_bytes, content_type, candidate.url)
        if not image_info:
            continue
        width, height, ext = image_info
        if width < MIN_WEB_IMAGE_WIDTH or height < MIN_WEB_IMAGE_HEIGHT:
            continue
        digest = hashlib.sha256(image_bytes).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        image_index = len(assets) + 1
        asset_name = f"web-image-{image_index:03d}{ext}"
        (assets_dir / asset_name).write_bytes(image_bytes)
        image_state["index"] = image_index
        image_text = image_text_for_markdown(asset_name, image_bytes, image_state, db)
        assets.append(
            WebImageAsset(
                source_url=candidate.url,
                asset_name=asset_name,
                alt=candidate.alt,
                caption=candidate.caption,
                image_text=image_text,
                width=width,
                height=height,
            )
        )
        total_bytes += len(image_bytes)
    return assets


def _read_web_image(image_url: str) -> tuple[bytes, str] | None:
    if image_url.startswith("data:image/"):
        return _read_data_image(image_url)
    request = Request(
        image_url,
        headers={
            "User-Agent": WEB_USER_AGENT,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=25) as response:
            content_type = (response.headers.get("content-type") or "").split(";", 1)[0].lower()
            content_length = _int_attr(response.headers.get("content-length"))
            if content_length and content_length > MAX_WEB_IMAGE_BYTES:
                return None
            if content_type and not content_type.startswith("image/"):
                return None
            image_bytes = response.read(MAX_WEB_IMAGE_BYTES + 1)
    except Exception:
        return None
    if not image_bytes or len(image_bytes) > MAX_WEB_IMAGE_BYTES:
        return None
    return image_bytes, content_type


def _read_data_image(data_url: str) -> tuple[bytes, str] | None:
    try:
        header, payload = data_url.split(",", 1)
    except ValueError:
        return None
    content_type = header.split(";", 1)[0].removeprefix("data:").lower()
    if not content_type.startswith("image/"):
        return None
    try:
        if ";base64" in header.lower():
            image_bytes = base64.b64decode(payload, validate=True)
        else:
            image_bytes = unquote_to_bytes(payload)
    except Exception:
        return None
    if not image_bytes or len(image_bytes) > MAX_WEB_IMAGE_BYTES:
        return None
    return image_bytes, content_type


def _web_image_info(image_bytes: bytes, content_type: str, source_url: str) -> tuple[int, int, str] | None:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as image:
            width, height = image.size
            image_format = (image.format or "").lower()
    except Exception:
        return None
    ext = _web_image_extension(image_format, content_type, source_url)
    if ext not in WEB_IMAGE_EXTENSIONS:
        return None
    return width, height, ext


def _web_image_extension(image_format: str, content_type: str, source_url: str) -> str:
    format_map = {
        "jpeg": ".jpg",
        "jpg": ".jpg",
        "png": ".png",
        "gif": ".gif",
        "bmp": ".bmp",
        "webp": ".webp",
        "tiff": ".tiff",
    }
    if image_format in format_map:
        return format_map[image_format]
    mime_ext = mimetypes.guess_extension(content_type or "")
    if mime_ext == ".jpe":
        mime_ext = ".jpg"
    if mime_ext in WEB_IMAGE_EXTENSIONS:
        return mime_ext
    url_ext = Path(urlparse(source_url).path).suffix.lower()
    if url_ext == ".jpeg":
        return ".jpg"
    return url_ext if url_ext in WEB_IMAGE_EXTENSIONS else ".png"


def _replace_remote_images_with_assets(source: str, image_assets: list[WebImageAsset]) -> str:
    content = source.strip()
    used_asset_names: set[str] = set()
    for index, asset in enumerate(image_assets, start=1):
        replacement = _web_image_asset_markdown(asset, index)
        pattern = re.compile(r"!\[([^\]]*)\]\(" + re.escape(asset.source_url) + r"\)")
        content, count = pattern.subn(replacement, content, count=1)
        if count:
            used_asset_names.add(asset.asset_name)
    missing_assets = [asset for asset in image_assets if asset.asset_name not in used_asset_names]
    if missing_assets:
        section_blocks = [
            _web_image_asset_markdown(asset, image_assets.index(asset) + 1)
            for asset in missing_assets
        ]
        content = f"{content.rstrip()}\n\n## 图文教程截图与识别文本\n\n" + "\n\n".join(section_blocks)
    return content.strip()


def _web_image_asset_markdown(asset: WebImageAsset, index: int) -> str:
    alt = _escape_markdown_alt(asset.alt or asset.caption or f"网页教程截图 {index}")
    lines = [f"![{alt}](assets/{asset.asset_name})"]
    summary_parts = []
    if asset.alt:
        summary_parts.append(asset.alt)
    if asset.caption and asset.caption not in summary_parts:
        summary_parts.append(asset.caption)
    if summary_parts:
        lines.append(f"> 图片说明：{'；'.join(summary_parts)}")
    lines.append(f"> 图片尺寸：{asset.width}x{asset.height}")
    if asset.image_text:
        lines.append(f"**图片识别文本：**\n\n{asset.image_text.strip()}")
    return "\n\n".join(lines)


def _ensure_web_images_preserved(markdown: str, image_assets: list[WebImageAsset] | None) -> str:
    if not image_assets:
        return markdown
    missing = [asset for asset in image_assets if f"(assets/{asset.asset_name})" not in markdown]
    if not missing:
        return markdown
    blocks = [
        _web_image_asset_markdown(asset, image_assets.index(asset) + 1)
        for asset in missing
    ]
    section = "\n\n## 图文教程截图与识别文本\n\n" + "\n\n".join(blocks) + "\n"
    keyword_match = re.search(r"\n##\s+可检索关键词\b", markdown)
    if keyword_match:
        return f"{markdown[:keyword_match.start()].rstrip()}{section}{markdown[keyword_match.start():].lstrip()}"
    return f"{markdown.rstrip()}{section}"


def build_web_markdown(
    db: Session,
    url: str,
    title: str,
    text: str,
    instruction: str = "",
    image_assets: list[WebImageAsset] | None = None,
) -> tuple[str, str]:
    source_text = _valuable_web_text(text)[:30000]
    openclaw_markdown, openclaw_mode = _build_web_markdown_with_openclaw(
        db,
        url,
        title,
        source_text,
        instruction,
        image_assets,
    )
    if openclaw_markdown:
        return _ensure_web_images_preserved(openclaw_markdown, image_assets), openclaw_mode
    llm = _resolve_pull_llm(db)
    prompt = build_web_pull_prompt(url, title, source_text, instruction, bool(image_assets))
    if llm["api_key"]:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=llm["api_key"], base_url=llm["base_url"])
            completion = client.chat.completions.create(
                model=llm["model"],
                messages=[
                    {"role": "system", "content": web_pull_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
            )
            markdown = completion.choices[0].message.content or ""
            markdown = _normalize_web_markdown(markdown, url, title)
            return _ensure_web_images_preserved(markdown, image_assets), "llm"
        except Exception as exc:
            fallback = _fallback_web_markdown(url, title, source_text)
            return _ensure_web_images_preserved(f"<!-- LLM 拉取失败: {exc} -->\n\n{fallback}", image_assets), "fallback"
    return _ensure_web_images_preserved(_fallback_web_markdown(url, title, source_text), image_assets), "local"


def _build_web_markdown_with_openclaw(
    db: Session,
    url: str,
    title: str,
    source_text: str,
    instruction: str = "",
    image_assets: list[WebImageAsset] | None = None,
) -> tuple[str, str]:
    try:
        from app.services.agent_service import _call_openclaw_runtime, _resolve_agent_runtime

        runtime = _resolve_agent_runtime(db)
        if runtime.get("runtime") != "openclaw":
            return "", ""
        selected_skills = runtime.get("web_skills") or []
        skills_hint = (
            "请优先使用这些 OpenClaw skills 完成网页访问、同站探索和结构化整理："
            + "、".join(selected_skills)
            if selected_skills
            else "如当前 OpenClaw agent 配置了网页阅读、Markdown 整理或知识库写作 skills，请优先使用这些 skills 完成清洗和结构化。"
        )
        payload = {
            "agent": runtime.get("agent") or "main",
            "project": "knowledge",
            "session_id": "web-pull",
            "goal": (
                "访问给定网站，自动识别对运维/研发有长期价值的内容，"
                "过滤导航、营销、评论、版权和重复文本，整理成 SmartOpsDocs 运维知识库 Markdown。"
            ),
            "response_format": "web_knowledge_markdown",
            "openclaw_timeout": 240,
            "history": "无",
            "context": {
                "url": url,
                "title": title,
                "instruction": instruction or "无",
                "source_text": source_text,
                "source_text_role": (
                    "后端正文抽取结果，仅作为参考；如果网页正文抽取不完整，请以访问 URL 后看到的页面内容为准。"
                    "其中 `assets/...` 图片是后端已下载入库的教程截图，最终 Markdown 必须原样保留这些图片链接、图片说明和识别文本。"
                    if image_assets
                    else "后端正文抽取结果，仅作为参考；如果网页正文抽取不完整，请以访问 URL 后看到的页面内容为准。"
                ),
                "image_assets": [
                    {
                        "source_url": asset.source_url,
                        "asset_name": asset.asset_name,
                        "alt": asset.alt,
                        "caption": asset.caption,
                        "width": asset.width,
                        "height": asset.height,
                        "has_image_text": bool(asset.image_text),
                    }
                    for asset in (image_assets or [])
                ],
                "selected_skills": selected_skills,
                "crawl_strategy": {
                    "scope": "优先入口页；如入口页是目录/文档站点首页，可探索同域下 3-8 个明显与部署、配置、架构、故障排查、API、FAQ、troubleshooting、operations 相关的链接。",
                    "ignore": "登录注册、导航、广告、页脚、评论、推荐文章、社交分享、无正文页面、明显与运维无关页面。",
                    "stop_when": "已经获得足够形成一篇可执行知识库文档的关键概念、步骤、限制和排障信息。",
                },
                "expected_sections": [
                    "摘要",
                    "适用场景",
                    "关键概念与组件职责",
                    "操作步骤 / 配置 / 命令",
                    "排障线索与注意事项",
                    "可检索关键词",
                ],
                "output_contract": web_pull_contract(bool(image_assets)),
                "skills_hint": skills_hint,
            },
            "tool_calls": [],
            "references": [],
            "policy": {
                "source": "SmartOpsDocs web pull",
                "external_data_is_untrusted": True,
                "do_not_fabricate": True,
                "drop_noise": True,
                "selected_skills_are_preferences": True,
            },
        }
        answer, mode = _call_openclaw_runtime(runtime, payload)
        markdown = _normalize_web_markdown(answer, url, title)
        if not _is_structured_web_markdown(markdown):
            return "", ""
        return markdown, mode
    except Exception:
        return "", ""


def _fallback_web_markdown(url: str, title: str, text: str) -> str:
    source_text = _valuable_web_text(text)
    return f"""# {title}

> 来源：{url}

## 摘要

- 未配置网页拉取模型，已保留规则过滤后的正文。
- 建议配置拉取模型后重新拉取，以生成更规范的知识库结构。

## 适用场景

原文未提供。

## 关键概念与组件职责

{source_text or "原文未提供。"}

## 操作步骤 / 配置 / 命令

原文未提供。

## 排障线索与注意事项

原文未提供。

## 可检索关键词

- {title}
- {urlparse(url).netloc}
"""


def _valuable_web_text(text: str) -> str:
    lines: list[str] = []
    seen = set()
    total = 0
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line or _is_noise_line(line):
            continue
        normalized = line.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        lines.append(line)
        total += len(line)
        if total >= 30000:
            break
    return "\n".join(lines).strip()


def _is_noise_line(line: str) -> bool:
    if len(line) <= 2:
        return True
    if re.fullmatch(r"[\W_]+", line):
        return True
    for pattern in WEB_NOISE_PATTERNS:
        if re.search(pattern, line, flags=re.IGNORECASE) and len(line) <= 60:
            return True
    return False


def _normalize_web_markdown(markdown: str, url: str, title: str) -> str:
    content = markdown.strip()
    if not content:
        return _fallback_web_markdown(url, title, "")
    content = re.sub(r"^```(?:markdown|md)?\s*", "", content, flags=re.IGNORECASE).strip()
    content = re.sub(r"\s*```\s*$", "", content).strip()
    if not content.startswith("#"):
        content = f"# {title}\n\n{content}"
    if url not in content:
        content = f"{content.rstrip()}\n\n## 来源\n\n- {url}"
    return content


def _is_structured_web_markdown(markdown: str) -> bool:
    content = markdown.strip()
    if not content.startswith("# "):
        return False
    for pattern in WEB_REPORT_PATTERNS:
        if re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE):
            return False
    return all(re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE) for pattern in WEB_KNOWLEDGE_SECTION_PATTERNS)


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
        update_document_task(db, task_id, "running", 35, "提取网页正文和教程图片")
        source_markdown, image_assets = _prepare_web_source_markdown(db, document_id, page)
        update_document_task(db, task_id, "running", 45, "整理网页内容")
        markdown, mode = build_web_markdown(
            db,
            url,
            page["title"],
            source_markdown or page["text"],
            instruction,
            image_assets,
        )
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
