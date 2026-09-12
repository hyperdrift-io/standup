"""One page in front of the agent. Starlette, SSE for progress, no accounts, no database."""
from __future__ import annotations

import asyncio
import html
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

# PM2 (interpreter: none) does not inject the app's .env — load it ourselves, never over the host.
load_dotenv(override=False)

from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import runs, store
from .models import Brief
from .pipeline import run_standup

CACHE: dict[str, tuple[float, Brief]] = {}
TTL = 3600
SWEEP_EVERY = 3600
_swept = 0.0
STATIC = Path(__file__).parent / "static"
REPO = "https://github.com/hyperdrift-io/standup"
HD = "https://ai.hyperdrift.io/?from=standup"


def _evict_cache() -> None:
    global _swept
    now = time.time()
    for stale in [k for k, (t, _) in CACHE.items() if now - t >= TTL]:
        del CACHE[stale]
    if now - _swept >= SWEEP_EVERY:
        _swept = now
        store.sweep(7)  # seven days of session files, swept while the page is awake


def _cache_brief(target: str, brief: Brief) -> None:
    CACHE[target] = (time.time(), brief)


def _norm(target: str) -> str:
    return target.strip().lstrip("@").lower()


_HANDLE = re.compile(r"[a-z0-9-]{1,39}")


def _not_a_handle(target: str) -> bool:
    return not _HANDLE.fullmatch(target)


BEFORE_SEND = ("before_send:function(e){if(!e)return e;var p=e.properties||{};"
               "p.$current_url='https://standup.hyperdrift.io/';for(var k in p){"
               "if(k.indexOf('$session_entry')===0||k==='$pathname'||k==='$referrer'||"
               "k==='$initial_referrer'||k==='$initial_referring_domain'){delete p[k]}}"
               "e.properties=p;return e}")


def _posthog(event: str | None = None, props: dict | None = None) -> str:
    """The init snippet, plus one capture when there is something to capture. The URL carries the
    handle, so every property that could leak it — including the $session_entry_* family
    posthog-js attaches to every event in a session — is stripped before anything leaves the
    browser. sanitize_properties is deprecated (and does not see $session_entry_*), so we use
    before_send instead."""
    key = os.environ.get("POSTHOG_KEY")
    if not key:
        return ""
    return (f"<script>!function(t,e){{var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){{"
            f"function g(t,e){{var o=e.split('.');2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){{t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}}}"
            f"(p=t.createElement('script')).type='text/javascript',p.crossOrigin='anonymous',p.async=!0,p.src=s.api_host+'/static/array.js',"
            f"(r=t.getElementsByTagName('script')[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a='posthog',u.people=u.people||[],"
            f"u.toString=function(t){{var e='posthog';return'posthog'!==a&&(e+='.'+a),t||(e+=' (stub)'),e}},u.people.toString=function(){{return u.toString(1)+'.people (stub)'}},"
            f"o='init capture identify'.split(' '),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])}},e.__SV=1)}}(document,window.posthog||[]);"
            f"posthog.init('{key}',{{api_host:'https://eu.i.posthog.com',person_profiles:'identified_only',"
            f"autocapture:false,capture_pageview:false,capture_pageleave:false,{BEFORE_SEND}}});"
            + (f"posthog.capture('{event}',{json.dumps(props or {})});" if event else "")
            + "</script>")


_CTA_SCRIPT = ("<script>document.addEventListener('click',function(e){"
               "var a=e.target.closest('a[data-cta]');"
               "a&&window.posthog&&posthog.capture('cta_clicked',{target:a.dataset.cta})});</script>")


