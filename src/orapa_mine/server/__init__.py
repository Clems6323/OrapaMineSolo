"""Serveur officiel du hackathon (issue #95) : stockage, file d'évaluation,
classement, et interface Streamlit.

La logique (comptes, soumissions, scoring, classement) est pure et testable ;
seules l'UI (`app.py`, Streamlit) et la construction/exécution Docker (dans le
*worker* et le bac à sable) dépendent d'outils externes.
"""

from __future__ import annotations
