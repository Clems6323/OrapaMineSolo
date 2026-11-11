"""Évaluation et scoring d'une soumission (issue #93)."""

from __future__ import annotations

import sys
import textwrap

from orapa_mine.solver import benchmark as bm
from orapa_mine.solver.evaluate import (
    DNF_SENTINEL_DISTANCE,
    GridEntry,
    GridScore,
    SubmissionResult,
    aggregate,
    evaluate,
    load_grid_set,
    rank,
    score_grid,
    to_json,
)
from orapa_mine.solver.referee import GridResult


def _result(**kw) -> GridResult:
    base = dict(solved=False, points=0, distance=None, moves=0, dnf_reason=None,
                cpu_time_ms=None, wall_time_ms=0, transcript=[])
    base.update(kw)
    return GridResult(**base)


# --- Notation d'une grille ---------------------------------------------------


def test_no_complete_submission_uses_sentinel_distance():
    s = score_grid(_result(distance=None, dnf_reason="eof", wall_time_ms=12), "g", "small")
    assert s.distance == DNF_SENTINEL_DISTANCE == 1000.0
    assert s.cpu_time_ms == 12          # repli sur le temps mur (cpu non mesuré)
    assert s.solved is False


def test_solved_grid_keeps_zero_distance_and_cpu():
    s = score_grid(_result(solved=True, distance=0.0, points=4, cpu_time_ms=50), "g", "small")
    assert s.distance == 0.0 and s.points == 4 and s.cpu_time_ms == 50 and s.solved is True


# --- Agrégation --------------------------------------------------------------


def test_aggregate_totals_and_per_tier():
    scores = [
        GridScore("g0", "small", True, 0.0, 4, 10, None, 3),
        GridScore("g1", "small", False, 1000.0, 0, 5, "eof", 1),
        GridScore("g2", "large", False, 2.5, 12, 20, None, 7),
    ]
    agg = aggregate(scores)
    assert agg.total_distance == 1002.5
    assert agg.total_points == 16
    assert agg.total_cpu_time_ms == 35
    assert agg.solved_count == 1 and agg.grid_count == 3
    assert agg.per_tier["small"] == {"distance": 1000.0, "points": 4, "cpu_time_ms": 15, "solved": 1, "count": 2}
    assert agg.per_tier["large"]["count"] == 1


# --- Classement lexicographique distance -> points -> cpu --------------------


def _sub(dist, pts, cpu) -> SubmissionResult:
    return SubmissionResult(dist, pts, cpu, 0, 0, {}, [])


def test_ranking_is_distance_then_points_then_cpu():
    results = {
        "A": _sub(0.0, 10, 100),
        "B": _sub(0.0, 10, 50),   # même distance+points, moins de CPU -> devant A
        "C": _sub(0.0, 5, 999),   # moins de points -> devant A et B
        "D": _sub(2.0, 0, 0),     # distance plus grande -> dernier
    }
    assert [name for name, _ in rank(results)] == ["C", "B", "A", "D"]


# --- Artefact JSON -----------------------------------------------------------


def test_to_json_shape():
    agg = aggregate([GridScore("g0", "small", True, 0.0, 4, 10, None, 3)])
    data = to_json(agg)
    assert set(data) == {"total", "per_tier", "grids"}
    assert data["total"]["solved"] == 1 and data["total"]["grids"] == 1
    row = data["grids"][0]
    assert row["grid_id"] == "g0" and row["distance"] == 0.0 and row["dnf_reason"] is None


# --- Chargement d'un jeu + intégration sous-processus ------------------------


def test_load_grid_set(tmp_path):
    for i, seed in enumerate((1, 2)):
        grid, spec, pieces = bm.generate_valid("small", seed=seed)
        bm.save_grid(tmp_path / f"{i:02d}-small.json", grid, spec, pieces)
    entries = load_grid_set(tmp_path)
    assert [e.grid_id for e in entries] == ["00-small", "01-small"]
    assert all(e.tier == "small" for e in entries)


def test_evaluate_give_up_over_a_grid_set(tmp_path):
    script = tmp_path / "solver.py"
    script.write_text(textwrap.dedent("""
        import sys, json
        for line in sys.stdin:
            msg = json.loads(line)
            if msg["type"] == "hello":
                print(json.dumps({"type": "give_up"}), flush=True)
            elif msg["type"] in ("result", "end"):
                break
    """), encoding="utf-8")
    entries = [
        GridEntry("a", "small", bm.generate_valid("small", seed=1)[0]),
        GridEntry("b", "small", bm.generate_valid("small", seed=2)[0]),
    ]
    result = evaluate([sys.executable, str(script)], entries, move_timeout_ms=2000)
    assert result.grid_count == 2
    assert result.solved_count == 0
    assert result.total_distance == 2 * DNF_SENTINEL_DISTANCE  # 2000.0
    assert result.total_points == 0
    assert result.total_cpu_time_ms >= 0
