"""Bac à sable d'exécution : durcissement, délégation, smoke test (issue #96)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from orapa_mine.solver import sandbox
from orapa_mine.solver.referee import GridResult
from orapa_mine.solver.sandbox import SandboxProfile

_ROOT = Path(__file__).resolve().parents[1]


def _result(**kw) -> GridResult:
    base = dict(solved=False, points=0, distance=None, moves=0, dnf_reason=None,
                cpu_time_ms=None, wall_time_ms=1, transcript=[])
    base.update(kw)
    return GridResult(**base)


# --- Commande d'évaluation durcie --------------------------------------------


def test_run_command_is_hardened_and_isolated():
    cmd = sandbox.docker_run_command("the-image")
    joined = " ".join(cmd)
    assert cmd[:4] == ["docker", "run", "--rm", "-i"]
    assert "--network none" in joined           # aucun réseau à l'évaluation
    assert "--read-only" in cmd
    assert "--cap-drop ALL" in joined
    assert "--security-opt no-new-privileges" in joined
    assert "--pids-limit 128" in joined         # anti fork-bomb
    assert "--memory 512m" in joined and "--memory-swap 512m" in joined
    assert "nofile=256:256" in joined
    assert cmd[-1] == "the-image"               # l'image en dernier


def test_run_command_leaks_nothing_to_the_container():
    cmd = sandbox.docker_run_command("img")
    # Aucun montage ni variable d'env : la grille cachée ne passe que par stdin.
    for leak in ("-v", "--volume", "--mount", "-e", "--env"):
        assert leak not in cmd


def test_profile_values_are_applied():
    cmd = sandbox.docker_run_command("img", SandboxProfile(memory="256m", cpus="0.5", pids_limit=64, nofile=128))
    joined = " ".join(cmd)
    assert "--memory 256m" in joined and "--cpus 0.5" in joined
    assert "--pids-limit 64" in joined and "nofile=128:128" in joined


# --- Phase de build (réseau autorisé) ----------------------------------------


def test_build_and_clone_commands():
    assert sandbox.docker_build_command("/ctx", "tag") == [
        "docker", "build", "-t", "tag", "-f", "/ctx/Dockerfile", "/ctx"
    ]
    clone = sandbox.clone_commands("https://gitlab/x.git", "abc123", "/dest")
    assert clone[0][:2] == ["git", "clone"] and clone[0][-1] == "/dest"
    assert clone[1] == ["git", "-C", "/dest", "checkout", "--detach", "abc123"]
    plan = sandbox.build_plan("https://gitlab/x.git", "main", "/dest", "tag")
    assert "clone" in plan and "build" in plan


# --- Délégation à l'arbitre ---------------------------------------------------


def test_run_sandboxed_delegates_with_the_hardened_command(monkeypatch):
    captured = {}

    def fake(command, grid, **kw):
        captured["command"] = command
        captured["kw"] = kw
        return _result(solved=True, distance=0.0, points=4)

    monkeypatch.setattr(sandbox, "run_submission", fake)
    res = sandbox.run_sandboxed("myimage", object(), move_timeout_ms=1234)
    assert captured["command"] == sandbox.docker_run_command("myimage")
    assert captured["kw"]["move_timeout_ms"] == 1234
    assert res.solved is True


# --- Smoke test d'acceptation ------------------------------------------------


def test_smoke_accepts_a_submission_that_plays(monkeypatch):
    monkeypatch.setattr(sandbox, "run_sandboxed", lambda *a, **k: _result(moves=3))
    ok, msg = sandbox.smoke_test("img")
    assert ok and msg == "ok"


def test_smoke_rejects_image_that_does_not_start(monkeypatch):
    monkeypatch.setattr(sandbox, "run_sandboxed", lambda *a, **k: _result(dnf_reason="spawn_failed"))
    ok, msg = sandbox.smoke_test("img")
    assert not ok and "start" in msg


def test_smoke_rejects_immediate_exit(monkeypatch):
    monkeypatch.setattr(sandbox, "run_sandboxed", lambda *a, **k: _result(dnf_reason="eof", moves=0))
    ok, _ = sandbox.smoke_test("img")
    assert not ok


# --- Intégration réelle (ignorée sans Docker) --------------------------------


def test_real_docker_build_and_smoke():
    if not sandbox.docker_available():
        pytest.skip("docker indisponible")
    tag = "orapa-template-smoke:test"
    context = str(_ROOT / "templates" / "python")
    subprocess.run(sandbox.docker_build_command(context, tag), check=True, capture_output=True)
    ok, msg = sandbox.smoke_test(tag)
    assert ok, msg
