"""Serveur officiel : comptes, soumissions, classement, worker (issue #95)."""

from __future__ import annotations

import pytest

from orapa_mine.server import worker
from orapa_mine.server.storage import Store, TeamExists


def _artifact(distance, points, cpu, *, solved=0, grids=9) -> dict:
    return {
        "total": {"distance": distance, "points": points, "cpu_time_ms": cpu,
                  "solved": solved, "grids": grids},
        "per_tier": {},
        "grids": [{"grid_id": "00-small", "tier": "small", "solved": bool(solved),
                   "distance": distance, "points": points, "cpu_time_ms": cpu,
                   "dnf_reason": None, "moves": 1}],
    }


# --- Comptes d'équipe --------------------------------------------------------


def test_register_and_authenticate():
    s = Store()
    s.register_team("alpha", "secret")
    assert s.authenticate("alpha", "secret") is True
    assert s.authenticate("alpha", "wrong") is False
    assert s.authenticate("ghost", "secret") is False


def test_duplicate_team_is_rejected():
    s = Store()
    s.register_team("alpha", "secret")
    with pytest.raises(TeamExists):
        s.register_team("alpha", "other")


def test_empty_credentials_are_rejected():
    s = Store()
    with pytest.raises(ValueError):
        s.register_team("", "x")


# --- Soumissions & statuts ---------------------------------------------------


def test_submission_lifecycle():
    s = Store()
    s.register_team("alpha", "pw")
    sid = s.add_submission("alpha", "https://gitlab/x.git", "main")
    assert [sub.id for sub in s.pending_submissions()] == [sid]

    s.record_result(sid, "sha123", _artifact(0.0, 42, 10, solved=9))
    sub = s.submission(sid)
    assert sub.status == "done" and sub.sha == "sha123"
    assert s.pending_submissions() == []
    assert s.team_best("alpha")["total"]["points"] == 42


def test_failure_is_recorded():
    s = Store()
    s.register_team("alpha", "pw")
    sid = s.add_submission("alpha", "repo", "ref")
    s.record_failure(sid, "BuildError: clone failed")
    sub = s.submission(sid)
    assert sub.status == "failed" and "clone failed" in sub.detail


# --- Classement : distance -> points -> cpu, meilleur par équipe -------------


def test_leaderboard_orders_and_keeps_best_per_team():
    s = Store()
    for team in ("A", "B", "C", "D"):
        s.register_team(team, "pw")
    s.record_result(s.add_submission("A", "r", "m"), "a", _artifact(0.0, 100, 50))
    s.record_result(s.add_submission("B", "r", "m"), "b", _artifact(0.0, 100, 40))  # < A par cpu
    s.record_result(s.add_submission("C", "r", "m"), "c", _artifact(0.0, 90, 999))  # < par points
    s.record_result(s.add_submission("D", "r", "m"), "d", _artifact(5.0, 0, 0))     # distance pire
    # A re-soumet mieux : le classement doit prendre son meilleur résultat.
    s.record_result(s.add_submission("A", "r", "m2"), "a2", _artifact(0.0, 80, 10))

    board = s.leaderboard()
    assert [row.team for row in board] == ["A", "C", "B", "D"]
    a = next(row for row in board if row.team == "A")
    assert a.points == 80 and a.cpu_time_ms == 10  # son meilleur, pas le premier


# --- Worker : file, résultat, échec (évaluateur injecté) ---------------------


def test_run_pending_records_results():
    s = Store()
    s.register_team("alpha", "pw")
    s.add_submission("alpha", "https://gitlab/a.git", "main")
    s.add_submission("alpha", "https://gitlab/a.git", "dev")

    def fake_eval(repo_url, ref, grids):
        return (f"sha-{ref}", _artifact(0.0, 7, 3, solved=9))

    done = worker.run_pending(s, [], evaluate_fn=fake_eval)
    assert done == 2
    assert all(sub.status == "done" for sub in s.team_submissions("alpha"))
    assert len(s.leaderboard()) == 1  # une ligne (meilleur des deux)


def test_worker_records_build_failure():
    s = Store()
    s.register_team("alpha", "pw")
    sid = s.add_submission("alpha", "repo", "ref")

    def boom(repo_url, ref, grids):
        raise worker.BuildError("clone failed")

    worker.run_pending(s, [], evaluate_fn=boom)
    sub = s.submission(sid)
    assert sub.status == "failed" and "BuildError" in sub.detail


# --- Grilles officielles -----------------------------------------------------


def test_official_grid_entries_are_nine_with_tiers():
    entries = worker.official_grid_entries(master_seed=2027)
    assert len(entries) == 9
    assert {e.tier for e in entries} == {"small", "standard", "large"}
    assert len({e.grid_id for e in entries}) == 9
