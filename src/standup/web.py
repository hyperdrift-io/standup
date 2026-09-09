"""One page in front of the agent. Starlette, SSE for progress, no accounts, no database."""
from __future__ import annotations

import asyncio
import html
import json
import os
import queue
import re
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # PM2 (interpreter: none) does not inject the app's .env — load it ourselves.

from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import store
from .models import Brief
from .pipeline import run_standup

CACHE: dict[str, tuple[float, Brief]] = {}
TTL = 3600
RUNS = asyncio.Semaphore(4)
LOCKS: dict[str, asyncio.Lock] = {}
STATIC = Path(__file__).parent / "static"
REPO = "https://github.com/hyperdrift-io/standup"
HD = "https://ai.hyperdrift.io/?from=standup"


def _evict_cache() -> None:
    now = time.time()
    for stale in [k for k, (t, _) in CACHE.items() if now - t >= TTL]:
        del CACHE[stale]


def _norm(target: str) -> str:
    return target.strip().lstrip("@").lower()


_HANDLE = re.compile(r"[a-z0-9-]{1,39}")


def _not_a_handle(target: str) -> bool:
    return not _HANDLE.fullmatch(target)


def _posthog(event: str, props: dict) -> str:
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
            f"autocapture:false,capture_pageview:false,capture_pageleave:false}});"
            f"posthog.capture('{event}',{json.dumps(props)});</script>")


_CTA_SCRIPT = ("<script>document.addEventListener('click',function(e){"
               "var a=e.target.closest('a[data-cta]');"
               "a&&window.posthog&&posthog.capture('cta_clicked',{target:a.dataset.cta})});</script>")


def _page(title: str, body: str, ph: str = "") -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<link rel="stylesheet" href="/static/standup.css">{ph}</head><body>
<header><a href="/">Standup</a><p>Who is waiting on you. What will hurt later. What to do first.</p></header>
<main>{body}</main>
<footer><a href="{REPO}" data-cta="repo">Open source, MIT</a> · read-only, sees only what GitHub shows a stranger · <a href="{HD}" data-cta="hyperdrift">Built by Hyperdrift</a></footer>
{_CTA_SCRIPT}
</body></html>""")


def render_brief(b: Brief, seconds: float = 0) -> str:
    items = "".join(
        f"<li><h2>{html.escape(i.title)} <small>{html.escape(i.repo)}</small></h2>"
        + (f"<p><b>{html.escape(i.waiting_on)}</b> is waiting.</p>" if i.waiting_on else "")
        + f"<p>{html.escape(i.evidence)}</p><p><strong>{html.escape(i.action)}</strong> <time>{i.minutes} min</time></p></li>"
        for i in b.items)
    could = "".join(f"<li>{html.escape(c)}</li>" for c in b.could_not_see)
    looked = "".join(f"<li><time>{e.when}</time> {html.escape(e.what)}</li>" for e in b.looked_at)
    return (f'<article data-state="done" data-items="{len(b.items)}" data-seconds="{seconds}">'
            f'<p>{html.escape(b.standing)}</p><ol>{items}</ol>'
            f"<p>Beyond tonight: {html.escape(b.beyond_tonight)}</p>"
            + (f"<details><summary>Could not see</summary><ul>{could}</ul></details>" if could else "")
            + f"<details><summary>What Standup looked at</summary><ul>{looked}</ul></details>"
            f"<p><small>Generated {b.generated_at}. Share this page: it stays for an hour.</small></p></article>")


async def home(_: Request):
    return _page("Standup", """<form method="post"><label for="t">Your GitHub handle</label>
<input id="t" name="target" placeholder="yannvr" required autocomplete="off" autofocus>
<button>What should I do first?</button>
<p>Reads your public repositories once, in the open. Never writes. Private repos stay invisible to it.</p></form>""")


async def go(request: Request):
    form = await request.form()
    return RedirectResponse(f"/{_norm(str(form.get('target', '')))}", status_code=303)


async def show(request: Request):
    target = _norm(request.path_params["target"])
    if _not_a_handle(target):
        return PlainTextResponse("not a handle", status_code=404)
    hit = CACHE.get(target)
    if hit and time.time() - hit[0] < TTL:
        b = hit[1]
        return _page(f"Standup · {target}", render_brief(b),
                     _posthog("standup_rendered",
                              {"handle_length": len(target), "items": len(b.items), "seconds": 0, "cached": True}))
    body = (f'<article data-state="reading" data-events="/{html.escape(target)}/events">'
            f"<p>Reading {html.escape(target)}…</p><ul></ul></article>"
            "<script>const a=document.querySelector('article');const s=new EventSource(a.dataset.events);"
            "s.addEventListener('progress',e=>{const li=document.createElement('li');li.textContent=e.data;a.querySelector('ul').append(li)});"
            "s.addEventListener('done',e=>{s.close();const hl=a.dataset.events.length-8;a.outerHTML=e.data;"
            "const d=document.querySelector('article').dataset;"
            "window.posthog&&posthog.capture('standup_rendered',{handle_length:hl,items:+d.items,seconds:+d.seconds,cached:false})});"
            "s.addEventListener('failed',e=>{s.close();a.dataset.state='failed';a.querySelector('p').textContent=e.data;"
            "window.posthog&&posthog.capture('standup_failed',{reason:e.data})});</script>")
    return _page(f"Standup · {target}", body, _posthog("standup_requested", {"handle_length": len(target)}))


async def events(request: Request):
    target = _norm(request.path_params["target"])
    if _not_a_handle(target):
        return PlainTextResponse("not a handle", status_code=404)
    lock = LOCKS.setdefault(target, asyncio.Lock())

    async def gen():
        async with lock:
            hit = CACHE.get(target)
            if hit and time.time() - hit[0] < TTL:
                yield {"event": "done", "data": render_brief(hit[1])}
                return
            if RUNS.locked():
                yield {"event": "failed", "data": "Standup is busy with four other people. Try again in a minute."}
                return
            async with RUNS:
                q: queue.Queue = queue.Queue()
                start = time.perf_counter()

                def work():
                    try:
                        q.put(("brief", run_standup(target, on_progress=lambda m: q.put(("progress", m)))))
                    except RuntimeError as exc:  # the pipeline's own plain one-line message
                        q.put(("failed", str(exc)))
                    except Exception as exc:  # named on the page, never a trace
                        q.put(("failed", f"Standup could not finish: {exc.__class__.__name__}."))

                threading.Thread(target=work, daemon=True).start()
                while True:
                    kind, payload = await asyncio.to_thread(q.get)
                    if kind == "progress":
                        yield {"event": "progress", "data": payload}
                    elif kind == "brief":
                        seconds = round(time.perf_counter() - start, 1)
                        CACHE[target] = (time.time(), payload)
                        _evict_cache()
                        yield {"event": "done", "data": render_brief(payload, seconds)}
                        return
                    else:
                        yield {"event": "failed", "data": payload}
                        return

    return EventSourceResponse(gen())


async def health(_: Request):
    return JSONResponse({"ok": True, "cached": len(CACHE)})


app = Starlette(routes=[
    Route("/", home, methods=["GET"]),
    Route("/", go, methods=["POST"]),
    Route("/health", health),
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
