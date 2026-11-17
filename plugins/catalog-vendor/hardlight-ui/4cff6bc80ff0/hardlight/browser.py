"""Optional, bounded local-browser evidence. Importing this module does not browse.

This is not an OS security sandbox: only audit local pages you are authorized to
execute. Requests are restricted to the exact literal-loopback origin or the
local HTML directory. No browser/dependency installation is performed.
"""
import asyncio
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


MAX_PATH = 4096
MAX_FILE_BYTES = 8 * 1024 * 1024
ASSET_SUFFIXES = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg", ".png", ".jpg", ".jpeg",
                  ".gif", ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".webm"}


def _bounded_string(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_PATH or any(ord(c) < 32 for c in value) or "\\" in value:
        raise ValueError(f"{field} must be a nonempty string of at most 4096 characters without control characters or backslashes")


def _no_symlinks(path):
    if any(part.is_symlink() for part in [path, *path.parents]):
        raise ValueError("symlink paths are not permitted")


def _http_origin(url):
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"} or parsed.username is not None or parsed.password is not None:
        raise ValueError("use literal-loopback HTTP (127.0.0.1 or [::1]) without credentials; hostnames and HTTPS are not accepted")
    # Force port validation; reject port zero as well as noncanonical host spellings.
    port = parsed.port if parsed.port is not None else 80
    if not 1 <= port <= 65535:
        raise ValueError("HTTP port must be in 1..65535")
    if not re.fullmatch(r"(?:127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?", parsed.netloc):
        raise ValueError("use an exact loopback literal with an optional numeric port")
    return ("http", parsed.hostname, port)


def _file_path(url):
    parsed = urlsplit(url)
    if parsed.scheme != "file" or parsed.netloc or parsed.query:
        raise ValueError("file URI must be local, absolute and have no query")
    path = Path(unquote(parsed.path))
    if not path.is_absolute() or "\x00" in str(path):
        raise ValueError("file URI must contain an absolute local path")
    return path


def _validate_target(target):
    _bounded_string(target, "target")
    parsed = urlsplit(target)
    if parsed.scheme == "http":
        return {"url": target, "origin": _http_origin(target), "file_root": None}
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError("target must be a local HTML file or literal-loopback HTTP URL")
    path = _file_path(target) if parsed.scheme == "file" else Path(target).absolute()
    _no_symlinks(path)
    path = path.resolve(strict=True)
    if path.suffix.lower() not in {".html", ".htm"} or not path.is_file():
        raise ValueError("local target must be an existing .html or .htm file")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("local HTML exceeds the 8 MiB file limit")
    fragment = "#" + parsed.fragment if parsed.scheme == "file" and parsed.fragment else ""
    return {"url": path.as_uri() + fragment, "origin": None, "file_root": str(path.parent)}


def _allowed_request(url, policy):
    try:
        _bounded_string(url, "request URL")
        if policy["origin"] is not None:
            return _http_origin(url) == policy["origin"]
        path = _file_path(url)
        _no_symlinks(path)
        relative = path.resolve(strict=True).relative_to(Path(policy["file_root"]))
        return (not any(part.startswith(".") for part in relative.parts)
                and path.is_file() and path.suffix.lower() in ASSET_SUFFIXES
                and path.stat().st_size <= MAX_FILE_BYTES)
    except (ValueError, OSError):
        return False


LIMITS = {"dom_elements": 2000, "findings_per_check": 100, "events_per_collection": 100,
          "event_text": 1000, "requests_per_context": 2000, "navigation_ms": 8000,
          "operation_ms": 5000, "run_seconds": 45, "screenshot_full_page": False,
          "screenshot_max_width": 1440, "screenshot_max_height": 1000}
VIEWS = [("wide", 1440, 1000, "no-preference"), ("narrow", 390, 844, "no-preference"),
         ("narrow-reduced-motion", 390, 844, "reduce")]
DOM_SCRIPT = r"""limit => {
    const cap = 100, walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_ELEMENT);
    const elements = [document.documentElement];
    while (elements.length < limit && walker.nextNode()) elements.push(walker.currentNode);
    const truncated = !!walker.nextNode();
    const overlays=[]; let overlayLimit=false;
    for(const e of elements) {
        const s=getComputedStyle(e);
        if(s.display==='none' || s.visibility!=='visible' || Number(s.opacity)===0) continue;
        if(['absolute','fixed','sticky'].includes(s.position) || s.zIndex!=='auto' || s.pointerEvents==='none') {
            if(overlays.length<100) overlays.push({element:e,rect:e.getBoundingClientRect()}); else overlayLimit=true;
        }
    }
    const result = {viewport:{width:innerWidth,height:innerHeight},
        reduced_motion:matchMedia('(prefers-reduced-motion: reduce)').matches,
        missing_accessible_names:[], duplicate_ids:[], broken_images:[], contrast:[],
        horizontal_overflow:{detected:false,scroll_width:Math.max(document.documentElement.scrollWidth,document.body?.scrollWidth||0),elements:[]},
        coverage:{sampled_elements:elements.length,truncated,scope:'main document light DOM only; initial state',
                  names:'heuristic name/label presence, not the full accessible-name algorithm',
                  contrast:'simple opaque sRGB text only; unknown is not a pass',finding_counts:{},findings_truncated:{}}};
    result.horizontal_overflow.detected = result.horizontal_overflow.scroll_width > innerWidth + 1;
    const add = (key, value) => {
        result.coverage.finding_counts[key] = (result.coverage.finding_counts[key] || 0) + 1;
        const list = key === 'overflow_elements' ? result.horizontal_overflow.elements : result[key];
        if (list.length < cap) list.push(value); else result.coverage.findings_truncated[key] = true;
    };
    const describe = e => ({tag:e.tagName.toLowerCase(),id:(e.id||'').slice(0,200)});
    const text = e => {
        if (!e) return '';
        const w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT); let output='',count=0;
        while (w.nextNode() && count++ < 20 && output.length < 500) output += w.currentNode.data.slice(0,200);
        return output.trim().slice(0,500);
    };
    const name = e => {
        const references=(e.getAttribute('aria-labelledby')||'').slice(0,2000).trim().split(/\s+/).slice(0,10);
        if (references.some(id => text(document.getElementById(id)))) return true;
        if ((e.getAttribute('aria-label')||'').trim()) return true;
        if (e.labels && Array.from(e.labels).slice(0,20).some(label => text(label))) return true;
        if (e.tagName==='INPUT') {
            if (['submit','reset'].includes(e.type)) return true;
            if (['button'].includes(e.type) && e.value.trim()) return true;
            if (e.type==='image' && (e.getAttribute('alt')||'').trim()) return true;
        }
        if (['BUTTON','A'].includes(e.tagName) || ['button','link'].includes(e.getAttribute('role'))) {
            if (text(e)) return true;
            const images=e.getElementsByTagName('img');
            for(let i=0;i<Math.min(images.length,10);i++) if((images[i].getAttribute('alt')||'').trim()) return true;
        }
        return !!(e.getAttribute('title')||'').trim();
    };
    const rgb = color => {
        const match = color.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)$/);
        if(!match || (match[4] !== undefined && Number(match[4]) !== 1)) return null;
        const channels=match.slice(1,4).map(Number);
        return channels.every(x => x>=0 && x<=255) ? channels : null;
    };
    const luminance = channels => channels.map(x => {x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4;})
        .reduce((sum,x,i)=>sum+x*[.2126,.7152,.0722][i],0);
    const contrast = (e, style, rect) => {
        const entry={...describe(e),status:'unknown',reason:'unsupported paint or transparent foreground/background'};
        const foreground=rgb(style.color), background=rgb(style.backgroundColor);
        // CSS color is evidence of glyph paint only for ordinary unstroked HTML text.
        if(e.namespaceURI!=='http://www.w3.org/1999/xhtml')
            return {...entry,reason:'non-HTML text paint (including SVG fill/stroke) requires manual inspection'};
        const fill=rgb(style.webkitTextFillColor);
        if(!fill || !foreground || fill.some((channel,i)=>channel!==foreground[i]))
            return {...entry,reason:'text-fill is transparent, unsupported or differs from CSS color; inspect effective glyph paint'};
        if(parseFloat(style.webkitTextStrokeWidth)!==0)
            return {...entry,reason:'text-stroke changes glyph paint; inspect fill and stroke contrast manually'};
        if (!foreground || !background) return entry;
        let ancestor=e,depth=0;
        while(ancestor && depth++<32) {
            const s=getComputedStyle(ancestor);
            if(/\binset\b/.test(s.boxShadow))
                return {...entry,reason:'inset box-shadow changes background paint; inspect contrast manually'};
            if(s.backgroundClip!=='border-box' || s.webkitBackgroundClip!=='border-box')
                return {...entry,reason:'background-clip changes background paint; inspect contrast manually'};
            if(Number(s.opacity)!==1 || s.backgroundImage!=='none' || s.filter!=='none' || s.backdropFilter!=='none' ||
               s.mixBlendMode!=='normal' || s.textShadow!=='none' || s.maskImage!=='none') return entry;
            for(const pseudo of ['::before','::after']) {
                const p=getComputedStyle(ancestor,pseudo);
                if(!['none','normal'].includes(p.content)) return entry;
            }
            ancestor=ancestor.parentElement;
        }
        if(ancestor) return {...entry,reason:'ancestor sample limit'};
        if(overlayLimit || overlays.some(o => o.element!==e && !o.element.contains(e) &&
            o.rect.left<rect.right && o.rect.right>rect.left && o.rect.top<rect.bottom && o.rect.bottom>rect.top))
            return {...entry,reason:'possible positioned or pointer-events-none overlay'};
        if(rect.right<=0 || rect.bottom<=0 || rect.left>=innerWidth || rect.top>=innerHeight)
            return {...entry,reason:'outside captured viewport; overlays not checked'};
        const x=Math.max(0,Math.min(innerWidth-1,(rect.left+rect.right)/2));
        const y=Math.max(0,Math.min(innerHeight-1,(rect.top+rect.bottom)/2));
        const top=document.elementFromPoint(x,y);
        if(top!==e && !e.contains(top)) return {...entry,reason:'possible overlay/occlusion'};
        const a=luminance(foreground), b=luminance(background), ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
        const size=parseFloat(style.fontSize),weight=parseFloat(style.fontWeight);
        const threshold=size>=24 || (size>=18.666666666666668 && weight>=700) ? 3 : 4.5;
        return {...describe(e),status:ratio>=threshold?'pass':'fail',ratio,threshold,foreground:style.color,background:style.backgroundColor};
    };
    const ids=new Map();
    for(const e of elements) {
        if(e.id) ids.set(e.id,(ids.get(e.id)||0)+1);
        if(e.tagName==='IMG' && e.complete && e.naturalWidth===0) add('broken_images',{...describe(e),source:(e.getAttribute('src')||'').slice(0,500)});
        const style=getComputedStyle(e), rect=e.getBoundingClientRect();
        if(style.display==='none' || style.visibility!=='visible') continue;
        const control=e.matches('button,a[href],input:not([type="hidden"]),select,textarea,[role="button"],[role="link"]');
        if(control && !name(e)) add('missing_accessible_names',describe(e));
        if(e.tagName==='IMG' && !e.hasAttribute('alt') && !name(e)) add('missing_accessible_names',describe(e));
        if(rect.width===0 || rect.height===0) continue;
        if(rect.left < -1 || rect.right > innerWidth+1) add('overflow_elements',describe(e));
        let directText=false;
        for(let i=0;i<Math.min(e.childNodes.length,20);i++) {
            if(e.childNodes[i].nodeType===Node.TEXT_NODE && e.childNodes[i].data.trim()) directText=true;
        }
        if(directText) add('contrast',contrast(e,style,rect));
    }
    for(const [id,count] of ids) if(count>1) add('duplicate_ids',{id:id.slice(0,200),count});
    return result;
}"""


def _prepare_output(output_dir):
    _bounded_string(output_dir, "output_dir")
    output = Path(output_dir).absolute()
    _no_symlinks(output)
    if output.exists() and not output.is_dir():
        raise ValueError("output_dir must be a directory, not a source file")
    output.mkdir(parents=True, exist_ok=True)
    report = output / "report.json"
    _no_symlinks(report)
    if report.exists():
        if not report.is_file() or report.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("refusing to replace a non-report output target")
        previous = json.loads(report.read_text(encoding="utf-8"))
        if not isinstance(previous, dict) or previous.get("hardlight_browser_report") != 1:
            raise ValueError("report.json exists but is not a Hardlight browser report; choose another output_dir")
    return output.resolve(), report


def _atomic_report(path, result):
    descriptor, temporary = tempfile.mkstemp(prefix=".hardlight-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=True, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _record(result, collection, item):
    if len(result[collection]) < LIMITS["events_per_collection"]:
        result[collection].append(item)
    else:
        result["events_truncated"][collection] = True


def _browser_executable(playwright, executable):
    if executable is not None:
        _bounded_string(executable, "executable")
        candidate = Path(executable).absolute()
    else:
        candidate = next((Path(found) for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
                          if (found := shutil.which(name))), Path(playwright.chromium.executable_path))
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise RuntimeError("No installed Chrome/Chromium found. Install a browser yourself or pass executable; Hardlight never installs one.")
    return str(candidate)


async def _close(resource, method, result):
    if resource is not None:
        try:
            await asyncio.wait_for(getattr(resource, method)(), timeout=3)
        except Exception as exc:
            result["cleanup_errors"].append(str(exc)[:1000])


async def _run(policy, run_dir, executable, result):
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("Optional browser audit requires Playwright in this Python environment; no dependencies are installed automatically.") from exc
    playwright = browser = context = None
    try:
        playwright = await asyncio.wait_for(async_playwright().start(), timeout=10)
        path = _browser_executable(playwright, executable)
        result["executable"] = path
        browser = await playwright.chromium.launch(executable_path=path, headless=True, timeout=10000,
            args=["--disable-background-networking", "--disable-component-update", "--disable-domain-reliability",
                  "--disable-sync", "--no-default-browser-check", "--no-first-run",
                  "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"])
        result["browser_version"] = browser.version
        for name, width, height, motion in VIEWS:
            try:
                context = await browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1,
                    reduced_motion=motion, service_workers="block", accept_downloads=False, permissions=[],
                    java_script_enabled=True)
                if not callable(getattr(context, "route_web_socket", None)):
                    raise RuntimeError("Browser audit requires Playwright >=1.48 for WebSocket blocking; update it explicitly.")
                context.set_default_timeout(LIMITS["operation_ms"])
                context.set_default_navigation_timeout(LIMITS["navigation_ms"])
                requests = 0

                async def route_request(route):
                    nonlocal requests
                    request = route.request
                    requests += 1
                    url = request.url
                    allowed = _allowed_request(url, policy)
                    if url.startswith("data:") and len(url) <= 2 * 1024 * 1024 and request.resource_type in {"image", "font"}:
                        allowed = True
                    reason = "outside allowed origin/directory"
                    if requests > LIMITS["requests_per_context"]:
                        allowed, reason = False, "request sample budget exceeded"
                    if any(key in request.headers for key in ("authorization", "proxy-authorization", "cookie")):
                        allowed, reason = False, "credential-bearing request blocked"
                    if allowed and policy["origin"] is not None:
                        # continue_() lets Chromium follow redirects without another
                        # route callback. Inspect Location before giving it to Chrome.
                        response = await route.fetch(max_redirects=0, max_retries=0, timeout=5000)
                        location = response.headers.get("location")
                        if 300 <= response.status < 400 and location:
                            destination = urljoin(url, location)
                            if not _allowed_request(destination, policy):
                                _record(result, "blocked_requests", {"view": name, "url": destination[:MAX_PATH], "reason": "cross-origin redirect blocked"})
                                await response.dispose()
                                await route.abort("blockedbyclient")
                                return
                        await route.fulfill(response=response)
                        await response.dispose()
                    elif allowed:
                        await route.continue_()
                    else:
                        _record(result, "blocked_requests", {"view": name, "url": url[:MAX_PATH], "reason": reason})
                        await route.abort("blockedbyclient")

                async def block_socket(socket):
                    _record(result, "blocked_requests", {"view": name, "url": socket.url[:MAX_PATH], "reason": "WebSockets disabled"})
                    await socket.close()

                async def safe_route(route):
                    try:
                        await route_request(route)
                    except Exception as exc:
                        _record(result, "request_errors", {"view": name, "url": route.request.url[:MAX_PATH],
                                                           "error": str(exc)[:1000]})
                        try:
                            await route.abort("failed")
                        except Exception:
                            pass  # Context teardown can already have cancelled the route.

                await context.route("**/*", safe_route)
                await context.route_web_socket("**/*", block_socket)
                await context.add_init_script("""Object.defineProperty(globalThis, 'RTCPeerConnection', {value:undefined, configurable:false});
                    Object.defineProperty(globalThis, 'webkitRTCPeerConnection', {value:undefined, configurable:false});""")
                page = await context.new_page()
                page.on("console", lambda message: _record(result, "console", {"view": name, "type": message.type, "text": message.text[:1000]}))
                page.on("pageerror", lambda error: _record(result, "page_errors", {"view": name, "text": str(error)[:1000]}))
                page.on("dialog", lambda dialog: dialog.dismiss())
                page.on("download", lambda download: download.cancel())
                context.on("page", lambda popup: popup.close() if popup != page else None)
                response = await page.goto(policy["url"], wait_until="load", timeout=LIMITS["navigation_ms"])
                if not _allowed_request(page.url, policy):
                    raise RuntimeError("page navigated outside the allowed origin/directory")
                if response is not None and response.status >= 400:
                    raise RuntimeError(f"local target returned HTTP {response.status}")
                dom = await asyncio.wait_for(page.evaluate(DOM_SCRIPT, LIMITS["dom_elements"]), timeout=5)
                screenshot = run_dir / (name + ".png")
                await page.screenshot(path=str(screenshot), full_page=False, timeout=5000)
                frames = [frame.url[:MAX_PATH] for frame in page.frames if frame != page.main_frame]
                result["captures"].append({"name": name, "url": page.url[:MAX_PATH], "initial_state": True,
                    "viewport": {"width": width, "height": height}, "reduced_motion": motion,
                    "screenshot": str(screenshot), "dom": dom,
                    "uninspected_frames": frames[:20], "frames_truncated": len(frames) > 20})
            finally:
                await _close(context, "close", result)
                context = None
    finally:
        await _close(context, "close", result)
        await _close(browser, "close", result)
        await _close(playwright, "stop", result)


def audit_page(target, output_dir, executable=None):
    """Capture three fresh local initial states and write output_dir/report.json.

    ``ok`` means the runner completed, never that all findings passed. Screenshots
    use a unique child directory; only a recognized Hardlight report is replaced.
    No clicks, credentials, installed profiles, downloads or service workers.
    """
    try:
        _bounded_string(output_dir, "output_dir")
        candidate = Path(output_dir).absolute()
        _no_symlinks(candidate)
        # Preserve the no-output-on-invalid-input contract for new directories.
        # Existing evidence must instead be invalidated before target validation.
        policy = None if candidate.exists() else _validate_target(target)
        output, report = _prepare_output(output_dir)
    except (ValueError, OSError) as exc:
        return {"ok": False, "error": str(exc)}
    result = {"hardlight_browser_report": 1, "ok": False, "status": "running", "target": None,
              "report": str(report), "captures": [], "console": [], "page_errors": [], "blocked_requests": [], "request_errors": [],
              "cleanup_errors": [], "events_truncated": {}, "limits": dict(LIMITS),
              "assessment": "partial automated evidence; not usability or WCAG certification",
              "unavailable_checks": ["keyboard and pointer task completion", "screen-reader behavior", "states requiring interaction",
                                     "shadow DOM", "iframe contents", "visual/artistic quality"],
              "limitations": ["Initial states only; no controls are clicked.", "Viewport-only screenshots; content below the fold is not captured.",
                              "Isolated browser with no stored credentials; allowed local pages still execute JavaScript.",
                              "This request policy is not an operating-system sandbox."]}
    try:
        _atomic_report(report, result)
        if policy is None:
            policy = _validate_target(target)
        result["target"] = policy["url"]
        run_dir = Path(tempfile.mkdtemp(prefix="capture-", dir=output))
        asyncio.run(asyncio.wait_for(_run(policy, run_dir, executable, result), timeout=LIMITS["run_seconds"]))
        if result["cleanup_errors"]:
            raise RuntimeError("browser cleanup reported errors")
        result.update(ok=True, status="complete")
    except Exception as exc:
        result.update(ok=False, status="failed", error=(str(exc) or type(exc).__name__)[:2000])
    finally:
        try:
            _atomic_report(report, result)
        except OSError as exc:
            result.update(ok=False, status="failed", error=f"could not write fresh report: {exc}")
    return result
