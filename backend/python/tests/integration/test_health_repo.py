import pytest

from repositories import health_repo

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_check_db_health_success(db_session):
    """Test database health check returns ok status"""
    result = await health_repo.check_db_health()
    assert result["status"] == "ok"
    assert "detail" not in result
