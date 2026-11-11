"""Stockage SQLite du serveur officiel (issue #95).

Comptes d'équipe (pseudo + mot de passe haché), soumissions (ref git, statut) et
résultats (totaux + artefact JSON). Le classement retient la **meilleure**
soumission par équipe, triée distance -> points -> temps CPU. Logique pure
(stdlib seule), testable en base mémoire.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import time
from dataclasses import dataclass

_ITERATIONS = 200_000


class TeamExists(Exception):
    """Un compte d'équipe porte déjà ce pseudo."""


@dataclass(frozen=True)
class Submission:
    id: int
    team: str
    repo_url: str
    ref: str
    sha: str | None
    status: str          # "queued" | "done" | "failed"
    detail: str | None   # raison d'échec, le cas échéant
    created_at: float


@dataclass(frozen=True)
class LeaderRow:
    team: str
    distance: float
    points: int
    cpu_time_ms: int
    solved: int
    grids: int
    submission_id: int


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return salt.hex(), digest.hex()


def _verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), _ITERATIONS)
    return hmac.compare_digest(digest.hex(), hash_hex)


class Store:
    """Accès au stockage. Un seul objet partagé (connexion unique)."""

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS teams (
                pseudo TEXT PRIMARY KEY,
                salt TEXT NOT NULL,
                pw_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team TEXT NOT NULL,
                repo_url TEXT NOT NULL,
                ref TEXT NOT NULL,
                sha TEXT,
                status TEXT NOT NULL,
                detail TEXT,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS results (
                submission_id INTEGER PRIMARY KEY,
                team TEXT NOT NULL,
                distance REAL NOT NULL,
                points INTEGER NOT NULL,
                cpu_time_ms INTEGER NOT NULL,
                solved INTEGER NOT NULL,
                grids INTEGER NOT NULL,
                artifact TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        self._conn.commit()

    # --- Comptes -----------------------------------------------------------

    def register_team(self, pseudo: str, password: str) -> None:
        """Crée une équipe. Lève `TeamExists` si le pseudo est pris."""
        if not pseudo or not password:
            raise ValueError("pseudo et mot de passe requis")
        salt, pw_hash = _hash_password(password)
        try:
            self._conn.execute(
                "INSERT INTO teams(pseudo, salt, pw_hash, created_at) VALUES (?,?,?,?)",
                (pseudo, salt, pw_hash, time.time()),
            )
        except sqlite3.IntegrityError as exc:
            raise TeamExists(pseudo) from exc
        self._conn.commit()

    def authenticate(self, pseudo: str, password: str) -> bool:
        row = self._conn.execute(
            "SELECT salt, pw_hash FROM teams WHERE pseudo=?", (pseudo,)
        ).fetchone()
        return bool(row) and _verify_password(password, row["salt"], row["pw_hash"])

    def team_exists(self, pseudo: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM teams WHERE pseudo=?", (pseudo,)
        ).fetchone() is not None

    # --- Soumissions -------------------------------------------------------

    def add_submission(self, team: str, repo_url: str, ref: str) -> int:
        """Enregistre une soumission en file (`queued`) et renvoie son id."""
        cur = self._conn.execute(
            "INSERT INTO submissions(team, repo_url, ref, sha, status, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (team, repo_url, ref, None, "queued", None, time.time()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def _submission(self, row) -> Submission:
        return Submission(
            id=row["id"], team=row["team"], repo_url=row["repo_url"], ref=row["ref"],
            sha=row["sha"], status=row["status"], detail=row["detail"],
            created_at=row["created_at"],
        )

    def submission(self, sub_id: int) -> Submission | None:
        row = self._conn.execute("SELECT * FROM submissions WHERE id=?", (sub_id,)).fetchone()
        return self._submission(row) if row else None

    def pending_submissions(self) -> list[Submission]:
        rows = self._conn.execute(
            "SELECT * FROM submissions WHERE status='queued' ORDER BY id"
        ).fetchall()
        return [self._submission(r) for r in rows]

    def team_submissions(self, team: str) -> list[Submission]:
        rows = self._conn.execute(
            "SELECT * FROM submissions WHERE team=? ORDER BY id DESC", (team,)
        ).fetchall()
        return [self._submission(r) for r in rows]

    def record_result(self, sub_id: int, sha: str, artifact: dict) -> None:
        """Marque une soumission `done` et stocke ses totaux + l'artefact JSON."""
        total = artifact["total"]
        team = self._conn.execute(
            "SELECT team FROM submissions WHERE id=?", (sub_id,)
        ).fetchone()["team"]
        self._conn.execute(
            "UPDATE submissions SET status='done', sha=?, detail=NULL WHERE id=?",
            (sha, sub_id),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO results(submission_id, team, distance, points, "
            "cpu_time_ms, solved, grids, artifact, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (sub_id, team, float(total["distance"]), int(total["points"]),
             int(total["cpu_time_ms"]), int(total["solved"]), int(total["grids"]),
             json.dumps(artifact), time.time()),
        )
        self._conn.commit()

    def record_failure(self, sub_id: int, reason: str) -> None:
        self._conn.execute(
            "UPDATE submissions SET status='failed', detail=? WHERE id=?", (reason, sub_id)
        )
        self._conn.commit()

    # --- Résultats & classement -------------------------------------------

    def team_best(self, team: str) -> dict | None:
        """Meilleur artefact de l'équipe (plus petite clé distance/points/cpu)."""
        rows = self._conn.execute(
            "SELECT artifact FROM results WHERE team=? "
            "ORDER BY distance ASC, points ASC, cpu_time_ms ASC LIMIT 1", (team,)
        ).fetchone()
        return json.loads(rows["artifact"]) if rows else None

    def leaderboard(self) -> list[LeaderRow]:
        """Une ligne par équipe (sa meilleure soumission), triée."""
        rows = self._conn.execute(
            "SELECT team, distance, points, cpu_time_ms, solved, grids, submission_id "
            "FROM results ORDER BY distance ASC, points ASC, cpu_time_ms ASC"
        ).fetchall()
        best: dict[str, LeaderRow] = {}
        for r in rows:
            if r["team"] not in best:  # déjà trié : la première vue est la meilleure
                best[r["team"]] = LeaderRow(
                    team=r["team"], distance=r["distance"], points=r["points"],
                    cpu_time_ms=r["cpu_time_ms"], solved=r["solved"], grids=r["grids"],
                    submission_id=r["submission_id"],
                )
        return sorted(
            best.values(), key=lambda x: (x.distance, x.points, x.cpu_time_ms)
        )
