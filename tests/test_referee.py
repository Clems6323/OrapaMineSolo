"""Arbitre : dispatch du protocole + robustesse sous-processus (issue #91)."""

from __future__ import annotations

import json
import sys
import textwrap

import pytest

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.gems import Position
from orapa_mine.model.grid import Grid
from orapa_mine.solver import referee
from orapa_mine.solver.referee import (
    ChannelClosed,
    ChannelTimeout,
    SolverSession,
    build_hello,
    drive,
    run_submission,
)


def _yellow_truth() -> Grid:
    g = Grid(width=10, height=8)
    g.place_gem(cat.YELLOW.at(Position(2, 2)))
    return g


def _line(**obj) -> str:
    return json.dumps(obj)


class FakeChannel:
    """Canal en mémoire : `recv` débite des lignes brutes (ou lève une erreur)."""

    def __init__(self, inputs: list) -> None:
        self._inputs = list(inputs)
        self.sent: list[dict] = []

    def send(self, obj: dict) -> None:
        self.sent.append(obj)

    def recv(self, timeout: float):
        if not self._inputs:
            raise ChannelClosed()
        item = self._inputs.pop(0)
        if isinstance(item, type) and issubclass(item, Exception):
            raise item()
        return item


def _run(truth: Grid, inputs: list, **kw):
    session = SolverSession(truth)
    hello = build_hello(session, truth, max_proposals=5, move_timeout_ms=1000, cpu_time_ms=10000)
    channel = FakeChannel(inputs)
    reason, moves = drive(session, channel, hello, move_timeout_s=1.0, **kw)
    return session, channel, reason, moves


# --- Dispatch nominal --------------------------------------------------------


def test_hello_carries_inventory_and_limits():
    session = SolverSession(_yellow_truth())
    hello = build_hello(session, _yellow_truth(), max_proposals=5,
                        move_timeout_ms=1000, cpu_time_ms=10000)
    assert hello["type"] == "hello" and hello["protocol"] == 1
    assert hello["width"] == 10 and hello["height"] == 8
    assert hello["max_proposals"] == 5
    assert any(it["piece"] == "yellow" for it in hello["inventory"])
    assert hello["limits"]["cpu_time_ms"] == 10000


def test_drive_place_and_submit_wins():
    session, channel, reason, moves = _run(
        _yellow_truth(),
        [_line(type="place", piece="yellow", anchor={"row": 2, "col": 2}, orient=0),
         _line(type="submit")],
    )
    assert reason is None
    assert session.solved is True
    kinds = [m["type"] for m in channel.sent]
    assert kinds == ["hello", "ack", "result"]
    assert channel.sent[-1]["won"] is True


def test_drive_shot_and_cell_dispatch():
    session, channel, reason, moves = _run(
        _yellow_truth(),
        [_line(type="shoot", entry={"row": 2, "col": 0}, direction="RIGHT"),
         _line(type="query", cell={"row": 2, "col": 2}),
         _line(type="give_up")],
    )
    shot = next(m for m in channel.sent if m["type"] == "shot")
    cell = next(m for m in channel.sent if m["type"] == "cell")
    assert "absorbed" in shot and "exit" in shot
    assert cell["occupied"] is True and cell["color"] == "yellow" and cell["kind"] is None


# --- Rejets (le jeu continue) ------------------------------------------------


def test_illegal_place_is_rejected_then_play_continues():
    session, channel, reason, moves = _run(
        _yellow_truth(),
        [_line(type="place", piece="yellow", anchor={"row": 7, "col": 9}, orient=0),  # déborde
         _line(type="give_up")],
    )
    rejects = [m for m in channel.sent if m["type"] == "reject"]
    assert rejects and rejects[0]["reason"] == "illegal_move"
    assert reason is None  # abandon = fin propre, pas une faute


def test_incomplete_submit_is_rejected_then_can_win():
    session, channel, reason, moves = _run(
        _yellow_truth(),
        [_line(type="submit"),  # plateau vide -> reject incomplete_board
         _line(type="place", piece="yellow", anchor={"row": 2, "col": 2}, orient=0),
         _line(type="submit")],
    )
    assert any(m["type"] == "reject" and m["reason"] == "incomplete_board" for m in channel.sent)
    assert session.solved is True


