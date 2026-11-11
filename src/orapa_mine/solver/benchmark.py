"""Génération et validation des grilles du hackathon (issue #92).

Trois choses :
- un **générateur paramétrable** (taille, extensions, graine) au-dessus de
  `ai.generator` : le nombre d'extensions est tiré au hasard dans `[0, max]`
  selon la taille (sauf si imposé), et les extensions sont choisies au hasard ;
- le **jeu officiel** : 9 grilles = 3 par palier de taille, reproductibles par
  graine, que l'organisateur fige au lancement ;
- un **validateur** : la grille respecte les règles de placement et est
  **résoluble sans ambiguïté** (une seule configuration complète est compatible
  avec ce qu'un solveur peut observer case par case).

Logique pure, aucun pygame.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from orapa_mine.ai.generator import (
    MAX_EXTENSIONS_BY_SIZE,
    Difficulty,
    configuration_problems,
    generate_hidden_grid,
)
from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.beam import fire_beam
from orapa_mine.model.gems import Direction, GemKind, Piece, PlacedGem, Position
from orapa_mine.model.grid import Grid
from orapa_mine.solver import naming

# Plafond d'énumération des configurations compatibles avec les questions de
# case (sécurité : au-delà, on juge la grille trop ambiguë et on la rejette).
_COVER_CAP = 2000


@dataclass(frozen=True)
class Tier:
    name: str
    width: int
    height: int
    max_extensions: int


# Trois paliers = trois tailles ; plafond d'extensions = `MAX_EXTENSIONS_BY_SIZE`.
TIERS: dict[str, Tier] = {
    "small": Tier("small", 8, 6, MAX_EXTENSIONS_BY_SIZE[0]),
    "standard": Tier("standard", 10, 8, MAX_EXTENSIONS_BY_SIZE[1]),
    "large": Tier("large", 12, 10, MAX_EXTENSIONS_BY_SIZE[2]),
}

# Identifiants fil des 5 extensions tirables au hasard.
EXTENSION_IDS: tuple[str, ...] = ("diamond", "filter", "black-body", "wormhole", "mystery")


@dataclass(frozen=True)
class GridSpec:
    """Métadonnées reproductibles d'une grille générée."""

    tier: str
    width: int
    height: int
    extensions: tuple[str, ...]  # ids fil, triés
    seed: int


# --- Génération --------------------------------------------------------------


def generate(
    tier: str,
    *,
    seed: int,
    extensions: list[str] | None = None,
    extension_count: int | None = None,
) -> tuple[Grid, GridSpec, list[Piece]]:
    """Génère une grille reproductible pour un palier.

    - `extensions` : liste imposée d'ids fil (sinon tirage aléatoire) ;
    - `extension_count` : nombre imposé d'extensions (sinon aléatoire dans
      `[0, max]`). Ignoré si `extensions` est fourni.

    Renvoie `(grille, spec, pièces de la palette)`.
    """
    if tier not in TIERS:
        raise ValueError(f"palier inconnu : {tier!r}")
    t = TIERS[tier]
    rng = random.Random(seed)

    if extensions is not None:
        ext_ids = sorted(dict.fromkeys(extensions))  # dédoublonne, ordre stable
        unknown = [e for e in ext_ids if e not in EXTENSION_IDS]
        if unknown:
            raise ValueError(f"extensions inconnues : {unknown}")
        if len(ext_ids) > t.max_extensions:
            raise ValueError(
                f"{len(ext_ids)} extensions > max {t.max_extensions} pour {tier}"
            )
    else:
        if extension_count is None:
            count = rng.randint(0, t.max_extensions)
        else:
            count = max(0, min(extension_count, t.max_extensions))
        ext_ids = sorted(rng.sample(EXTENSION_IDS, count))

    pieces = cat.base_set() + [naming.piece_by_id(e) for e in ext_ids]
    grid = generate_hidden_grid(
        difficulty=Difficulty(pieces=pieces, width=t.width, height=t.height), rng=rng
    )
    spec = GridSpec(tier=tier, width=t.width, height=t.height,
                    extensions=tuple(ext_ids), seed=seed)
    return grid, spec, pieces


def generate_valid(
    tier: str,
    *,
    seed: int,
    extensions: list[str] | None = None,
    extension_count: int | None = None,
    max_tries: int = 100,
) -> tuple[Grid, GridSpec, list[Piece]]:
    """Comme `generate`, mais réessaie (graine +1) jusqu'à une grille **valide**.

    `spec.seed` porte la graine réellement retenue (reproductible)."""
    s = seed
    for _ in range(max_tries):
        grid, spec, pieces = generate(
            tier, seed=s, extensions=extensions, extension_count=extension_count
        )
        if is_valid(grid, pieces):
            return grid, spec, pieces
        s += 1
    raise RuntimeError(f"aucune grille valide pour {tier} après {max_tries} essais")


