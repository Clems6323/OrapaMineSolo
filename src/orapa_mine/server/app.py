"""Interface Streamlit du serveur officiel (issue #95).

UI mince : inscription / connexion d'équipe, soumission par **ref git**,
classement public, et page d'équipe **minimale** (résultat global + par grille,
raison de DNF) — **jamais** de transcript ni de contenu de grille (anti-triche).

Lancement : `streamlit run -m orapa_mine.server.app` (ou via le Dockerfile).
Dépend de `streamlit` (hors cœur du projet) ; configuré par les variables
d'environnement `ORAPA_DB` (chemin SQLite). Le *worker* évalue la file à part.
"""

from __future__ import annotations

import os

import streamlit as st

from orapa_mine.server.storage import Store, TeamExists


@st.cache_resource
def _store() -> Store:
    return Store(os.environ.get("ORAPA_DB", "orapa.sqlite3"))


def _auth_sidebar(store: Store) -> str | None:
    """Barre latérale : inscription / connexion. Renvoie l'équipe connectée."""
    team = st.session_state.get("team")
    with st.sidebar:
        st.header("Équipe")
        if team:
            st.success(f"Connecté : **{team}**")
            if st.button("Se déconnecter"):
                st.session_state.pop("team", None)
                st.rerun()
            return team

        tab_in, tab_up = st.tabs(["Connexion", "Inscription"])
        with tab_in:
            pseudo = st.text_input("Pseudo", key="in_pseudo")
            pw = st.text_input("Mot de passe", type="password", key="in_pw")
            if st.button("Se connecter"):
                if store.authenticate(pseudo, pw):
                    st.session_state["team"] = pseudo
                    st.rerun()
                else:
                    st.error("Identifiants invalides.")
        with tab_up:
            pseudo = st.text_input("Pseudo", key="up_pseudo")
            pw = st.text_input("Mot de passe", type="password", key="up_pw")
            if st.button("Créer l'équipe"):
                try:
                    store.register_team(pseudo, pw)
                    st.session_state["team"] = pseudo
                    st.rerun()
                except TeamExists:
                    st.error("Ce pseudo est déjà pris.")
                except ValueError as exc:
                    st.error(str(exc))
    return None


def _leaderboard(store: Store) -> None:
    st.header("Classement")
    st.caption("Tri : distance à la vérité → points → temps CPU (plus bas = mieux).")
    board = store.leaderboard()
    if not board:
        st.info("Aucune soumission évaluée pour l'instant.")
        return
    st.table([
        {"#": i + 1, "Équipe": r.team, "Distance": round(r.distance, 3),
         "Points": r.points, "CPU (ms)": r.cpu_time_ms, "Résolues": f"{r.solved}/{r.grids}"}
        for i, r in enumerate(board)
    ])


def _submit(store: Store, team: str) -> None:
    st.header("Soumettre")
    st.caption("Dépôt GitLab + ref (branche, tag ou commit). La plateforme résout "
               "le commit, construit le Dockerfile, puis évalue en bac à sable.")
    repo = st.text_input("URL du dépôt GitLab")
    ref = st.text_input("Ref (branche / tag / commit)", value="main")
    if st.button("Envoyer") and repo:
        sid = store.add_submission(team, repo, ref)
        st.success(f"Soumission #{sid} en file. Résultat visible après évaluation.")


def _team_page(store: Store, team: str) -> None:
    st.header("Mon équipe")
    for sub in store.team_submissions(team):
        label = f"#{sub.id} · {sub.ref} · {sub.status}"
        if sub.status == "failed" and sub.detail:
            label += f" ({sub.detail})"
        st.write(label)

    best = store.team_best(team)
    if not best:
        st.info("Pas encore de résultat.")
        return
    total = best["total"]
    st.subheader("Meilleur résultat")
    st.write(f"Distance **{round(total['distance'], 3)}** · points **{total['points']}** · "
             f"CPU **{total['cpu_time_ms']} ms** · résolues **{total['solved']}/{total['grids']}**")
    st.subheader("Par grille")
    # Volontairement minimal : aucune reconstruction possible des grilles cachées.
    st.table([
        {"Grille": g["grid_id"], "Palier": g["tier"], "Résolue": g["solved"],
         "Distance": round(g["distance"], 3), "Points": g["points"],
         "CPU (ms)": g["cpu_time_ms"], "DNF": g["dnf_reason"] or ""}
        for g in best["grids"]
    ])


def main() -> None:  # pragma: no cover - interface Streamlit
    st.set_page_config(page_title="Orapa Mine — Hackathon", layout="wide")
    st.title("Orapa Mine — Hackathon")
    store = _store()
    team = _auth_sidebar(store)

    _leaderboard(store)
    if team:
        _submit(store, team)
        _team_page(store, team)
    else:
        st.info("Connecte-toi (barre latérale) pour soumettre et voir ta page d'équipe.")


if __name__ == "__main__":  # pragma: no cover - `streamlit run` fixe __name__ à __main__
    main()
