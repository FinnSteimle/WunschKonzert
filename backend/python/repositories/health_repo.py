from sqlalchemy import text

from core.database import get_session_factory


async def check_db_health() -> dict[str, object]:
    """Check if database is healthy by executing a simple query"""
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                return {"status": "ok"}
        return {"status": "error", "detail": "Query returned unexpected result"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
