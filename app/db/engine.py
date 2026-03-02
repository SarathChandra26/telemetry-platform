from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config import settings


def build_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={"server_settings": {"jit": "off"}},
    )


primary_engine: AsyncEngine = build_engine(
    str(settings.database_url), echo=settings.db_echo
)

replica_engine: AsyncEngine = build_engine(
    str(settings.database_replica_url or settings.database_url),
    echo=settings.db_echo,
)

AsyncSessionLocal = async_sessionmaker(
    bind=primary_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

AsyncSessionReplica = async_sessionmaker(
    bind=replica_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