def official_set(master_seed: int = 2027) -> list[tuple[Grid, GridSpec, list[Piece]]]:
    """Les 9 grilles officielles **valides** : 3 par palier, graines reproductibles.

    À exécuter par l'organisateur au lancement pour figer le jeu caché.
    """
    out: list[tuple[Grid, GridSpec, list[Piece]]] = []
    for ti, tier in enumerate(TIERS):
        for i in range(3):
            seed = master_seed * 1000 + ti * 10 + i
            out.append(generate_valid(tier, seed=seed))
    return out


# --- Validation --------------------------------------------------------------


def _query_signature(gem) -> tuple[str | None, str | None]:
    """Ce qu'une **question de case** révèle d'une gemme : (couleur, nature).

    Gemme normale ou mystère -> couleur (la mystère révèle sa couleur), nature
    None ; extension (diamant/filtre/corps-noir/trou-de-ver) -> nature, couleur
    None. Reproduit `SolverSession.query` (ce qu'un solveur peut observer)."""
    if gem.kind in (GemKind.NORMAL, GemKind.MYSTERY):
        return (naming.color_to_ascii(gem.color), None)
    return (None, naming.kind_to_ascii(gem.kind))


def _candidate_gems(
    piece: Piece, observed: dict[Position, tuple[str | None, str | None]]
) -> list[PlacedGem]:
    """Placements de `piece` compatibles avec `observed` (questions de case).

    Un placement est retenu si toutes ses cases sont occupées et que la signature
    qu'il produit (couleur/nature visible) y correspond exactement. Pour la gemme
    mystère, la couleur devinée est fixée à la couleur observée."""
    if not observed:
        return []
    height = max(p.row for p in observed) + 1
    width = max(p.col for p in observed) + 1
    out: list[PlacedGem] = []
    for orient in piece.orientations():
        max_r = max(p.row for p, _ in orient)
        max_c = max(p.col for p, _ in orient)
        for row in range(height - max_r):
            for col in range(width - max_c):
                gem = PlacedGem(piece=piece, anchor=Position(row, col), orientation=orient)
                cells = gem.absolute_cells()
                if not all(cell in observed for cell in cells):
                    continue
                if piece.kind is GemKind.MYSTERY:
                    colours = {observed[c][0] for c in cells}
                    if len(colours) != 1 or next(iter(colours)) is None:
                        continue
                    color_token = next(iter(colours))
                    gem = PlacedGem(piece=piece, anchor=Position(row, col),
                                    orientation=orient,
                                    override_color=naming.ascii_to_color(color_token))
                    sig = (color_token, None)
                elif piece.kind is GemKind.NORMAL:
                    sig = (naming.color_to_ascii(piece.color), None)
                else:
                    sig = (None, naming.kind_to_ascii(piece.kind))
                if all(observed[c] == sig for c in cells):
                    out.append(gem)
    return out


def _query_consistent_boards(
    grid: Grid, pieces: list[Piece], *, cap: int = _COVER_CAP
) -> list[list[PlacedGem]]:
    """Toutes les configurations complètes compatibles avec les questions de case.

    Pave exactement les cases occupées avec l'inventaire (couleurs/natures
    correspondantes). La vraie grille en fait toujours partie. Borné par `cap`."""
    observed = {cell: _query_signature(grid.owner[cell]) for cell in grid.surface}
    all_cells = set(observed)
    types = {p.name: p for p in pieces}
    counts: Counter = Counter()
    for p in pieces:
        counts[p.name] += p.quantity
    cand = {name: _candidate_gems(types[name], observed) for name in types}
    cells_of = {id(g): frozenset(g.absolute_cells()) for gems in cand.values() for g in gems}

    boards: list[list[PlacedGem]] = []
    covered: set[Position] = set()
    chosen: list[PlacedGem] = []
    remaining = dict(counts)

    def backtrack() -> None:
        if len(boards) >= cap:
            return
        if len(covered) == len(all_cells):
            boards.append(list(chosen))
            return
        target = next(cell for cell in all_cells if cell not in covered)
        for name, gems in cand.items():
            if remaining[name] <= 0:
                continue
            for gem in gems:
                cells = cells_of[id(gem)]
                if target not in cells or cells & covered:
                    continue
                covered.update(cells)
                remaining[name] -= 1
                chosen.append(gem)
                backtrack()
                chosen.pop()
                remaining[name] += 1
                covered.difference_update(cells)
                if len(boards) >= cap:
                    return

    backtrack()
    return boards


def ray_signature(grid: Grid) -> tuple:
    """Signature des tirs de bord : ce qu'un solveur observe par les rayons.

    Pour chaque entrée de bordure (dans la grille), le résultat de `fire_beam`
    (sortie, couleur, absorption). Deux grilles de même signature de rayons **et**
    de mêmes questions de case sont indiscernables."""
    def one(entry: Position, direction: Direction) -> tuple:
        r = fire_beam(grid, entry, direction)
        exit_pt = (r.exit_point.row, r.exit_point.col) if r.exit_point else None
        return (entry.row, entry.col, direction.name, exit_pt, r.color, r.absorbed)

    sig = []
    for row in range(grid.height):
        sig.append(one(Position(row, 0), Direction.RIGHT))
        sig.append(one(Position(row, grid.width - 1), Direction.LEFT))
    for col in range(grid.width):
        sig.append(one(Position(0, col), Direction.DOWN))
        sig.append(one(Position(grid.height - 1, col), Direction.UP))
    return tuple(sig)


