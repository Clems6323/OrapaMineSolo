"""Solveur de référence (issue #94) — baseline correct, non optimisé.

Stratégie simple qui résout **toute grille valide** : interroger chaque case
(pour connaître les cases occupées, leurs couleurs/natures), reconstruire les
configurations compatibles (pavage exact de l'inventaire), puis — s'il en reste
plusieurs — les départager en tirant des rayons réels et en simulant chaque
candidate. Enfin poser et proposer.

Il coûte cher en points (beaucoup de questions) : c'est volontairement une base
à battre. Contrairement au client (`sdk.py`, autonome), il **utilise le moteur**
`orapa_mine.model` pour simuler les rayons ; un solveur dans un autre langage
réimplémenterait cette logique.

Lancement comme soumission : `python -m orapa_mine.solver.reference_solver`.
"""

from __future__ import annotations

from orapa_mine.model.beam import fire_beam
from orapa_mine.model.gems import Direction, GemKind, Position
from orapa_mine.model.grid import Grid
from orapa_mine.solver import benchmark, naming
from orapa_mine.solver.sdk import run


def _grid_of(width: int, height: int, board) -> Grid:
    g = Grid(width=width, height=height)
    for gem in board:
        g.place_gem(gem)
    return g


def _border_entries(width: int, height: int) -> list[tuple[Position, Direction]]:
    entries: list[tuple[Position, Direction]] = []
    for row in range(height):
        entries.append((Position(row, 0), Direction.RIGHT))
        entries.append((Position(row, width - 1), Direction.LEFT))
    for col in range(width):
        entries.append((Position(0, col), Direction.DOWN))
        entries.append((Position(height - 1, col), Direction.UP))
    return entries


def _predicted_shot(grid: Grid, entry: Position, direction: Direction) -> tuple:
    r = fire_beam(grid, entry, direction)
    exit_pt = {"row": r.exit_point.row, "col": r.exit_point.col} if r.exit_point else None
    return (exit_pt, naming.ray_color_to_ascii(r.color), r.absorbed)


def solve(client) -> None:
    width, height = client.width, client.height

    # 1. Interroger toutes les cases -> cases occupées (couleur/nature visible).
    observed: dict[Position, tuple[str | None, str | None]] = {}
    for row in range(height):
        for col in range(width):
            resp = client.query(row, col)
            if resp["occupied"]:
                observed[Position(row, col)] = (resp["color"], resp["kind"])

    # 2. Reconstruire les configurations compatibles avec ces questions.
    pieces = [naming.piece_by_id(item["piece"]) for item in client.inventory]
    boards = benchmark.query_consistent_boards_from_observed(observed, pieces)
    if not boards:
        client.give_up()
        return

    # 3. Départager par rayons réels (simule chaque candidate, garde celles qui
    #    coïncident), jusqu'à une seule.
    if len(boards) > 1:
        for entry, direction in _border_entries(width, height):
            target = client.shoot(entry.row, entry.col, direction.name)
            observed_shot = (target["exit"], target["color"], target["absorbed"])
            boards = [
                b for b in boards
                if _predicted_shot(_grid_of(width, height, b), entry, direction) == observed_shot
            ]
            if len(boards) <= 1:
                break

    # 4. Poser la configuration retenue, puis proposer.
    for gem in boards[0]:
        piece_id = naming.piece_id(gem.piece.name)
        orient = gem.piece.variant_index(gem)
        color = naming.color_to_ascii(gem.color) if gem.kind is GemKind.MYSTERY else None
        client.place(piece_id, gem.anchor.row, gem.anchor.col, orient, color)
    client.submit()


def main() -> None:
    run(solve)


if __name__ == "__main__":
    main()
