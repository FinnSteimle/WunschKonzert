import pytest
from httpx import ASGITransport, AsyncClient
from fast_api import app


# Test that .allowMethods actually rejects other methods
async def test_delete_request_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:5173"
    ) as client:
        response = await client.delete("/hello")

        assert response.status_code == 405
        assert response.json() == {"detail": "Method Not Allowed"}
