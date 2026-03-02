from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Generic async repository base."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
