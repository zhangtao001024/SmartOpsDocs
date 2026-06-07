import io
from types import SimpleNamespace

import app.services.web_pull_service as web_pull_service
from app.services.document_service import markdown_for_api
from app.services.web_pull_service import (
    WebImageAsset,
    WebImageCandidate,
    _build_web_markdown_with_openclaw,
    _ensure_web_images_preserved,
    _extract_main_web_content,
    _fallback_web_markdown,
    _prepare_web_source_markdown,
    _is_structured_web_markdown,
    _valuable_web_text,
    build_web_markdown,
)


def _png_bytes(width: int = 320, height: int = 180) -> bytes:
    from PIL import Image

    image = Image.new("RGB", (width, height), (30, 90, 150))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_valuable_web_text_filters_navigation_noise_and_duplicates():
    text = "\n".join(
        [
            "首页",
            "登录",
            "Kubernetes 控制面负责维护集群期望状态。",
            "上一篇",
            "Kubernetes 控制面负责维护集群期望状态。",
            "调度器根据资源、亲和性和约束选择节点。",
        ]
    )

    filtered = _valuable_web_text(text)

    assert "首页" not in filtered
    assert "登录" not in filtered
    assert "上一篇" not in filtered
    assert filtered.count("Kubernetes 控制面") == 1
    assert "调度器" in filtered


def test_extract_main_web_content_keeps_article_text():
    page = _extract_main_web_content(
        """
        <html>
          <head><title>Kubernetes 架构</title></head>
          <body>
            <nav>首页 登录 分享</nav>
            <article>
              <h1>Kubernetes 架构</h1>
              <p>API Server 是 Kubernetes 控制面的统一入口。</p>
              <p>Scheduler 根据资源、亲和性和约束选择节点。</p>
            </article>
          </body>
        </html>
        """,
        "https://example.test/k8s",
        "fallback",
    )

    assert "Kubernetes" in page["title"]
    assert "API Server" in page["text"]
    assert "Scheduler" in page["text"]


def test_extract_main_web_content_keeps_article_images_and_captions():
    page = _extract_main_web_content(
        """
        <html>
          <head><title>Grafana 告警配置</title></head>
          <body>
            <nav><img src="/logo.png" width="40" height="20" alt="logo"></nav>
            <article>
              <h1>Grafana 告警配置</h1>
              <p>先进入 Alert rules 页面创建规则。</p>
              <figure>
                <img src="/assets/alert-step.png" width="640" height="360" alt="Alert rule 状态截图">
                <figcaption>截图显示 Pending 和 Firing 状态。</figcaption>
              </figure>
            </article>
          </body>
        </html>
        """,
        "https://docs.example.test/grafana/alert",
        "fallback",
    )

    assert len(page["images"]) == 1
    image = page["images"][0]
    assert image.url == "https://docs.example.test/assets/alert-step.png"
    assert image.alt == "Alert rule 状态截图"
    assert image.caption == "截图显示 Pending 和 Firing 状态。"
    assert "![Alert rule 状态截图](https://docs.example.test/assets/alert-step.png)" in page["article_markdown"]
    assert "图片说明：截图显示 Pending 和 Firing 状态。" in page["article_markdown"]


def test_fallback_web_markdown_uses_knowledge_structure():
    markdown = _fallback_web_markdown(
        "https://example.test/k8s",
        "Kubernetes 架构",
        "控制面包含 API Server、Scheduler 和 Controller Manager。",
    )

    assert markdown.startswith("# Kubernetes 架构")
    assert "## 摘要" in markdown
    assert "## 关键概念与组件职责" in markdown
    assert "https://example.test/k8s" in markdown


def test_prepare_web_source_markdown_downloads_images_and_api_renders_data_url(monkeypatch, tmp_path):
    import app.services.document_service as document_service

    monkeypatch.setattr(document_service, "get_settings", lambda: SimpleNamespace(knowledge_dir=tmp_path))
    monkeypatch.setattr(web_pull_service, "_read_web_image", lambda _url: (_png_bytes(), "image/png"))
    monkeypatch.setattr(
        web_pull_service,
        "image_text_for_markdown",
        lambda _name, _bytes, _state, _db: "截图中包含 Pending 和 Firing 状态。",
    )
    page = {
        "title": "Grafana 告警配置",
        "text": "进入 Alert rules 页面创建规则。",
        "article_markdown": (
            "# Grafana 告警配置\n\n"
            "进入 Alert rules 页面创建规则。\n\n"
            "![Alert rule 状态截图](https://docs.example.test/assets/alert-step.png)"
        ),
        "images": [
            WebImageCandidate(
                url="https://docs.example.test/assets/alert-step.png",
                alt="Alert rule 状态截图",
                caption="截图显示 Pending 和 Firing 状态。",
                order=1,
            )
        ],
    }

    source, assets = _prepare_web_source_markdown(None, 7, page)

    assert len(assets) == 1
    assert (tmp_path / "7" / "assets" / "web-image-001.png").exists()
    assert "![Alert rule 状态截图](assets/web-image-001.png)" in source
    assert "图片说明：Alert rule 状态截图；截图显示 Pending 和 Firing 状态。" in source
    assert "图片识别文本" in source
    assert "Pending 和 Firing" in source
    assert "https://docs.example.test/assets/alert-step.png" not in source
    api_markdown = markdown_for_api(7, source)
    assert "data:image/png;base64" in api_markdown
    assert "Pending 和 Firing" in api_markdown


