"""Parquet-backed analytical storage for high-volume, append-mostly data
(raw/processed FIRMS observations, engineered features, event analytics).

PostgreSQL holds operational/queryable state (events, facilities, alerts);
Parquet holds the bulk analytical layer so we never force large FIRMS pulls
or engineered feature tables into row-store OLTP tables.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import get_settings

settings = get_settings()
DATA_ROOT = settings.data_dir.parent.parent / "data"  # repo-level /data


def _path(subdir: str, name: str) -> Path:
    p = DATA_ROOT / subdir
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{name}.parquet"


def write_parquet(df: pd.DataFrame, subdir: str, name: str) -> Path:
    path = _path(subdir, name)
    df.to_parquet(path, index=False)
    return path


def append_parquet(df: pd.DataFrame, subdir: str, name: str) -> Path:
    path = _path(subdir, name)
    if path.exists():
        existing = pd.read_parquet(path)
        df = pd.concat([existing, df], ignore_index=True).drop_duplicates()
    df.to_parquet(path, index=False)
    return path


def read_parquet(subdir: str, name: str) -> pd.DataFrame:
    path = _path(subdir, name)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)
