"""SDK participant (client du protocole) — issue #94.

Gère la plomberie du protocole fil (#90) sur stdin/stdout : lit `hello`, expose
les commandes (`pieces/shoot/query/place/remove/submit/give_up`) comme de simples
appels, analyse les réponses, et boucle jusqu'à `end`.

**Autonome et sans dépendance** (stdlib seule) : ce fichier est vendu tel quel
dans le dépôt-modèle des participants (`templates/python/orapa_client.py`). Il
n'importe donc **rien** du reste du projet.
"""

from __future__ import annotations

import json
import sys


class ProtocolError(RuntimeError):
    """Message inattendu ou flux fermé par l'arbitre."""


class Client:
    """Client du protocole : un appel = une commande + sa réponse.

    À la création, lit le message `hello` et expose `width`, `height`,
    `inventory`, `extensions`, `max_proposals`, `limits`.
    """

    def __init__(self, inp=None, out=None) -> None:
        self._in = inp if inp is not None else sys.stdin
        self._out = out if out is not None else sys.stdout
        hello = self._read()
        if hello.get("type") != "hello":
            raise ProtocolError(f"attendu hello, reçu {hello.get('type')!r}")
        self.hello = hello
        self.protocol = hello.get("protocol")
        self.width = hello["width"]
        self.height = hello["height"]
        self.inventory = hello["inventory"]
        self.extensions = hello.get("extensions", [])
        self.max_proposals = hello["max_proposals"]
        self.limits = hello.get("limits", {})

    # --- E/S bas niveau ----------------------------------------------------

    def _read(self) -> dict:
        line = self._in.readline()
        if not line:
            raise EOFError("flux fermé par l'arbitre")
        return json.loads(line)

    def _command(self, obj: dict) -> dict:
        self._out.write(json.dumps(obj) + "\n")
        self._out.flush()
        return self._read()

    # --- Commandes ---------------------------------------------------------

    def pieces(self) -> dict:
        """Re-demande l'inventaire (identique à `hello`). La couleur mystère
        reste cachée."""
        return self._command({"type": "pieces"})

    def shoot(self, row: int, col: int, direction: str) -> dict:
        """Tire un rayon depuis la case de bordure (row, col) vers `direction`
        (`UP|DOWN|LEFT|RIGHT`). Renvoie `{exit, color, absorbed}`. Coût : 1."""
        return self._command(
            {"type": "shoot", "entry": {"row": row, "col": col}, "direction": direction}
        )

    def query(self, row: int, col: int) -> dict:
        """Interroge une case. Renvoie `{occupied, color, kind}`. Coût : 3."""
        return self._command({"type": "query", "cell": {"row": row, "col": col}})

    def place(self, piece: str, row: int, col: int, orient: int, color: str | None = None) -> dict:
        """Pose `piece` (id fil) ancrée en (row, col), orientation `orient`.
        `color` requis seulement pour `mystery`. Renvoie `ack`/`reject`."""
        msg = {"type": "place", "piece": piece, "anchor": {"row": row, "col": col}, "orient": orient}
        if color is not None:
            msg["color"] = color
        return self._command(msg)

    def remove(self, row: int, col: int) -> dict:
        """Retire la pièce occupant (row, col). Renvoie `ack`/`reject`."""
        return self._command({"type": "remove", "cell": {"row": row, "col": col}})

    def submit(self) -> dict:
        """Propose le plateau courant (complet requis). Renvoie `result`/`reject`."""
        return self._command({"type": "submit"})

    def give_up(self) -> dict:
        """Abandonne la grille. Renvoie `result`."""
        return self._command({"type": "give_up"})


def run(solve) -> None:
    """Crée un `Client`, appelle `solve(client)`, et termine proprement.

    `solve` reçoit le client et joue la grille. Les fermetures de flux en fin de
    partie (après `submit`/`give_up`) sont absorbées."""
    try:
        client = Client()
        solve(client)
    except (EOFError, BrokenPipeError):
        pass


if __name__ == "__main__":  # pragma: no cover - lanceur générique
    run(lambda c: c.give_up())
