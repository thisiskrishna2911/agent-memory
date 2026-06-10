from pathlib import Path
from agent_memory import identity, vault


def test_normalize_remote_strips_protocol_and_git():
    assert identity.normalize_remote(
        "git@github.com:krishna/feat-x.git") == "github.com/krishna/feat-x"
    assert identity.normalize_remote(
        "https://github.com/Krishna/Feat-X.git") == "github.com/krishna/feat-x"


def test_marker_signal_read(tmp_path: Path):
    (tmp_path / ".agentmemory").write_text("project: my-proj\n")
    sig = identity.detect_signals(tmp_path)
    assert sig["marker"] == "my-proj"


def test_folder_signal_fallback(tmp_path: Path):
    proj = tmp_path / "Some Cool Repo"
    proj.mkdir()
    sig = identity.detect_signals(proj)
    assert sig["folder"] == "some-cool-repo"
    assert sig["marker"] is None


def test_list_known_projects(tmp_path: Path):
    vault.scaffold(tmp_path)
    (tmp_path / "projects" / "alpha").mkdir(parents=True)
    (tmp_path / "sessions" / "beta").mkdir(parents=True)
    known = identity.list_known_projects(tmp_path)
    assert known == ["alpha", "beta"]
