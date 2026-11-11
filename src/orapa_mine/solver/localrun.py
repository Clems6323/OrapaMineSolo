"""Serveur de test local (issue #94) : jouer son solveur sur des grilles locales.

Génère une ou plusieurs grilles d'entraînement (paramètres au choix) et fait
jouer la commande du solveur dessus, en affichant le **même score** que le
serveur officiel (distance -> points -> temps CPU). Aucune persistance, aucun
classement : purement pour itérer en local.

Exemples :
    uv run --no-sync python -m orapa_mine.solver.localrun -- python main.py
    uv run --no-sync python -m orapa_mine.solver.localrun --tier small --seed 3 -- python main.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from orapa_mine.solver import benchmark
from orapa_mine.solver.evaluate import GridEntry, evaluate, to_json


def build_entries(*, tier: str | None, seed: int) -> list[GridEntry]:
    """Une grille du palier demandé, ou un échantillon (une par palier)."""
    if tier is not None:
        grid, spec, _ = benchmark.generate_valid(tier, seed=seed)
        return [GridEntry(f"{tier}-{spec.seed}", tier, grid)]
    entries: list[GridEntry] = []
    for i, name in enumerate(benchmark.TIERS):
        grid, spec, _ = benchmark.generate_valid(name, seed=seed + i)
        entries.append(GridEntry(f"{name}-{spec.seed}", name, grid))
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serveur de test local Orapa Mine (#94).")
    parser.add_argument("--tier", choices=list(benchmark.TIERS),
                        help="un seul palier (sinon un échantillon : une grille par palier)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", help="écrire aussi l'artefact JSON de résultats")
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="commande du solveur (après --), ex. -- python main.py")
    args = parser.parse_args(argv)

    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command:
        parser.error("commande du solveur manquante (après --)")

    entries = build_entries(tier=args.tier, seed=args.seed)
    result = evaluate(command, entries)
    data = to_json(result)
    if args.out:
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    for g in data["grids"]:
        print(f"{g['grid_id']:16} solved={str(g['solved']):5} "
              f"dist={g['distance']:.3f} pts={g['points']} cpu_ms={g['cpu_time_ms']}")
    t = data["total"]
    print(f"TOTAL  distance={t['distance']:.3f}  points={t['points']}  "
          f"cpu_ms={t['cpu_time_ms']}  solved={t['solved']}/{t['grids']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(main(sys.argv[1:]))
