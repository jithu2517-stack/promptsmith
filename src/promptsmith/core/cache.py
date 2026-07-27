from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

from promptsmith.models.types import RunResult


CACHE_DB_FILENAME = "cache.db"


class Cache:
    """SQLite-backed response cache to save API costs during development."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".promptsmith_cache" / CACHE_DB_FILENAME
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    cache_key TEXT PRIMARY KEY,
                    prompt_hash TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    tokens_input INTEGER NOT NULL,
                    tokens_output INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    cost_usd REAL NOT NULL,
                    created_at REAL NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    last_accessed REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_hash
                ON cache(prompt_hash, provider, model)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_access
                ON cache(last_accessed)
            """)
            conn.commit()

    @staticmethod
    def _compute_cache_key(
        messages_json: str, provider: str, model: str
    ) -> str:
        raw = f"{provider}:{model}:{messages_json}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(
        self, prompt_hash: str, provider: str, model: str, messages_json: str
    ) -> RunResult | None:
        cache_key = self._compute_cache_key(messages_json, provider, model)
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT * FROM cache WHERE cache_key = ? AND prompt_hash = ?",
                (cache_key, prompt_hash),
            ).fetchone()

            if row:
                conn.execute(
                    "UPDATE cache SET access_count = access_count + 1, last_accessed = ? WHERE cache_key = ?",
                    (time.time(), cache_key),
                )
                conn.commit()
                return self._row_to_result(row)

        return None

    def set(self, result: RunResult, messages_json: str) -> None:
        cache_key = self._compute_cache_key(
            messages_json, result.provider.value, result.model
        )
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache
                   (cache_key, prompt_hash, provider, model, response_text,
                    tokens_input, tokens_output, latency_ms, cost_usd,
                    created_at, last_accessed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cache_key,
                    result.prompt_hash,
                    result.provider.value,
                    result.model,
                    result.response_text,
                    result.tokens_input,
                    result.tokens_output,
                    result.latency_ms,
                    result.cost_usd,
                    result.timestamp,
                    time.time(),
                ),
            )
            conn.commit()

    def invalidate(self, prompt_hash: str | None = None) -> int:
        with sqlite3.connect(str(self.db_path)) as conn:
            if prompt_hash:
                cursor = conn.execute(
                    "DELETE FROM cache WHERE prompt_hash = ?", (prompt_hash,)
                )
            else:
                cursor = conn.execute("DELETE FROM cache")
            conn.commit()
            return cursor.rowcount

    def stats(self) -> dict[str, object]:
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            total_saved = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM cache"
            ).fetchone()[0]
            total_access = conn.execute(
                "SELECT COALESCE(SUM(access_count), 0) FROM cache"
            ).fetchone()[0]
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

            return {
                "total_entries": total,
                "cost_saved_usd": round(total_saved, 6),
                "total_accesses": total_access,
                "db_size_bytes": db_size,
                "db_path": str(self.db_path),
            }

    def _row_to_result(self, row: tuple) -> RunResult:
        return RunResult(
            prompt_name="",
            prompt_version=0,
            prompt_hash=row[1],
            provider=row[2],
            model=row[3],
            messages_sent=[],
            response_text=row[4],
            tokens_input=row[5],
            tokens_output=row[6],
            latency_ms=row[7],
            cost_usd=row[8],
            cached=True,
            timestamp=row[9],
        )

    def prune(self, max_age_days: int = 30) -> int:
        cutoff = time.time() - (max_age_days * 86400)
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE last_accessed < ?", (cutoff,)
            )
            conn.commit()
            return cursor.rowcount
