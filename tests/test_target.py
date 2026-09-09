from standup.target import is_path


def test_handles_are_not_paths():
    for t in ("yannvr", "hyperdrift-io", "trekhleb"):
        assert not is_path(t)


def test_prefixes_are_paths():
    for t in (".", "./x", "/tmp", "~/dev", "../up"):
        assert is_path(t)


def test_existing_directory_is_a_path(tmp_path):
    assert is_path(str(tmp_path))
