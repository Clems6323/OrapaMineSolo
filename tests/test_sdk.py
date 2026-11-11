"""SDK participant, solveur de référence, modèle et serveur local (issue #94)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from orapa_mine.solver import benchmark as bm
from orapa_mine.solver import localrun
from orapa_mine.solver.evaluate import GridEntry, evaluate
from orapa_mine.solver.referee import run_submission
from orapa_mine.solver.sdk import Client, run

_ROOT = Path(__file__).resolve().parents[1]
_REF = [sys.executable, "-m", "orapa_mine.solver.reference_solver"]
_TEMPLATE_MAIN = _ROOT / "templates" / "python" / "main.py"


def _hello(**over) -> str:
    msg = {
        "type": "hello", "protocol": 1, "width": 10, "height": 8,
        "extensions": [], "max_proposals": 5,
        "inventory": [{"piece": "yellow", "quantity": 1, "orientations": []}],
        "limits": {"move_timeout_ms": 1000, "cpu_time_ms": 10000},
    }
    msg.update(over)
    return json.dumps(msg) + "\n"


# --- Client SDK --------------------------------------------------------------


def test_client_reads_hello_and_round_trips_a_command():
    inp = io.StringIO(_hello() + json.dumps({"type": "cell", "occupied": True, "color": "yellow", "kind": None}) + "\n")
    out = io.StringIO()
    client = Client(inp, out)
    assert client.width == 10 and client.height == 8 and client.max_proposals == 5
    resp = client.query(2, 2)
    assert resp["color"] == "yellow"
    sent = json.loads(out.getvalue().strip())
    assert sent == {"type": "query", "cell": {"row": 2, "col": 2}}


def test_run_drives_solve_and_absorbs_eof(monkeypatch):
    inp = io.StringIO(_hello() + json.dumps({"type": "result", "won": False, "points": 0, "remaining_proposals": 5}) + "\n")
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", inp)
    monkeypatch.setattr(sys, "stdout", out)
    run(lambda c: c.give_up())
    assert '"give_up"' in out.getvalue()


# --- Solveur de référence : résout toute grille valide -----------------------


def test_reference_solver_solves_each_tier():
    for tier in bm.TIERS:
        grid, _, _ = bm.generate_valid(tier, seed=1)
        result = run_submission(_REF, grid, move_timeout_ms=5000, total_timeout_ms=60000)
        assert result.solved is True
        assert result.distance == 0.0


def test_reference_solver_via_evaluate_solves_a_sample():
    entries = [
        GridEntry("a", "small", bm.generate_valid("small", seed=2)[0]),
        GridEntry("b", "standard", bm.generate_valid("standard", seed=2)[0]),
    ]
    result = evaluate(_REF, entries, move_timeout_ms=5000, total_timeout_ms=60000)
    assert result.solved_count == 2
    assert result.total_distance == 0.0


# --- Dépôt-modèle ------------------------------------------------------------


def test_template_client_is_identical_to_the_sdk():
    sdk = (_ROOT / "src" / "orapa_mine" / "solver" / "sdk.py").read_text(encoding="utf-8")
    vendored = (_ROOT / "templates" / "python" / "orapa_client.py").read_text(encoding="utf-8")
    assert vendored == sdk  # le client embarqué ne doit pas diverger


def test_template_example_submits_a_complete_board_and_uses_orientations():
    argv = [sys.executable, str(_TEMPLATE_MAIN)]
    submitted = False
    rotated = False
    for seed in (1, 2, 3):
        grid, _, _ = bm.generate_valid("small", seed=seed)
        result = run_submission(argv, grid, move_timeout_ms=5000, total_timeout_ms=60000)
        if result.distance is not None:  # une proposition complète a été faite
            submitted = True
        if any(m[0] == "place" and m[3] != 0 for m in result.transcript):
            rotated = True
    assert submitted            # l'exemple pose un plateau complet et propose
    assert rotated              # et sait poser une orientation non nulle


# --- Serveur de test local ---------------------------------------------------


def test_localrun_prints_scores(capsys):
    code = localrun.main(["--tier", "small", "--seed", "1", "--", *_REF])
    assert code == 0
    out = capsys.readouterr().out
    assert "TOTAL" in out and "solved=1/1" in out
