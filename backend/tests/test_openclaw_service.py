from app.services import openclaw_service


def test_normalize_skill_names_drops_invalid_and_duplicates():
    assert openclaw_service.normalize_skill_names('["browser-automation", "bad skill", "summarize", "summarize"]') == [
        "browser-automation",
        "summarize",
    ]


def test_get_openclaw_endpoint_status_treats_http_probe_as_reachable(monkeypatch):
    calls = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(req, timeout):
        calls["url"] = req.full_url
        calls["auth"] = req.headers.get("Authorization")
        assert timeout == 10
        return FakeResponse()

    monkeypatch.setattr(openclaw_service.url_request, "urlopen", fake_urlopen)

    status = openclaw_service.get_openclaw_endpoint_status("http://openclaw.local/api/agent/run", "token")

    assert status["ok"] is True
    assert status["gateway"]["reachable"] is True
    assert status["gateway"]["url"] == "http://openclaw.local/api/agent/run"
    assert status["gateway_service"]["runtime_short"] == "endpoint"
    assert status["raw"]["mode"] == "endpoint"
    assert calls["auth"] == "Bearer token"
