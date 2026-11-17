"""Security tests always run; real Chromium tests require HARDLIGHT_BROWSER_TESTS=1."""
import importlib
import json
import os
from pathlib import Path

import pytest


def module():
    return importlib.import_module("hardlight.browser")


@pytest.mark.parametrize("target", [
    "https://example.com/", "http://example.com/?127.0.0.1", "http://127.0.0.1.evil.test/",
    "http://user:pass@127.0.0.1/", "http://127.1/", "http://2130706433/", "http://0x7f000001/",
    "http://localhost/", "http://127.0.0.2/", "http://[::ffff:127.0.0.1]/", "https://127.0.0.1/",
    "http://127.0.0.1:99999/", "http://127.0.0.1\\@example.com/", "http://127.0.0.1/\nfoo",
    "http://[::1]evil.test/", "http://[::1]:/", "http://127.0.0.1:/",
    "file://example.com/a.html", "data:text/html,hello", "javascript:alert(1)", "ftp://127.0.0.1/",
    "", None, False, "a" * 4097,
])
def test_invalid_targets_fail_before_browser_or_output(target, tmp_path):
    output = tmp_path / "untouched"
    result = module().audit_page(target, str(output))
    assert result["ok"] is False
    assert result["error"]
    assert not output.exists()
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("target", [
    "missing.html", "https://example.com/", "http://user:PRIVATE_CREDENTIAL@127.0.0.1/",
    None, False, {"target": "invalid type"}, "http://[malformed/",
    "http://user:PRIVATE_CREDENTIAL@[malformed/",
])
def test_validation_failure_replaces_owned_success_without_browser(target, tmp_path, monkeypatch):
    browser = module()
    output = tmp_path / "out"
    output.mkdir()
    report = output / "report.json"
    report.write_text(json.dumps({"hardlight_browser_report": 1, "ok": True,
                                  "status": "complete", "marker": "OLD_EVIDENCE"}))
    original = browser._validate_target

    def validate(value):
        sentinel = json.loads(report.read_text())
        assert sentinel["ok"] is False and sentinel["status"] == "running"
        return original(value)

    async def no_browser(*args):
        pytest.fail("validation failures must not launch a browser")

    monkeypatch.setattr(browser, "_validate_target", validate)
    monkeypatch.setattr(browser, "_run", no_browser)
    result = browser.audit_page(target, str(output))
    assert result["ok"] is False and result["status"] == "failed"
    assert result["error"]
    persisted = report.read_text()
    assert json.loads(persisted) == result
    assert "OLD_EVIDENCE" not in persisted and "PRIVATE_CREDENTIAL" not in persisted
    assert result["target"] is None
    assert result["captures"] == []
    assert list(output.iterdir()) == [report]


def test_invalid_target_preserves_unsafe_output(tmp_path):
    browser = module()
    source = tmp_path / "source.html"
    source.write_text("unrelated source")
    output = tmp_path / "out"
    output.mkdir()
    report = output / "report.json"
    report.symlink_to(source)
    assert browser.audit_page(None, str(output))["ok"] is False
    assert report.is_symlink() and source.read_text() == "unrelated source"
    report.unlink()
    report.write_text('{"unrelated": true}')
    assert browser.audit_page(None, str(output))["ok"] is False
    assert report.read_text() == '{"unrelated": true}'
    linked = tmp_path / "linked"
    linked.symlink_to(output, target_is_directory=True)
    assert browser.audit_page(None, str(linked))["ok"] is False
    assert report.read_text() == '{"unrelated": true}'


def test_literal_loopback_and_file_validation(tmp_path):
    browser = module()
    assert browser._validate_target("http://127.0.0.1:8123/a?q=1")["origin"] == ("http", "127.0.0.1", 8123)
    assert browser._validate_target("http://[::1]:8123/")["origin"] == ("http", "::1", 8123)
    source = tmp_path / "space name.html"
    source.write_text("<!doctype html><title>Local</title>")
    assert browser._validate_target(str(source))["url"] == source.as_uri()
    assert browser._validate_target(source.as_uri())["url"] == source.as_uri()
    assert browser._validate_target(source.as_uri() + "#details")["url"] == source.as_uri() + "#details"
    for bad in [tmp_path / "missing.html", tmp_path / "dir.html", tmp_path / "source.txt"]:
        if bad.name == "dir.html":
            bad.mkdir()
        elif bad.name == "source.txt":
            bad.write_text("not html")
        assert browser.audit_page(str(bad), str(tmp_path / "out"))["ok"] is False


