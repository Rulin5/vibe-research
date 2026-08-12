"""Database runtime configuration for the production user-data store."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


_ENV_PATH = Path(__file__).with_name(".env")
load_dotenv(_ENV_PATH, override=False)


class DatabaseConfigError(RuntimeError):
    pass


def database_url() -> str:
    value = (os.environ.get("VR_DATABASE_URL") or "").strip()
    if not value:
        raise DatabaseConfigError("缺少 VR_DATABASE_URL，用户数据服务未配置")
    if not value.startswith("postgresql+psycopg://"):
        raise DatabaseConfigError("VR_DATABASE_URL 必须使用 postgresql+psycopg 驱动")
    return value


@lru_cache(maxsize=1)
def engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True, pool_size=5, max_overflow=5)


@lru_cache(maxsize=1)
def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()
