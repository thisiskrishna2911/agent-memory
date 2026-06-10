"""Regression tests for issues found in final code review."""
from datetime import datetime
from pathlib import Path

from agent_memory import identity, sessions, vault


def test_checkpoint_slug_suffix_does_not_collide(tmp_path: Path):
    """Task 'Login' must NOT hijack an existing 'Social login' session.

    Filename suffix matching (`endswith`) would wrongly treat them as one note.
    """
    vault.scaffold(tmp_path)
    p_social = sessions.checkpoint(tmp_path, project="x", task="Social login",
                                   summary="oauth", now=datetime(2026, 6, 10, 14, 30))
    p_login = sessions.checkpoint(tmp_path, project="x", task="Login",
                                  summary="password form", now=datetime(2026, 6, 10, 14, 31))
    assert p_social != p_login
    files = list((tmp_path / "sessions" / "x").glob("*.md"))
    assert len(files) == 2
    # The Social login session is intact, not overwritten with Login content.
    assert "oauth" in vault.read_note(p_social).body


def test_checkpoint_same_task_still_idempotent(tmp_path: Path):
    """The exact-tag match must still update the same note for the same task."""
    vault.scaffold(tmp_path)
    p1 = sessions.checkpoint(tmp_path, project="x", task="Login",
                             summary="v1", now=datetime(2026, 6, 10, 14, 30))
    p2 = sessions.checkpoint(tmp_path, project="x", task="Login",
                             summary="v2", now=datetime(2026, 6, 10, 15, 0))
    assert p1 == p2
    assert "v2" in vault.read_note(p2).body


def test_normalize_remote_handles_ssh_scheme():
    assert identity.normalize_remote(
        "ssh://git@github.com/krishna/feat-x.git") == "github.com/krishna/feat-x"
