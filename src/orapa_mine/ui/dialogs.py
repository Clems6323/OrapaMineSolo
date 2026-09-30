"""Boîtes de dialogue fichier (sauvegarde / chargement) et I/O JSON.

Utilise tkinter (bibliothèque standard) pour un vrai sélecteur de fichier.
Si tkinter est indisponible, retombe sur un chemin par défaut dans le dossier
courant afin de ne jamais bloquer le jeu.
"""

from __future__ import annotations

import json

_FILETYPES = [("Sauvegarde Orapa Mine", "*.json"), ("Tous les fichiers", "*.*")]
_DEFAULT_PATH = "orapa_mine_save.json"


def _dialog(save: bool) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if save:
            path = filedialog.asksaveasfilename(
                title="Sauvegarder la partie",
                defaultextension=".json",
                filetypes=_FILETYPES,
                initialfile=_DEFAULT_PATH,
            )
        else:
            path = filedialog.askopenfilename(
                title="Charger une partie", filetypes=_FILETYPES
            )
        root.destroy()
        return path or None
    except Exception:
        # tkinter absent : chemin par défaut (sauvegarde) ou introuvable (chargement).
        return _DEFAULT_PATH if save else None


def ask_save_path() -> str | None:
    return _dialog(save=True)


def ask_open_path() -> str | None:
    return _dialog(save=False)


def write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