def _page(title: str, body: str, ph: str = "", status: int = 200, noindex: bool = False) -> HTMLResponse:
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{robots}<title>{html.escape(title)}</title>
<meta name="description" content="A little help getting back to it. We read your public projects and find a useful place to start. Public repositories, read-only, no login.">
<meta name="theme-color" content="#fcfaf7">
<link rel="stylesheet" href="/static/standup.css"><script src="/static/standup.js" defer></script>{ph}</head><body>
<a href="#main">Skip to content</a>
<header><a href="/" aria-label="Standup home">Standup</a></header>
<main id="main">{body}</main>
<footer><a href="{REPO}" data-cta="repo">Open source, MIT</a><a href="{HD}" data-cta="hyperdrift">Built by Hyperdrift</a></footer>
{_CTA_SCRIPT}
</body></html>""", status_code=status)


def render_brief(b: Brief, seconds: float = 0) -> str:
    items = "".join(
        f"<li><div><h2>{html.escape(i.title)}</h2><small>{html.escape(i.repo)}</small>"
        + (f"<p><b>{html.escape(i.waiting_on)}</b> is waiting.</p>" if i.waiting_on else "")
        + f"<p>{html.escape(i.evidence)}</p><p><strong>{html.escape(i.action)}</strong></p></div>"
        + f'<time datetime="PT{i.minutes}M">{i.minutes} min</time></li>'
        for i in b.items)
    could = "".join(f"<li>{html.escape(c)}</li>" for c in b.could_not_see)
    looked = "".join(f"<li><time>{e.when}</time> {html.escape(e.what)}</li>" for e in b.looked_at)
    return (f'<article data-state="done" data-items="{len(b.items)}" data-seconds="{seconds}" aria-labelledby="brief-title">'
            f'<header><p>Your brief · {html.escape(b.target)}</p><h1 id="brief-title" tabindex="-1">A useful place to start.</h1>'
            f'<p>{html.escape(b.standing)}</p></header><ol>{items}</ol>'
            f"<p>Beyond tonight: {html.escape(b.beyond_tonight)}</p>"
            + (f"<details><summary>Could not see</summary><ul>{could}</ul></details>" if could else "")
            + f"<details><summary>What Standup looked at</summary><ul>{looked}</ul></details>"
            f"<p><small>Generated {html.escape(b.generated_at)}. Share this page: it stays for an hour.</small></p>"
            '<a href="/">Read another handle <span aria-hidden="true">↗</span></a></article>')


FORM = r"""<form method="post" action="/">
<label for="t">Your GitHub handle
<input id="t" name="target" placeholder="yannvr" required maxlength="40"
 pattern="@?[a-zA-Z0-9\-]{1,39}" title="A GitHub handle: letters, digits and hyphens."
 autocomplete="off" autocapitalize="none" spellcheck="false" aria-describedby="scan-boundary"></label>
