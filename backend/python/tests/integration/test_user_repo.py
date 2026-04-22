import uuid

import pytest

pytestmark = pytest.mark.integration

from core.exceptions import ResourceExistsError, ResourceNotFoundError
from models import domain
from repositories import user_repo


@pytest.mark.asyncio
async def test_create_and_get_user_base_case(db_session):
    user_id = str(uuid.uuid4())
    display_name = "test_user"

    await user_repo.create_user(user_id, display_name, db_session)
    user: domain.User = await user_repo.get_user(user_id, db_session)

    assert user.userId == user_id
    assert user.displayName == display_name


@pytest.mark.asyncio
async def test_create_user_that_exists_throws_error(db_session):
    user_id = str(uuid.uuid4())
    display_name = "test_user"

    await user_repo.create_user(user_id, display_name, db_session)

    with pytest.raises(ResourceExistsError):
        await user_repo.create_user(user_id, display_name, db_session)


@pytest.mark.asyncio
async def test_get_user_not_found(db_session):
    user_id = str(uuid.uuid4())

    with pytest.raises(ResourceNotFoundError):
        await user_repo.get_user(user_id, db_session)


@pytest.mark.asyncio
async def test_update_user_display_name(db_session):
    user_id = str(uuid.uuid4())
    original_name = "original_name"
    updated_name = "updated_name"

    await user_repo.create_user(user_id, original_name, db_session)
    updated_user = await user_repo.update_user_display_name(
        user_id, updated_name, db_session
    )

    assert updated_user.displayName == updated_name
    assert updated_user.userId == user_id


@pytest.mark.asyncio
async def test_update_user_display_name_not_found(db_session):
    user_id = str(uuid.uuid4())

    with pytest.raises(ResourceNotFoundError):
        await user_repo.update_user_display_name(user_id, "new_name", db_session)