def test_request_policy_is_exact_origin_not_substrings(tmp_path):
    browser = module()
    policy = browser._validate_target("http://127.0.0.1:8123/")
    assert browser._allowed_request("http://127.0.0.1:8123/style.css", policy)
    for url in ["http://127.0.0.1:8124/", "http://[::1]:8123/", "https://127.0.0.1:8123/",
                "http://evil.test/?http://127.0.0.1:8123/", "http://u:p@127.0.0.1:8123/", "file:///etc/passwd"]:
        assert not browser._allowed_request(url, policy)
    source = tmp_path / "index.html"
    source.write_text("<title>Test</title>")
    css = tmp_path / "style.css"
    css.write_text("body{color:black}")
    policy = browser._validate_target(str(source))
    assert browser._allowed_request(css.as_uri(), policy)
    assert not browser._allowed_request((tmp_path.parent / "secret.html").as_uri(), policy)
    secret = tmp_path / ".secret.html"
    secret.write_text("secret")
    assert not browser._allowed_request(secret.as_uri(), policy)
    link = tmp_path / "link.css"
    link.symlink_to(css)
    assert not browser._allowed_request(link.as_uri(), policy)


def test_output_safety_and_fresh_failure_report(tmp_path, monkeypatch):
    browser = module()
    source = tmp_path / "index.html"
    source.write_text("<title>Source must survive</title>")
    for output in [str(source), "", None, False, "x" * 4097]:
        assert browser.audit_page(str(source), output)["ok"] is False
    unsafe = tmp_path / "unsafe"
    unsafe.symlink_to(tmp_path, target_is_directory=True)
    assert browser.audit_page(str(source), str(unsafe))["ok"] is False
    output = tmp_path / "out"
    output.mkdir()
    report = output / "report.json"
    report.symlink_to(source)
    assert browser.audit_page(str(source), str(output))["ok"] is False
    assert source.read_text() == "<title>Source must survive</title>"
    report.unlink()
    report.write_text('{"source":"unrelated"}')
    assert browser.audit_page(str(source), str(output))["ok"] is False
    assert json.loads(report.read_text()) == {"source": "unrelated"}
    report.write_text(json.dumps({"hardlight_browser_report": 1, "ok": True, "status": "complete"}))

    async def unavailable(policy, run_dir, executable, result):
        sentinel = json.loads(report.read_text())
        assert sentinel["status"] == "running" and sentinel["ok"] is False
        raise RuntimeError("Playwright unavailable (test setup failure)")

    monkeypatch.setattr(browser, "_run", unavailable)
    result = browser.audit_page(str(source), str(output))
    assert result["ok"] is False and result["status"] == "failed"
    assert "Playwright unavailable" in result["error"]
    assert json.loads(report.read_text()) == result
    assert source.read_text() == "<title>Source must survive</title>"
    assert not list(output.glob("*.tmp"))