<button type="submit">Read my projects</button>
<p id="scan-boundary">Public repositories. Read-only. No login.</p></form>"""

HOME = ('<section aria-labelledby="question"><h1 id="question">A little help getting back to it.</h1>'
        '<p>We read your public projects and find a useful place to start.</p>' + FORM + '</section>'
        '<section aria-labelledby="example-heading"><header><p id="example-heading">Example route</p>'
        '</header><div data-route="example">'
        '<svg viewBox="0 0 1200 520" preserveAspectRatio="none" aria-hidden="true" focusable="false">'
        '<path d="M-40 10 H790 Q835 10 870 45 L1030 205 M180 10 Q220 10 255 45 L370 160"/>'
        '<path d="M335 210 L370 245 Q400 270 445 270 H1240 M680 235 L855 60 Q900 10 950 10 H1240"/>'
        '<path d="M810 340 L1070 600 M890 470 H980 Q1040 470 1080 430 L1170 340 Q1210 305 1240 305"/>'
        '<path d="M200 320 Q245 320 280 360 L350 430 Q390 470 430 470 H910"/>'
        '<path d="M-40 340 H165 Q205 340 240 305 L350 195 Q380 160 410 160 H565 Q605 160 640 195 L740 295 Q780 340 820 340 H855 Q900 340 935 305 L1040 200 Q1080 160 1120 160 H1240"/>'
        '<path data-segment="1" d="M410 160 H565 Q605 160 640 195 L680 235"/>'
        '<path data-segment="2" d="M680 235 L740 295 Q780 340 820 340 H855 Q900 340 935 305 L1000 240"/>'
        '<path data-segment="3" d="M1000 240 L1040 200 Q1080 160 1120 160 H1240"/>'
        '</svg><p>Your projects are still standing.<br>Maya offered a documentation fix.</p>'
        '<ol aria-label="Follow a contribution to its next step">'
        '<li><details><summary><span>docs-kit · Pull request #42</span><small>opened 3 days ago</small></summary>'
        '<div><h3>Someone has already taken the first step.</h3>'
        '<p>In this example, Maya has written a documentation fix. Her contribution gives you a place to pick up the thread.</p></div></details></li>'
        '<li><details><summary><span>Your paths meet here</span><small>Maya’s contribution · your review</small></summary>'
        '<div><h3>A small review can carry her work forward.</h3>'
        '<p>Read her changes and let her know what works. If something needs adjusting, a clear reply gives her a next step too.</p></div></details></li>'
        '<li><details><summary><span>Review her pull request</span><time datetime="PT15M">15 min</time></summary>'
        '<div><h3>One useful thing for the time you have.</h3>'
        '<p>You can leave the rest for another evening. Standup brings the contribution, its context and a next step together.</p>'
        '<a href="#t">Find a starting point in my projects ↗</a></div></details></li></ol></div>'
        '<details><summary>What Standup looked at</summary>'
        '<p>This is an example, using an illustrative contributor and project. Enter a handle above '
        'for your own brief and a record of the public projects Standup read.</p></details></section>')


async def home(_: Request):
    return _page("Standup — A place to start", HOME, _posthog())


async def robots(_: Request):
    return PlainTextResponse("User-agent: *\nDisallow: /\nAllow: /$\n")


def _try_again(message: str) -> HTMLResponse:
    return _page("Standup", f'<section><div><h1>Let’s find your projects.</h1><p role="alert">{html.escape(message)}</p>{FORM}</div></section>',
                 _posthog(), status=404, noindex=True)


async def go(request: Request):
    form = await request.form()
    return RedirectResponse(f"/{_norm(str(form.get('target', '')))}", status_code=303)


async def show(request: Request):
    target = _norm(request.path_params["target"])
    if _not_a_handle(target):
        return _try_again("That does not look like a GitHub handle. Letters, digits and hyphens, up to 39.")
    hit = CACHE.get(target)
    if hit and time.time() - hit[0] < TTL:
        b = hit[1]
        return _page(f"Standup · {target}", render_brief(b),
                     _posthog("standup_rendered",
                              {"handle_length": len(target), "items": len(b.items), "seconds": 0, "cached": True}),
                     noindex=True)
    body = (f'<article data-state="reading" data-hl="{len(target)}" data-events="/{html.escape(target)}/events" '
            'aria-labelledby="reading-title"><header>'
            f'<p>Public projects · {html.escape(target)}</p><h1 id="reading-title">Finding a useful next step.</h1>'
            '<p>Your work stays yours. We’re just doing the reading.</p></header>'
            '<p role="status" aria-live="polite">Connecting to your public projects…</p>'
            '<ul aria-label="Reading activity"></ul><p><small>Public repositories. Read-only. No login.</small></p>'
            '<p data-retry hidden><a href="">Try this handle again ↗</a> · <a href="/">Read another handle</a></p>'
            '<noscript><p>Enable JavaScript for live progress, or <a href="?wait=1">read your brief without it</a>.</p></noscript></article>')
    if request.query_params.get("wait") == "1":
        run = runs.watch(target, lambda progress: run_standup(target, on_progress=progress, source="github"),
                         on_brief=_cache_brief)
        index = 0
        while True:
            kind, payload = await asyncio.to_thread(run.event, index)
            index += 1
            if kind == "brief":
                return _page(f"Standup · {target}", render_brief(payload), noindex=True)
            if kind == "failed":
                return _try_again(str(payload))
    return _page(f"Standup · {target}", body, _posthog("standup_requested", {"handle_length": len(target)}),
                 noindex=True)


async def events(request: Request):
    target = _norm(request.path_params["target"])
    if _not_a_handle(target):
        return PlainTextResponse("not a handle", status_code=404)

    async def gen():
        hit = CACHE.get(target)
        if hit and time.time() - hit[0] < TTL:
            yield {"event": "done", "data": render_brief(hit[1])}
            return
        run = runs.watch(target, lambda progress: run_standup(target, on_progress=progress, source="github"),
                          on_brief=_cache_brief)
        index = 0
        while True:
            kind, payload = await asyncio.to_thread(run.event, index)
            index += 1
            if kind == "progress":
                yield {"event": "progress", "data": payload}
            elif kind == "brief":
                seconds = round(time.perf_counter() - run.started, 1)
                _cache_brief(target, payload)  # idempotent: on_brief above already wrote this
                _evict_cache()
                yield {"event": "done", "data": render_brief(payload, seconds)}
                return
            else:
                yield {"event": "failed", "data": payload}
                return

    return EventSourceResponse(gen())


async def health(_: Request):
    return JSONResponse({"ok": True, "cached": len(CACHE), "running": len(runs.INFLIGHT)})


app = Starlette(routes=[
    Route("/", home, methods=["GET"]),
    Route("/", go, methods=["POST"]),
    Route("/health", health),
    Route("/robots.txt", robots),
    Mount("/static", StaticFiles(directory=str(STATIC)), name="static"),
    Route("/{target}", show),
    Route("/{target}/events", events),
])


def main() -> None:
    import uvicorn
    store.sweep(7)
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "3016")))


if __name__ == "__main__":
    main()
