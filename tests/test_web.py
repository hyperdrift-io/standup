import time

from starlette.testclient import TestClient

from standup import web
from standup.models import Brief, BriefItem


def brief(target="yannvr"):
    return Brief(target=target, standing="Green.", beyond_tonight="b", generated_at="2026-09-09T00:00:00Z",
                 items=[BriefItem(title="Do", evidence="e", action="a", minutes=5, kind="thread", waiting_on=None, repo="r")])


def test_home_has_one_form_and_no_classes():
    html = TestClient(web.app).get("/").text
    assert html.count("<form") == 1 and 'class="' not in html


def test_post_redirects_to_handle():
    r = TestClient(web.app).post("/", data={"target": " @YannVR "}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/yannvr"


def test_cached_brief_renders_without_running():
    web.CACHE["yannvr"] = (time.time(), brief())
    html = TestClient(web.app).get("/yannvr").text
    assert "Green." in html and "Do" in html and 'data-state="done"' in html


def test_uncached_renders_reading_state():
    web.CACHE.clear()
    html = TestClient(web.app).get("/nobody-here").text
    assert 'data-state="reading"' in html and "/nobody-here/events" in html


def test_posthog_payload_never_contains_the_handle(monkeypatch):
    monkeypatch.setenv("POSTHOG_KEY", "phc_test")
    web.CACHE["yannvr"] = (time.time(), brief())
    html = TestClient(web.app).get("/yannvr").text
    assert "handle_length" in html and "'yannvr'" not in html.split("posthog.capture")[1][:200]


def test_favicon_is_not_treated_as_a_handle():
    r = TestClient(web.app).get("/favicon.ico")
    assert r.status_code == 404


def test_reflected_xss_attempt_is_rejected_as_not_a_handle():
    r = TestClient(web.app).get('/x" onmouseover="alert(1)')
    assert r.status_code == 404


def test_posthog_snippet_disables_autocapture_and_pageviews(monkeypatch):
    monkeypatch.setenv("POSTHOG_KEY", "phc_test")
    web.CACHE["yannvr"] = (time.time(), brief())
    html = TestClient(web.app).get("/yannvr").text
    assert "autocapture:false" in html and "capture_pageview:false" in html


def test_home_page_has_cta_click_tracking(monkeypatch):
    monkeypatch.setenv("POSTHOG_KEY", "phc_test")
    html = TestClient(web.app).get("/").text
    assert "cta_clicked" in html and 'data-cta="repo"' in html and 'data-cta="hyperdrift"' in html