def _board_from(width: int, height: int, gems: list[PlacedGem]) -> Grid:
    g = Grid(width=width, height=height)
    for gem in gems:
        g.place_gem(gem)
    return g


def grid_problems(grid: Grid, pieces: list[Piece]) -> list[str]:
    """Problèmes d'une grille : règles de placement + ambiguïté. Vide si OK.

    Codes : "touche"/"cachée" (règles, via `ai.generator`), "ambiguous" (une autre
    configuration complète produit les mêmes questions de case **et** les mêmes
    rayons), "unsolvable" (aucune configuration compatible — ne doit pas arriver).
    Un solveur dispose des questions **et** des rayons : une grille n'est ambiguë
    que si deux configurations coïncident sur les deux."""
    problems = [code for code, _gem in configuration_problems(grid)]

    boards = _query_consistent_boards(grid, pieces)
    if not boards:
        problems.append("unsolvable")
        return problems
    if len(boards) >= _COVER_CAP:  # trop de configurations à départager : prudence
        problems.append("ambiguous")
        return problems

    truth_sig = ray_signature(grid)
    matches = 0
    for board in boards:
        if ray_signature(_board_from(grid.width, grid.height, board)) == truth_sig:
            matches += 1
            if matches >= 2:
                break
    if matches == 0:  # défensif : la vérité doit correspondre à elle-même
        problems.append("unsolvable")
    elif matches >= 2:
        problems.append("ambiguous")
    return problems


def is_valid(grid: Grid, pieces: list[Piece]) -> bool:
    """Vrai si la grille est bien formée et résoluble sans ambiguïté."""
    return not grid_problems(grid, pieces)


# --- Sérialisation fichier + CLI organisateur --------------------------------


def save_grid(path, grid: Grid, spec: GridSpec, pieces: list[Piece]) -> None:
    """Écrit une grille (config seule) + ses métadonnées de génération en JSON."""
    import json
    from pathlib import Path

    from orapa_mine.model import serialization

    data = serialization.to_dict(
        width=spec.width, height=spec.height, palette_pieces=pieces,
        hidden_grid=grid, include_progress=False,
    )
    data["benchmark"] = {"tier": spec.tier, "extensions": list(spec.extensions), "seed": spec.seed}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_grid(path) -> tuple[Grid, list[Piece], dict | None]:
    """Relit une grille sauvegardée : (grille cachée, palette, métadonnées)."""
    import json
    from pathlib import Path

    from orapa_mine.model import serialization

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    loaded = serialization.from_dict(data)
    return loaded.game.hidden_grid, loaded.palette_pieces, data.get("benchmark")


def main(argv: list[str] | None = None) -> int:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Grilles du hackathon Orapa Mine (#92).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="générer une grille")
    g.add_argument("--tier", choices=list(TIERS), required=True)
    g.add_argument("--seed", type=int, required=True)
    g.add_argument("--extensions", help="ids fil séparés par des virgules (sinon aléatoire)")
    g.add_argument("--count", type=int, help="nombre d'extensions (sinon aléatoire)")
    g.add_argument("--out", required=True, help="fichier JSON de sortie")

    o = sub.add_parser("official", help="générer le jeu officiel (9 grilles)")
    o.add_argument("--seed", type=int, default=2027)
    o.add_argument("--out-dir", required=True)

    v = sub.add_parser("validate", help="valider une grille JSON")
    v.add_argument("file")

    args = parser.parse_args(argv)

    if args.cmd == "generate":
        exts = args.extensions.split(",") if args.extensions else None
        grid, spec, pieces = generate_valid(
            args.tier, seed=args.seed, extensions=exts, extension_count=args.count
        )
        save_grid(args.out, grid, spec, pieces)
        print(f"{args.out}: {spec.tier} {spec.width}x{spec.height} "
              f"extensions={list(spec.extensions)} seed={spec.seed}")
        return 0

    if args.cmd == "official":
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for idx, (grid, spec, pieces) in enumerate(official_set(args.seed)):
            path = out_dir / f"{idx:02d}-{spec.tier}.json"
            save_grid(path, grid, spec, pieces)
            print(f"{path}: {spec.tier} extensions={list(spec.extensions)} seed={spec.seed}")
        return 0

    if args.cmd == "validate":
        grid, pieces, meta = load_grid(args.file)
        problems = grid_problems(grid, pieces)
        if problems:
            print(f"INVALIDE : {args.file} -> {problems}")
            return 1
        print(f"OK : {args.file} ({meta})")
        return 0

    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(main(sys.argv[1:]))
