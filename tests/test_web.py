import threading
import time

import pytest
from starlette.testclient import TestClient

from standup import runs, web
from standup.models import Brief, BriefItem


@pytest.fixture(autouse=True)
def clean_state():
    web.CACHE.clear()
    runs.INFLIGHT.clear()
    yield
    web.CACHE.clear()
    runs.INFLIGHT.clear()


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
    html = TestClient(web.app).get("/nobody-here").text
    assert 'data-state="reading"' in html and "/nobody-here/events" in html


def test_posthog_payload_never_contains_the_handle(monkeypatch):
    monkeypatch.setenv("POSTHOG_KEY", "phc_test")
    web.CACHE["yannvr"] = (time.time(), brief())
    html = TestClient(web.app).get("/yannvr").text
    assert "handle_length" in html and "'yannvr'" not in html.split("posthog.capture")[1][:200]


def test_posthog_rewrites_the_url_properties_that_would_carry_the_handle(monkeypatch):
    monkeypatch.setenv("POSTHOG_KEY", "phc_test")
    web.CACHE["yannvr"] = (time.time(), brief())
    html = TestClient(web.app).get("/yannvr").text
    assert "sanitize_properties" in html
    assert "delete p.$pathname" in html and "delete p.$referrer" in html


def test_home_initialises_posthog_without_capturing_a_page_view(monkeypatch):
    monkeypatch.setenv("POSTHOG_KEY", "phc_test")
    html = TestClient(web.app).get("/").text
    assert "posthog.init" in html
    assert html.count("posthog.capture(") == 1 and "cta_clicked" in html
    assert "posthog.capture(" not in web._posthog()


def test_robots_keeps_crawlers_off_every_handle():
    r = TestClient(web.app).get("/robots.txt")
    assert r.status_code == 200
    assert r.text == "User-agent: *\nDisallow: /\nAllow: /$\n"


def test_a_bad_handle_gets_the_page_back_with_one_line():
    r = TestClient(web.app).get('/x" onmouseover="alert(1)')
    assert r.status_code == 404
    assert "does not look like a GitHub handle" in r.text and "<form" in r.text


def test_one_run_per_target_however_many_people_are_watching():
    calls = []

    def slow(progress):
        calls.append(1)
        time.sleep(0.2)
        return brief()

    first = runs.watch("yannvr", slow)
    second = runs.watch("yannvr", slow)
    assert first is second
    kind, payload = first.event(0)
    assert kind == "brief" and calls == [1]


def test_the_budget_is_released_when_the_work_ends(monkeypatch):
    monkeypatch.setattr(runs, "BUDGET", threading.Semaphore(1))
    for target in ("one", "two"):
        run = runs.watch(target, lambda progress: brief())
        assert run.event(0)[0] == "brief"


def test_a_fifth_run_is_told_to_come_back(monkeypatch):
    monkeypatch.setattr(runs, "BUDGET", threading.Semaphore(0))
    run = runs.watch("yannvr", lambda progress: brief())
    kind, payload = run.event(0)
    assert kind == "failed" and payload == runs.BUSY


def test_an_unexpected_break_is_a_sentence_not_a_class_name():
    assert runs.plain(ValueError("boom")) == runs.BROKE
    assert runs.plain(RuntimeError("Standup could not finish the brief (Boom)")).startswith("Standup could not finish the brief")


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


def test_a_second_visitor_joins_the_run_instead_of_starting_another(monkeypatch):
    calls = []

    def fake(target, on_progress=None, source=None):
        calls.append(target)
        on_progress("scout 1 of 1")
        time.sleep(0.2)
        return brief()

    monkeypatch.setattr(web, "run_standup", fake)
    runs.watch("yannvr", lambda progress: web.run_standup("yannvr", on_progress=progress, source="github"))
    body = TestClient(web.app).get("/yannvr/events").text
    assert calls == ["yannvr"]
    assert "event: progress" in body and "event: done" in body