def test_unknown_piece_is_rejected():
    session, channel, reason, moves = _run(
        _yellow_truth(),
        [_line(type="place", piece="banana", anchor={"row": 0, "col": 0}, orient=0),
         _line(type="give_up")],
    )
    assert any(m["type"] == "reject" and m["reason"] == "unknown_piece" for m in channel.sent)


def test_five_wrong_submits_end_the_grid():
    session, channel, reason, moves = _run(
        _yellow_truth(),
        [_line(type="place", piece="yellow", anchor={"row": 5, "col": 5}, orient=0)]
        + [_line(type="submit")] * 5,
    )
    assert reason is None
    assert session.solved is False
    assert session.finished is True
    results = [m for m in channel.sent if m["type"] == "result"]
    assert results[-1]["remaining_proposals"] == 0


# --- Fautes (fin de grille) --------------------------------------------------


def test_unknown_type_is_a_malformed_fault():
    _, _, reason, _ = _run(_yellow_truth(), [_line(type="wat")])
    assert reason == "malformed"


def test_bad_json_is_a_malformed_fault():
    _, _, reason, _ = _run(_yellow_truth(), ["this is not json"])
    assert reason == "malformed"


def test_eof_is_a_fault():
    _, _, reason, _ = _run(_yellow_truth(), [])  # recv -> ChannelClosed
    assert reason == "eof"


def test_move_timeout_is_a_fault():
    _, _, reason, _ = _run(_yellow_truth(), [ChannelTimeout])
    assert reason == "move_timeout"


# --- Sous-processus réel : robustesse ----------------------------------------


def _solver(tmp_path, body: str) -> list[str]:
    script = tmp_path / "solver.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return [sys.executable, str(script)]


def test_subprocess_give_up_is_clean_unsolved(tmp_path):
    argv = _solver(tmp_path, """
        import sys, json
        for line in sys.stdin:
            msg = json.loads(line)
            if msg["type"] == "hello":
                print(json.dumps({"type": "give_up"}), flush=True)
            elif msg["type"] in ("result", "end"):
                break
    """)
    result = run_submission(argv, _yellow_truth(), move_timeout_ms=2000)
    assert result.solved is False
    assert result.dnf_reason is None          # abandon = propre
    assert result.distance is None            # aucune proposition complète
    assert result.wall_time_ms >= 0
    assert result.cpu_time_ms is None or result.cpu_time_ms >= 0


def test_subprocess_crash_is_eof_fault(tmp_path):
    argv = _solver(tmp_path, """
        import sys
        sys.exit(0)
    """)
    result = run_submission(argv, _yellow_truth(), move_timeout_ms=2000)
    assert result.solved is False
    assert result.dnf_reason == "eof"


def test_subprocess_hang_hits_move_timeout(tmp_path):
    argv = _solver(tmp_path, """
        import sys, json, time
        for line in sys.stdin:
            if json.loads(line)["type"] == "hello":
                time.sleep(30)
    """)
    result = run_submission(argv, _yellow_truth(), move_timeout_ms=200)
    assert result.dnf_reason == "move_timeout"


def test_spawn_failure_is_contained():
    result = run_submission(["this-binary-does-not-exist-xyz"], _yellow_truth())
    assert result.dnf_reason == "spawn_failed"


# --- Les messages émis respectent le schéma (si jsonschema présent) ----------


def test_emitted_messages_validate_against_schema(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    from pathlib import Path

    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schema" / "hackathon_protocol.schema.json")
        .read_text(encoding="utf-8")
    )
    _, channel, _, _ = _run(
        _yellow_truth(),
        [_line(type="shoot", entry={"row": 2, "col": 0}, direction="RIGHT"),
         _line(type="query", cell={"row": 2, "col": 2}),
         _line(type="place", piece="yellow", anchor={"row": 2, "col": 2}, orient=0),
         _line(type="submit")],
    )
    for msg in channel.sent:  # hello, shot, cell, ack, result
        jsonschema.validate(msg, schema)
