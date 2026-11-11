#!/usr/bin/env python3
"""Solveur exemple — point de départ à modifier.

Stratégie (volontairement simple) : interroger chaque case pour connaître les
cases occupées et leurs couleurs/natures, reconstruire un pavage de l'inventaire
compatible avec ces observations, le poser, puis proposer.

Il résout les grilles entièrement déterminées par les questions de case ; sur
les autres il propose sa première reconstruction compatible. Pour faire mieux
(moins de points, départager par les rayons), remplace `solve`. Un solveur de
référence complet (questions + rayons) est fourni par le projet :
`python -m orapa_mine.solver.reference_solver`.

Dépend uniquement de `orapa_client.py` (stdlib) : aucune autre dépendance.
"""

from __future__ import annotations

from orapa_client import run

# Les ids de pièces portent leur couleur (gemmes normales) ou leur nature
# (extensions) ; la mystère est révélée par les questions de case.
NORMAL_COLOUR = {
    "red": "red", "yellow": "yellow", "blue": "blue",
    "white-big": "white", "white-small": "white",
}
EXTENSION_KIND = {
    "diamond": "diamond", "filter": "filter",
    "black-body": "black-body", "wormhole": "wormhole",
}


def solve(client) -> None:
    width, height = client.width, client.height

    # 1. Interroger toutes les cases.
    observed = {}  # (row, col) -> (couleur, nature) visibles
    for row in range(height):
        for col in range(width):
            resp = client.query(row, col)
            if resp["occupied"]:
                observed[(row, col)] = (resp["color"], resp["kind"])

    # 2. Placements possibles de chaque pièce, compatibles avec les observations.
    placements = {}  # id -> list de (cases, orient, (ancre_r, ancre_c), couleur_devinée)
    for item in client.inventory:
        pid = item["piece"]
        plist = []
        for orient_index, orientation in enumerate(item["orientations"]):
            rel = [(cell["row"], cell["col"]) for cell in orientation]
            max_r = max(r for r, _ in rel)
            max_c = max(c for _, c in rel)
            for ar in range(height - max_r):
                for ac in range(width - max_c):
                    cells = frozenset((ar + r, ac + c) for r, c in rel)
                    if not all(cell in observed for cell in cells):
                        continue
                    if pid in NORMAL_COLOUR:
                        sig, colour = (NORMAL_COLOUR[pid], None), None
                    elif pid in EXTENSION_KIND:
                        sig, colour = (None, EXTENSION_KIND[pid]), None
                    else:  # mystery : couleur devinée = couleur observée
                        colours = {observed[c][0] for c in cells}
                        if len(colours) != 1 or None in colours:
                            continue
                        colour = next(iter(colours))
                        sig = (colour, None)
                    if all(observed[c] == sig for c in cells):
                        plist.append((cells, orient_index, (ar, ac), colour))
        placements[pid] = plist

    # 3. Pavage exact (première solution).
    remaining = {item["piece"]: item["quantity"] for item in client.inventory}
    all_cells = set(observed)
    chosen = []

    def backtrack(covered) -> bool:
        if len(covered) == len(all_cells):
            return True
        target = next(cell for cell in all_cells if cell not in covered)
        for pid, plist in placements.items():
            if remaining[pid] <= 0:
                continue
            for cells, orient_index, anchor, colour in plist:
                if target not in cells or cells & covered:
                    continue
                remaining[pid] -= 1
                chosen.append((pid, anchor, orient_index, colour))
                if backtrack(covered | cells):
                    return True
                chosen.pop()
                remaining[pid] += 1
        return False

    if not backtrack(frozenset()):
        client.give_up()
        return

    # 4. Poser puis proposer.
    for pid, (ar, ac), orient_index, colour in chosen:
        client.place(pid, ar, ac, orient_index, colour)
    client.submit()


if __name__ == "__main__":
    run(solve)