@pytest.fixture
def live_browser():
    if os.environ.get("HARDLIGHT_BROWSER_TESTS") != "1":
        pytest.skip("set HARDLIGHT_BROWSER_TESTS=1 for real installed Chrome/Chromium tests")
    pytest.importorskip("playwright.async_api", reason="optional Playwright dependency is not installed")
    import shutil
    from playwright.sync_api import sync_playwright
    if not any(shutil.which(name) for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")):
        with sync_playwright() as pw:
            if not Path(pw.chromium.executable_path).is_file():
                pytest.skip("no installed Chrome or Playwright Chromium; no automatic install")
    return module()


def test_real_initial_captures_and_viewport_geometry(live_browser, tmp_path):
    source = tmp_path / "index.html"
    source.write_text('''<!doctype html><html lang="en"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Capture fixture</title><style>body{background:white;color:black}</style>
        <h1>Initial state</h1><button aria-label="Save">Save</button>
        <script>document.body.dataset.motion = matchMedia('(prefers-reduced-motion: reduce)').matches;</script></html>''')
    result = live_browser.audit_page(str(source), str(tmp_path / "out"))
    assert result["ok"] is True, result
    assert result["status"] == "complete"
    assert [view["name"] for view in result["captures"]] == ["wide", "narrow", "narrow-reduced-motion"]
    for view, dimensions in zip(result["captures"], [(1440, 1000), (390, 844), (390, 844)]):
        assert (view["dom"]["viewport"]["width"], view["dom"]["viewport"]["height"]) == dimensions
        png = Path(view["screenshot"]).read_bytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        import struct
        assert struct.unpack(">II", png[16:24]) == dimensions
        assert view["initial_state"] is True
    assert result["captures"][2]["dom"]["reduced_motion"] is True
    assert result["captures"][0]["dom"]["reduced_motion"] is False
    assert result["assessment"] == "partial automated evidence; not usability or WCAG certification"
    assert json.loads(Path(result["report"]).read_text()) == result
    assert result["limits"]["dom_elements"] <= 3000
    assert result["cleanup_errors"] == []


def test_real_bounded_dom_findings_unknown_contrast_and_errors(live_browser, tmp_path):
    source = Path(__file__).parent / "fixtures/browser-findings.html"
    result = live_browser.audit_page(str(source), str(tmp_path / "out"))
    assert result["ok"] is True, result
    dom = result["captures"][0]["dom"]
    assert dom["horizontal_overflow"]["detected"] is True
    assert dom["horizontal_overflow"]["scroll_width"] > dom["viewport"]["width"]
    missing = {item["id"] for item in dom["missing_accessible_names"]}
    assert {"unnamed", "empty-link", "unlabelled", "false-name", "false-name-button"} <= missing
    assert {"named", "named-button"}.isdisjoint(missing)
    assert dom["duplicate_ids"] == [{"id": "duplicate", "count": 2}]
    assert any(item["id"] == "broken" for item in dom["broken_images"])
    contrast = {item["id"]: item for item in dom["contrast"]}
    assert contrast["low"]["status"] == "fail"
    assert contrast["high"]["status"] == "pass"
    assert contrast["high"]["ratio"] == pytest.approx(21)
    for identity in ("transparent", "gradient", "opacity-text", "obscured", "pass-through-text", "pseudo"):
        assert contrast[identity]["status"] == "unknown", contrast[identity]
    assert dom["coverage"]["sampled_elements"] == result["limits"]["dom_elements"]
    assert dom["coverage"]["truncated"] is True
    assert result["captures"][0]["uninspected_frames"]
    assert any("fixture console error" in entry["text"] for entry in result["console"])
    assert any("fixture page error" in entry["text"] for entry in result["page_errors"])
    assert len(result["console"]) == 100
    assert result["events_truncated"]["console"] is True
    assert all(len(entries) <= 100 for entries in (dom["contrast"], dom["missing_accessible_names"], dom["broken_images"]))


def test_real_unsupported_text_paint_is_unknown_with_measured_controls(live_browser, tmp_path, subtests):
    source = tmp_path / "paint.html"
    source.write_text('''<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Text paint regression</title><style>
        body{background:white;font:16px sans-serif}
        p,text{color:black;background:white}
        #fill{-webkit-text-fill-color:white}
        #transparent-fill{-webkit-text-fill-color:transparent}
        #alpha-fill{-webkit-text-fill-color:rgba(0,0,0,.5)}
        #wide-gamut-fill{-webkit-text-fill-color:color(display-p3 0 0 0)}
        #stroke{-webkit-text-stroke:2px white}
        #inherited-paint{-webkit-text-fill-color:white}
        #low{color:#777;background:#888}
        #same-fill{-webkit-text-fill-color:rgb(0,0,0)}
        #oklch{color:oklch(20% .01 240)}
        #mixed{color:color-mix(in oklab, black 90%, white)}
        </style>
        <p id="control">Black on white</p><p id="low">Low contrast control</p>
        <p id="same-fill">Matching opaque fill remains measurable</p>
        <p id="oklch">Modern color is not a measured sRGB pair</p>
        <p id="mixed">A color mix is not automatically accessible</p>
        <p id="fill">White fill</p><p id="transparent-fill">Transparent fill</p>
        <p id="alpha-fill">Translucent fill</p><p id="wide-gamut-fill">Unsupported fill</p>
        <p id="stroke">White stroke</p><div id="inherited-paint"><p id="inherited-fill">Inherited fill</p></div>
        <svg width="350" height="60"><text id="svgpaint" x="1" y="40" fill="white"
        style="font-size:28px">White SVG text on white</text></svg>''')
    result = live_browser.audit_page(str(source), str(tmp_path / "out"))
    assert result["ok"] is True, result
    assert [view["name"] for view in result["captures"]] == ["wide", "narrow", "narrow-reduced-motion"]
    for view in result["captures"]:
        contrast = {item["id"]: item for item in view["dom"]["contrast"]}
        for identity in ("control", "same-fill"):
            with subtests.test(view=view["name"], identity=identity):
                assert contrast[identity]["status"] == "pass", contrast[identity]
                assert contrast[identity]["ratio"] == 21
        with subtests.test(view=view["name"], identity="low"):
            assert contrast["low"]["status"] == "fail", contrast["low"]
            assert contrast["low"]["ratio"] < contrast["low"]["threshold"]
        for identity, reason in (("fill", "text-fill"), ("transparent-fill", "text-fill"),
                                 ("alpha-fill", "text-fill"), ("wide-gamut-fill", "text-fill"),
                                 ("oklch", "text-fill"), ("mixed", "text-fill"),
                                 ("inherited-fill", "text-fill"), ("stroke", "text-stroke"),
                                 ("svgpaint", "non-HTML")):
            with subtests.test(view=view["name"], identity=identity):
                assert contrast[identity]["status"] == "unknown", contrast[identity]
                assert reason in contrast[identity]["reason"]
                assert "ratio" not in contrast[identity]
    assert json.loads(Path(result["report"]).read_text()) == result


def test_real_unsupported_background_paint_is_unknown_with_measured_controls(live_browser, tmp_path, subtests):
    source = tmp_path / "background-paint.html"
    source.write_text('''<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Background paint regression</title><style>
        body{background:black;font:16px sans-serif;margin:8px}
        p{color:black;background:white;margin:4px 0;padding:4px;line-height:20px}
        #inset,.ancestor-inset{box-shadow:inset 0 0 0 100px black}
        #multi{box-shadow:0 0 0 1px white, inset 0 0 0 100px black}
        #clip,.ancestor-clip{background-clip:text}
        #webkit-clip,.ancestor-webkit-clip{-webkit-background-clip:text}
        #content,.ancestor-content{background-clip:content-box}
        #padding{background-clip:padding-box}
        #outer{box-shadow:0 0 0 1px white}
        #low{color:#777;background:#888}
        </style>
        <p id="control">Black on white</p><p id="low">Low contrast</p>
        <p id="outer">Outer shadow control</p>
        <p id="inset">Inset shadow</p><p id="multi">Multiple shadows</p>
        <p id="clip">Clipped background</p><p id="webkit-clip">WebKit clip</p>
        <p id="content">Content clip</p><p id="padding">Padding clip</p>
        <div class="ancestor-inset"><p id="inherited-inset">Ancestor inset</p></div>
        <div class="ancestor-clip"><p id="inherited-clip">Ancestor clip</p></div>
        <div class="ancestor-webkit-clip"><p id="inherited-webkit-clip">Ancestor WebKit clip</p></div>
        <div class="ancestor-content"><p id="inherited-content">Ancestor content clip</p></div>''', encoding="utf-8")
    result = live_browser.audit_page(str(source), str(tmp_path / "out"),
                                     executable=os.environ.get("HARDLIGHT_CHROME"))
    assert result["ok"] is True, result
    assert [view["name"] for view in result["captures"]] == ["wide", "narrow", "narrow-reduced-motion"]
    assert result["cleanup_errors"] == []
    assert result["request_errors"] == []
    assert result["page_errors"] == []
    for view in result["captures"]:
        assert view["dom"]["horizontal_overflow"]["detected"] is False
        contrast = {item["id"]: item for item in view["dom"]["contrast"]}
        for identity in ("control", "outer"):
            with subtests.test(view=view["name"], identity=identity):
                assert contrast[identity]["status"] == "pass", contrast[identity]
                assert contrast[identity]["ratio"] == 21
        with subtests.test(view=view["name"], identity="low"):
            assert contrast["low"]["status"] == "fail", contrast["low"]
            channels = [value / 255 for value in (119, 136)]
            luminances = [((value + .055) / 1.055) ** 2.4 for value in channels]
            assert contrast["low"]["ratio"] == pytest.approx(
                (luminances[1] + .05) / (luminances[0] + .05), abs=1e-14, rel=0)
        for identity, reason in (("inset", "inset box-shadow"), ("multi", "inset box-shadow"),
                                 ("inherited-inset", "inset box-shadow"),
                                 ("clip", "background-clip"), ("webkit-clip", "background-clip"),
                                 ("content", "background-clip"), ("padding", "background-clip"),
                                 ("inherited-clip", "background-clip"),
                                 ("inherited-webkit-clip", "background-clip"),
                                 ("inherited-content", "background-clip")):
            with subtests.test(view=view["name"], identity=identity):
                assert contrast[identity]["status"] == "unknown", contrast[identity]
                assert reason in contrast[identity]["reason"]
                assert "ratio" not in contrast[identity]
    assert json.loads(Path(result["report"]).read_text(encoding="utf-8")) == result


@pytest.fixture
def local_servers():
    from contextlib import ExitStack
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    def start(responder):
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(self.path)
                status, headers, content = responder(self.path)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(content.encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        cleanup.callback(thread.join, 2)
        cleanup.callback(server.server_close)
        cleanup.callback(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}", calls

    with ExitStack() as cleanup:
        yield start


def test_real_cross_origin_requests_sockets_and_redirects_never_reach_sink(live_browser, local_servers, tmp_path):
    sink, sink_calls = local_servers(lambda path: (200, {"Content-Type": "text/plain"}, "network escape"))
    ws = sink.replace("http:", "ws:")

    def respond(path):
        if path == "/same-origin-hop":
            return 302, {"Location": "/redirect"}, ""
        if path == "/redirect":
            return 302, {"Location": sink + "/redirect-leak"}, ""
        if path == "/sw.js":
            return 200, {"Content-Type": "text/javascript"}, "console.log('service worker must not execute')"
        return 200, {"Content-Type": "text/html"}, f'''<!doctype html><title>Security fixture</title>
            <h1>Security fixture</h1><iframe src="/redirect" title="Redirect"></iframe>
            <iframe src="/same-origin-hop" title="Redirect chain"></iframe>
            <img src="{sink}/image" alt="Blocked"><script>
            fetch('{sink}/fetch').catch(()=>{{}});
            new WebSocket('{ws}/socket');
            navigator.serviceWorker.register('/sw.js').catch(()=>{{}});
            fetch('/credential',{{headers:{{Authorization:'Bearer deliberately-not-a-secret'}}}}).catch(()=>{{}});
            </script>'''

    origin, calls = local_servers(respond)
    result = live_browser.audit_page(origin + "/", str(tmp_path / "out"))
    assert result["ok"] is True, result
    assert sink_calls == [], f"cross-origin requests escaped policy: {sink_calls}"
    assert "/sw.js" not in calls
    assert "/credential" not in calls
    blocked = result["blocked_requests"]
    assert any("/fetch" in entry["url"] for entry in blocked)
    assert any("/image" in entry["url"] for entry in blocked)
    assert any("/redirect-leak" in entry["url"] for entry in blocked)
    assert any(entry["reason"] == "WebSockets disabled" for entry in blocked)
    assert any(entry["reason"] == "credential-bearing request blocked" for entry in blocked)


def test_real_failure_replaces_prior_success_and_closes_browser(live_browser, local_servers, tmp_path):
    source = tmp_path / "source.html"
    source.write_text("<title>First run</title>")
    output = tmp_path / "out"
    assert live_browser.audit_page(str(source), str(output))["ok"] is True
    sink, calls = local_servers(lambda path: (200, {}, "do not visit"))
    origin, _ = local_servers(lambda path: (302, {"Location": sink + "/escape"}, ""))
    result = live_browser.audit_page(origin + "/", str(output))
    assert result["ok"] is False
    assert result["status"] == "failed"
    assert calls == []
    assert result["cleanup_errors"] == []
    assert json.loads((output / "report.json").read_text()) == result
    result = live_browser.audit_page(str(source), str(output), executable=str(tmp_path / "missing-chrome"))
    assert result["ok"] is False and "installed Chrome" in result["error"]
    assert json.loads((output / "report.json").read_text()) == result


def test_missing_optional_dependency_writes_fresh_failure(tmp_path, monkeypatch):
    import builtins
    browser = module()
    source = tmp_path / "index.html"
    source.write_text("<title>Dependency failure fixture</title>")
    output = tmp_path / "out"
    output.mkdir()
    report = output / "report.json"
    report.write_text(json.dumps({"hardlight_browser_report": 1, "ok": True, "status": "complete"}))
    original = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "playwright.async_api":
            assert json.loads(report.read_text())["status"] == "running"
            raise ImportError("deliberately unavailable optional dependency")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    result = browser.audit_page(str(source), str(output))
    assert result["ok"] is False and "requires Playwright" in result["error"]
    assert json.loads(report.read_text()) == result


def test_real_file_assets_cannot_escape_directory(live_browser, tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    outside = tmp_path / "outside.js"
    outside.write_text("console.error('OUTSIDE SCRIPT EXECUTED');")
    (public / "symlink.js").symlink_to(outside)
    source = public / "index.html"
    source.write_text('''<!doctype html><title>File boundary</title><h1>Boundary</h1>
        <script src="../outside.js"></script><script src="symlink.js"></script>''')
    result = live_browser.audit_page(str(source), str(tmp_path / "out"))
    assert result["ok"] is True, result
    assert not any("OUTSIDE SCRIPT EXECUTED" in entry["text"] for entry in result["console"])
    assert any("outside.js" in entry["url"] for entry in result["blocked_requests"])
    assert any("symlink.js" in entry["url"] for entry in result["blocked_requests"])


def test_real_hung_page_has_bounded_failure_and_cleanup(live_browser, tmp_path, monkeypatch):
    import time
    source = tmp_path / "index.html"
    source.write_text("<!doctype html><title>Hung script</title><script>while(true){}</script>")
    monkeypatch.setitem(live_browser.LIMITS, "navigation_ms", 300)
    before = time.monotonic()
    result = live_browser.audit_page(str(source), str(tmp_path / "out"))
    assert time.monotonic() - before < 15
    assert result["ok"] is False and "Timeout" in result["error"]
    assert result["cleanup_errors"] == []
    assert result["captures"] == []
    assert json.loads(Path(result["report"]).read_text()) == result


def test_real_refused_connection_is_reported_without_unhandled_callback(live_browser, tmp_path, monkeypatch, capsys):
    import socket
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    monkeypatch.setitem(live_browser.LIMITS, "navigation_ms", 500)
    result = live_browser.audit_page(f"http://127.0.0.1:{port}/", str(tmp_path / "out"))
    assert result["ok"] is False
    assert result["request_errors"] and "ECONNREFUSED" in result["request_errors"][0]["error"]
    assert result["cleanup_errors"] == []
    assert "Error occurred in event listener" not in capsys.readouterr().err
