"""Évaluation d'une soumission sur un jeu de grilles (issue #93).

Fait jouer une soumission (via l'arbitre #91) sur chaque grille, note chacune
`(distance, points, temps CPU)`, puis agrège. Classement **lexicographique,
tout croissant** : distance à la vérité, puis points, puis temps CPU. Une grille
sans proposition complète prend la distance sentinelle `DNF_SENTINEL_DISTANCE`.

Logique pure (aucun pygame). Produit un artefact JSON exploitable par le
classement (#95) et pour l'audit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from orapa_mine.model.grid import Grid
from orapa_mine.solver import benchmark
from orapa_mine.solver.referee import GridResult, run_submission
from orapa_mine.solver.session import DEFAULT_MAX_PROPOSALS

# Distance d'une grille sans aucune proposition complète (plante / délai /
# abandon) : constante isolée et documentée (#88/#93).
DNF_SENTINEL_DISTANCE = 1000.0


@dataclass(frozen=True)
class GridEntry:
    """Une grille du jeu à évaluer."""

    grid_id: str
    tier: str
    grid: Grid


@dataclass(frozen=True)
class GridScore:
    """Note d'une soumission sur une grille."""

    grid_id: str
    tier: str
    solved: bool
    distance: float      # distance de scoring (sentinelle si aucune proposition complète)
    points: int
    cpu_time_ms: int     # CPU si mesuré, sinon temps mur (repli hors POSIX)
    dnf_reason: str | None
    moves: int


@dataclass(frozen=True)
class SubmissionResult:
    """Agrégat d'une soumission sur tout le jeu."""

    total_distance: float
    total_points: int
    total_cpu_time_ms: int
    solved_count: int
    grid_count: int
    per_tier: dict[str, dict]
    grids: list[GridScore] = field(default_factory=list)

    @property
    def ranking_key(self) -> tuple[float, int, int]:
        """Clé de tri : distance, puis points, puis temps CPU (tout croissant)."""
        return (self.total_distance, self.total_points, self.total_cpu_time_ms)


# --- Notation ----------------------------------------------------------------


def score_grid(result: GridResult, grid_id: str, tier: str) -> GridScore:
    """Transforme un `GridResult` de l'arbitre en note de grille.

    `distance` = meilleure proposition complète, ou `DNF_SENTINEL_DISTANCE` si
    aucune. `cpu_time_ms` = CPU mesuré, sinon temps mur (repli hors POSIX)."""
    distance = DNF_SENTINEL_DISTANCE if result.distance is None else result.distance
    cpu = result.cpu_time_ms if result.cpu_time_ms is not None else result.wall_time_ms
    return GridScore(
        grid_id=grid_id, tier=tier, solved=result.solved, distance=distance,
        points=result.points, cpu_time_ms=cpu, dnf_reason=result.dnf_reason,
        moves=result.moves,
    )


def aggregate(scores: list[GridScore]) -> SubmissionResult:
    """Agrège des notes de grille : totaux, sous-totaux par palier, résolues."""
    per_tier: dict[str, dict] = {}
    for s in scores:
        d = per_tier.setdefault(
            s.tier, {"distance": 0.0, "points": 0, "cpu_time_ms": 0, "solved": 0, "count": 0}
        )
        d["distance"] += s.distance
        d["points"] += s.points
        d["cpu_time_ms"] += s.cpu_time_ms
        d["solved"] += int(s.solved)
        d["count"] += 1
    return SubmissionResult(
        total_distance=sum(s.distance for s in scores),
        total_points=sum(s.points for s in scores),
        total_cpu_time_ms=sum(s.cpu_time_ms for s in scores),
        solved_count=sum(1 for s in scores if s.solved),
        grid_count=len(scores),
        per_tier=per_tier,
        grids=list(scores),
    )


def rank(results: dict[str, SubmissionResult]) -> list[tuple[str, SubmissionResult]]:
    """Classe des soumissions (nom -> résultat) : meilleure (plus basse) d'abord."""
    return sorted(results.items(), key=lambda kv: kv[1].ranking_key)


# --- Évaluation d'une soumission ---------------------------------------------


def evaluate(
    command: list[str],
    entries: list[GridEntry],
    *,
    max_proposals: int = DEFAULT_MAX_PROPOSALS,
    move_timeout_ms: int = 2000,
    cpu_time_ms: int = 10000,
    total_timeout_ms: int | None = 30000,
) -> SubmissionResult:
    """Fait jouer `command` sur chaque grille et agrège le résultat."""
    scores: list[GridScore] = []
    for entry in entries:
        result = run_submission(
            command, entry.grid, max_proposals=max_proposals,
            move_timeout_ms=move_timeout_ms, cpu_time_ms=cpu_time_ms,
            total_timeout_ms=total_timeout_ms,
        )
        scores.append(score_grid(result, entry.grid_id, entry.tier))
    return aggregate(scores)


# --- Artefact JSON -----------------------------------------------------------


def to_json(result: SubmissionResult) -> dict:
    """Artefact structuré (totaux + sous-totaux + lignes par grille)."""
    return {
        "total": {
            "distance": result.total_distance,
            "points": result.total_points,
            "cpu_time_ms": result.total_cpu_time_ms,
            "solved": result.solved_count,
            "grids": result.grid_count,
        },
        "per_tier": result.per_tier,
        "grids": [
            {
                "grid_id": g.grid_id,
                "tier": g.tier,
                "solved": g.solved,
                "distance": g.distance,
                "points": g.points,
                "cpu_time_ms": g.cpu_time_ms,
                "dnf_reason": g.dnf_reason,
                "moves": g.moves,
            }
            for g in result.grids
        ],
    }


# --- Chargement d'un jeu de grilles + CLI ------------------------------------


def load_grid_set(directory) -> list[GridEntry]:
    """Charge toutes les grilles `*.json` d'un dossier (triées par nom)."""
    entries: list[GridEntry] = []
    for path in sorted(Path(directory).glob("*.json")):
        grid, _pieces, meta = benchmark.load_grid(path)
        tier = (meta or {}).get("tier", "unknown")
        entries.append(GridEntry(grid_id=path.stem, tier=tier, grid=grid))
    return entries


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Évalue une soumission sur un jeu de grilles (#93)."
    )
    parser.add_argument("grid_dir", help="dossier de grilles JSON")
    parser.add_argument("out", help="fichier JSON de résultats")
    parser.add_argument(
        "command", nargs=argparse.REMAINDER,
        help="commande de la soumission (après --), ex. -- python solver.py",
    )
    args = parser.parse_args(argv)

    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command:
        parser.error("commande de soumission manquante (après --)")

    entries = load_grid_set(args.grid_dir)
    result = evaluate(command, entries)
    Path(args.out).write_text(
        json.dumps(to_json(result), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"{args.out}: distance={result.total_distance:.3f} "
        f"points={result.total_points} cpu_ms={result.total_cpu_time_ms} "
        f"solved={result.solved_count}/{result.grid_count}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(main(sys.argv[1:]))
