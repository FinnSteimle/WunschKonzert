import pytest
import uuid
from repositories import crud
from models.domain import User

@pytest.mark.asyncio
async def test_create_and_get_user(db_session):
    # Arrange
    user_id = str(uuid.uuid4())
    display_name = "Test User"

    # Act
    user = await crud.create_user(user_id, display_name)
    fetched_user = await crud.get_user(user_id)

    # Assert
    assert user.userId == user_id
    assert user.displayName == display_name
    assert fetched_user is not None
    assert fetched_user.userId == user_id
    assert fetched_user.displayName == display_name

@pytest.mark.asyncio
async def test_create_duplicate_user(db_session):
    # Arrange
    user_id = str(uuid.uuid4())
    display_name = "Test User"
    await crud.create_user(user_id, display_name)

    # Act & Assert
    with pytest.raises(ValueError, match="User already exists"):
        await crud.create_user(user_id, "Another Name")

@pytest.mark.asyncio
async def test_get_nonexistent_user(db_session):
    # Act
    user = await crud.get_user("non-existent-id")

    # Assert
    assert user is None

@pytest.mark.asyncio
async def test_update_user_display_name(db_session):
    # Arrange
    user_id = str(uuid.uuid4())
    await crud.create_user(user_id, "Old Name")

    # Act
    await crud.update_user_display_name(user_id, "New Name")
    user = await crud.get_user(user_id)

    # Assert
    assert user.displayName == "New Name"
