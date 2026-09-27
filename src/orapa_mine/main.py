"""Point d'entrée : lance l'application graphique."""

from __future__ import annotations

from orapa_mine.ui.app import OrapaMineApp


def main() -> None:
    app = OrapaMineApp()
    app.run()


if __name__ == "__main__":
    main()
