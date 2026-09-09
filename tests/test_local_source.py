import subprocess

from standup.sources.local import LocalSource


def git(*args, cwd, extra_env=None):
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"}
    if extra_env:
        env.update(extra_env)
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)


def test_reads_a_repo_with_uncommitted_work(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    (repo / "a.txt").write_text("a")
    git("add", ".", cwd=repo)
    git("commit", "-q", "-m", "feat: first", cwd=repo)
    (repo / "b.txt").write_text("b")
    states = LocalSource(str(repo)).read()
    assert len(states) == 1
    s = states[0]
    assert s.name == "proj" and s.default_branch == "main"
    assert s.uncommitted == 1
    assert s.recent_commits == ["feat: first"]


def test_reads_a_directory_of_repos(tmp_path):
    for n in ("one", "two"):
        r = tmp_path / n
        r.mkdir()
        git("init", "-q", "-b", "main", cwd=r)
        (r / "f").write_text(n)
        git("add", ".", cwd=r)
        git("commit", "-q", "-m", f"feat: {n}", cwd=r)
    names = sorted(s.name for s in LocalSource(str(tmp_path)).read())
    assert names == ["one", "two"]


def test_not_a_repo_yields_nothing(tmp_path):
    assert LocalSource(str(tmp_path)).read() == []


def test_directory_scan_orders_by_most_recent_commit_first(tmp_path):
    dates = {"old": "2026-01-01T00:00:00Z", "mid": "2026-06-01T00:00:00Z", "new": "2026-09-01T00:00:00Z"}
    for n, when in dates.items():
        r = tmp_path / n
        r.mkdir()
        git("init", "-q", "-b", "main", cwd=r)
        (r / "f").write_text(n)
        git("add", ".", cwd=r)
        git("commit", "-q", "-m", f"feat: {n}", cwd=r,
            extra_env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
    names = [s.name for s in LocalSource(str(tmp_path)).read()]
    assert names == ["new", "mid", "old"]
