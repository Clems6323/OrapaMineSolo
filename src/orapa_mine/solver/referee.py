"""Arbitre : fait jouer un programme participant sur une grille (issue #91).

Transforme les lignes JSON d'une soumission en coups sur une `SolverSession`,
applique le protocole (#90), impose les limites (délai par coup, temps total,
taille de sortie) et produit un `GridResult` par grille. Logique pure côté
dispatch (testable sans sous-processus) ; le transport (sous-processus + files)
est isolé dans `SubprocessChannel`.

Aucune règle de jeu ici : tout passe par `SolverSession`. Aucun import pygame.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from orapa_mine.model.gems import Direction, GemKind, Position
from orapa_mine.model.grid import Grid
from orapa_mine.solver import naming
from orapa_mine.solver.session import SolverError, SolverSession

# Mesure du temps CPU des sous-processus (enfants) : stdlib `resource` sous
# POSIX (plateforme Docker Linux officielle), indisponible sous Windows -> None.
try:  # pragma: no cover - dépend de l'OS
    import resource

    def _cpu_children_s() -> float:
        r = resource.getrusage(resource.RUSAGE_CHILDREN)
        return r.ru_utime + r.ru_stime
except ImportError:  # pragma: no cover - Windows
    _cpu_children_s = None  # type: ignore[assignment]

_MAX_LINE_BYTES = 1_000_000   # une ligne de sortie plus longue = débordement
_MAX_MOVES = 1_000_000        # borne les boucles de messages sans fin


# --- Canal de transport ------------------------------------------------------


class ChannelClosed(Exception):
    """Le programme a fermé sa sortie (EOF)."""


class ChannelTimeout(Exception):
    """Aucune ligne reçue dans le délai imparti."""


class ChannelOverflow(Exception):
    """Ligne de sortie trop longue (sortie abusive)."""


class SubprocessChannel:
    """Canal sur les flux stdin/stdout d'un sous-processus (lignes JSON).

    Un fil lecteur découple la lecture bloquante ; `recv(timeout)` renvoie la
    prochaine ligne, lève `ChannelTimeout`/`ChannelClosed`/`ChannelOverflow`.
    """

    def __init__(self, process: subprocess.Popen) -> None:
        self._p = process
        self._q: queue.Queue = queue.Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        try:
            for raw in self._p.stdout:  # type: ignore[union-attr]
                if len(raw) > _MAX_LINE_BYTES:
                    self._q.put(("overflow", None))
                    break
                self._q.put(("line", raw))
        except Exception:  # lecture interrompue (processus tué)
            pass
        self._q.put(("eof", None))

    def send(self, obj: dict) -> None:
        line = json.dumps(obj, separators=(",", ":")) + "\n"
        try:
            self._p.stdin.write(line)  # type: ignore[union-attr]
            self._p.stdin.flush()  # type: ignore[union-attr]
        except (BrokenPipeError, OSError):
            raise ChannelClosed()

    def recv(self, timeout: float) -> str:
        try:
            kind, payload = self._q.get(timeout=timeout)
        except queue.Empty:
            raise ChannelTimeout()
        if kind == "eof":
            raise ChannelClosed()
        if kind == "overflow":
            raise ChannelOverflow()
        return payload

    def close(self) -> None:
        for stream in (self._p.stdin, self._p.stdout):
            try:
                if stream:
                    stream.close()
            except OSError:
                pass


# --- Résultat ----------------------------------------------------------------


@dataclass
class GridResult:
    """Résultat d'une grille pour une soumission."""

    solved: bool
    points: int
    distance: float | None       # meilleure distance (propositions complètes), None si aucune
    moves: int
    dnf_reason: str | None       # None si fin « propre » (gagné / 5 essais / abandon) ; sinon faute
    cpu_time_ms: int | None
    wall_time_ms: int
    transcript: list = field(default_factory=list)


# --- Dispatch des commandes (pur) --------------------------------------------


def _pos(d: dict) -> Position:
    return Position(int(d["row"]), int(d["col"]))


def _pos_payload(p: Position | None) -> dict | None:
    return None if p is None else {"row": p.row, "col": p.col}


def inventory_payload(session: SolverSession) -> list[dict]:
    """Charge utile « inventaire » (hello / réponse à `pieces`)."""
    items = []
    for item in session.pieces().items:
        items.append(
            {
                "piece": item.piece,
                "quantity": item.quantity,
                "orientations": [
                    [{"row": r, "col": c, "half": h} for r, c, h in shape.cells]
                    for shape in item.orientations
                ],
            }
        )
    return items


def _handle_pieces(session: SolverSession, msg: dict) -> dict:
    return {"type": "inventory", "pieces": inventory_payload(session), "mystery_color": None}


def _handle_shoot(session: SolverSession, msg: dict) -> dict:
    res = session.shoot(_pos(msg["entry"]), Direction[msg["direction"]])
    return {"type": "shot", "exit": _pos_payload(res.exit), "color": res.color, "absorbed": res.absorbed}


def _handle_query(session: SolverSession, msg: dict) -> dict:
    res = session.query(_pos(msg["cell"]))
    return {"type": "cell", "occupied": res.occupied, "color": res.color, "kind": res.kind}


def _handle_place(session: SolverSession, msg: dict) -> dict:
    session.place(msg["piece"], _pos(msg["anchor"]), int(msg["orient"]), msg.get("color"))
    return {"type": "ack"}


def _handle_remove(session: SolverSession, msg: dict) -> dict:
    session.remove(_pos(msg["cell"]))
    return {"type": "ack"}