def test_build_web_markdown_restores_images_when_model_drops_them(monkeypatch):
    image_assets = [
        WebImageAsset(
            source_url="https://docs.example.test/assets/alert-step.png",
            asset_name="web-image-001.png",
            alt="Alert rule 状态截图",
            caption="截图显示 Pending 和 Firing 状态。",
            image_text="截图中包含 Pending 和 Firing 状态。",
            width=320,
            height=180,
        )
    ]

    def fake_openclaw(_db, _url, _title, _source_text, _instruction="", _image_assets=None):
        return """# Grafana 告警配置

> 来源：https://docs.example.test/grafana/alert

## 摘要

- 告警规则需要关注 Pending 和 Firing 状态。

## 适用场景

Grafana 告警排障。

## 关键概念与组件职责

Alert rule 负责判断指标状态。

## 操作步骤 / 配置 / 命令

进入 Alert rules 页面创建规则。

## 排障线索与注意事项

检查表达式和通知策略。

## 可检索关键词

- Grafana
- Alert rule
""", "openclaw-gateway"

    monkeypatch.setattr(web_pull_service, "_build_web_markdown_with_openclaw", fake_openclaw)

    markdown, mode = build_web_markdown(
        object(),
        "https://docs.example.test/grafana/alert",
        "Grafana 告警配置",
        "进入 Alert rules 页面创建规则。",
        image_assets=image_assets,
    )

    assert mode == "openclaw-gateway"
    assert "![Alert rule 状态截图](assets/web-image-001.png)" in markdown
    assert "图片识别文本" in markdown
    assert markdown.index("## 图文教程截图与识别文本") < markdown.index("## 可检索关键词")


def test_openclaw_web_pull_payload_includes_selected_skills(monkeypatch):
    captured = {}

    def fake_resolve_runtime(_db):
        return {
            "runtime": "openclaw",
            "agent": "main",
            "endpoint": "http://openclaw.local/api/agent/run",
            "api_key": "",
            "web_skills": ["browser-automation", "summarize"],
        }

    def fake_call_runtime(runtime, payload):
        captured["runtime"] = runtime
        captured["payload"] = payload
        return """# Kubernetes 架构

> 来源：https://example.test/k8s

## 摘要

- API Server 是入口。

## 适用场景

排查控制面访问异常。

## 关键概念与组件职责

API Server 负责统一入口。

## 操作步骤 / 配置 / 命令

`kubectl get --raw=/readyz?verbose`

## 排障线索与注意事项

检查 readyz 和 etcd 延迟。

## 可检索关键词

- Kubernetes
- API Server
""", "openclaw-gateway"

    import app.services.agent_service as agent_service

    monkeypatch.setattr(agent_service, "_resolve_agent_runtime", fake_resolve_runtime)
    monkeypatch.setattr(agent_service, "_call_openclaw_runtime", fake_call_runtime)

    markdown, mode = _build_web_markdown_with_openclaw(
        object(),
        "https://example.test/k8s",
        "Kubernetes 架构",
        "API Server 是 Kubernetes 控制面的统一入口。",
        "只保留运维知识",
    )

    assert mode == "openclaw-gateway"
    assert "API Server" in markdown
    payload = captured["payload"]
    assert payload["context"]["selected_skills"] == ["browser-automation", "summarize"]
    assert payload["response_format"] == "web_knowledge_markdown"
    assert payload["openclaw_timeout"] == 240
    assert "browser-automation" in payload["context"]["skills_hint"]
    assert payload["context"]["source_text_role"].startswith("后端正文抽取结果")
    assert "同域" in payload["context"]["crawl_strategy"]["scope"]


def test_openclaw_web_pull_rejects_execution_report(monkeypatch):
    def fake_resolve_runtime(_db):
        return {
            "runtime": "openclaw",
            "agent": "main",
            "endpoint": "http://openclaw.local/api/agent/run",
            "api_key": "",
            "web_skills": ["browser-automation"],
        }

    def fake_call_runtime(_runtime, _payload):
        return """## 任务结论

**目标**: https://example.test/k8s

### 输出文件

已按要求生成 6 个章节。
""", "openclaw-gateway"

    import app.services.agent_service as agent_service

    monkeypatch.setattr(agent_service, "_resolve_agent_runtime", fake_resolve_runtime)
    monkeypatch.setattr(agent_service, "_call_openclaw_runtime", fake_call_runtime)

    markdown, mode = _build_web_markdown_with_openclaw(
        object(),
        "https://example.test/k8s",
        "Kubernetes 架构",
        "API Server 是 Kubernetes 控制面的统一入口。",
    )

    assert markdown == ""
    assert mode == ""


def test_structured_web_markdown_requires_knowledge_sections():
    valid = """# Kubernetes 架构

## 摘要

## 适用场景

## 关键概念与组件职责

## 操作步骤 / 配置 / 命令

## 排障线索与注意事项

## 可检索关键词
"""
    report = """# Kubernetes 架构

## 任务结论

站点规模: 单页文档

## 摘要
"""

    assert _is_structured_web_markdown(valid) is True
    assert _is_structured_web_markdown(report) is False