def _handle_submit(session: SolverSession, msg: dict) -> dict:
    res = session.submit()
    return {"type": "result", "won": res.won, "points": res.points,
            "remaining_proposals": res.remaining_proposals}


def _handle_give_up(session: SolverSession, msg: dict) -> dict:
    session.give_up()
    return {"type": "result", "won": False, "points": session.points,
            "remaining_proposals": session.remaining_proposals}


_HANDLERS: dict[str, Callable[[SolverSession, dict], dict]] = {
    "pieces": _handle_pieces,
    "shoot": _handle_shoot,
    "query": _handle_query,
    "place": _handle_place,
    "remove": _handle_remove,
    "submit": _handle_submit,
    "give_up": _handle_give_up,
}


def build_hello(session: SolverSession, grid: Grid, *, max_proposals: int,
                move_timeout_ms: int, cpu_time_ms: int) -> dict:
    ext_ids = {naming.piece_id(p.name) for p in {g.piece for g in grid.gems}
               if p.kind is not GemKind.NORMAL}
    return {
        "type": "hello",
        "protocol": 1,
        "width": grid.width,
        "height": grid.height,
        "extensions": sorted(ext_ids),
        "max_proposals": max_proposals,
        "inventory": inventory_payload(session),
        "limits": {"move_timeout_ms": move_timeout_ms, "cpu_time_ms": cpu_time_ms},
    }


# --- Boucle de jeu (transport abstrait) --------------------------------------


def drive(
    session: SolverSession,
    channel,
    hello: dict,
    *,
    move_timeout_s: float,
    total_timeout_s: float | None = None,
    now: Callable[[], float] = time.monotonic,
) -> tuple[str | None, int]:
    """Joue une partie en parlant à `channel`. Renvoie (raison de faute|None, coups).

    Ne mesure pas le CPU (fait par `run_submission`) ; `now` injectable pour les
    tests. Envoie `hello` au début ; **n'envoie pas `end`** (l'appelant le fait
    après avoir mesuré le temps).
    """
    channel.send(hello)
    start = now()
    reason: str | None = None
    moves = 0
    while not session.finished:
        if total_timeout_s is not None and now() - start > total_timeout_s:
            reason = "timeout"
            break
        try:
            line = channel.recv(move_timeout_s)
        except ChannelTimeout:
            reason = "move_timeout"
            break
        except ChannelOverflow:
            reason = "output_overflow"
            break
        except ChannelClosed:
            reason = "eof"
            break

        moves += 1
        if moves > _MAX_MOVES:
            reason = "too_many_moves"
            break

        try:
            msg = json.loads(line)
            mtype = msg["type"] if isinstance(msg, dict) else None
        except (json.JSONDecodeError, TypeError):
            reason = "malformed"
            break
        handler = _HANDLERS.get(mtype)
        if handler is None:
            reason = "malformed"  # type inconnu / manquant
            break

        try:
            response = handler(session, msg)
        except SolverError as exc:
            response = {"type": "reject", "reason": exc.reason}
        except (KeyError, TypeError, ValueError):
            response = {"type": "reject", "reason": "illegal_move"}
        try:
            channel.send(response)
        except ChannelClosed:
            reason = "eof"
            break
    return reason, moves


def _result(session: SolverSession, reason: str | None, moves: int,
            cpu_time_ms: int | None, wall_time_ms: int) -> GridResult:
    return GridResult(
        solved=session.solved,
        points=session.points,
        distance=session.best_distance(),
        moves=moves,
        dnf_reason=reason,
        cpu_time_ms=cpu_time_ms,
        wall_time_ms=wall_time_ms,
        transcript=session.transcript,
    )


# --- Exécution d'une soumission (sous-processus réel) ------------------------


def run_submission(
    command: list[str],
    grid: Grid,
    *,
    max_proposals: int = 5,
    move_timeout_ms: int = 2000,
    cpu_time_ms: int = 10000,
    total_timeout_ms: int | None = 30000,
) -> GridResult:
    """Lance `command` (argv) et le fait jouer `grid`. Toujours un `GridResult`.

    Un programme qui plante, boucle, dépasse les limites ou émet du charabia est
    contenu : `dnf_reason` renseigné, jamais d'exception propagée.
    """
    session = SolverSession(grid, max_proposals=max_proposals)
    hello = build_hello(session, grid, max_proposals=max_proposals,
                        move_timeout_ms=move_timeout_ms, cpu_time_ms=cpu_time_ms)

    cpu0 = _cpu_children_s() if _cpu_children_s is not None else None
    wall0 = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
    except (OSError, ValueError):
        wall_ms = int((time.monotonic() - wall0) * 1000)
        return _result(session, "spawn_failed", 0, None, wall_ms)

    channel = SubprocessChannel(process)
    try:
        reason, moves = drive(
            session, channel, hello,
            move_timeout_s=move_timeout_ms / 1000.0,
            total_timeout_s=None if total_timeout_ms is None else total_timeout_ms / 1000.0,
        )
        # Dernier message pour le programme (il peut l'ignorer / être déjà mort).
        try:
            channel.send({"type": "end", "solved": session.solved,
                          "points": session.points, "cpu_time_ms": 0})
        except ChannelClosed:
            pass
    finally:
        try:
            process.terminate()
        except OSError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:  # pragma: no cover - processus récalcitrant
            process.kill()
            process.wait(timeout=2)
        channel.close()

    wall_ms = int((time.monotonic() - wall0) * 1000)
    cpu_ms = None
    if cpu0 is not None and _cpu_children_s is not None:  # pragma: no cover - POSIX
        cpu_ms = max(0, int((_cpu_children_s() - cpu0) * 1000))
    return _result(session, reason, moves, cpu_ms, wall_ms)
