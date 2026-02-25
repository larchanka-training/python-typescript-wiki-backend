from uuid import uuid4

import pytest

from app.services.article_service import ArticleService


class TestArticleService:
    @pytest.fixture
    def article_service(self, mocker):
        mock_article_repo = mocker.AsyncMock()
        mock_article_version_repo = mocker.AsyncMock()
        mock_space_repo = mocker.AsyncMock()
        return ArticleService(mock_article_repo, mock_article_version_repo, mock_space_repo)

    @pytest.mark.asyncio
    async def test_create_article_success(self, article_service, mocker):
        space_id = uuid4()
        user_id = 1
        title = "Test Article"
        content = "# Test Content"

        article_service._space_repository.get_membership_role.return_value = "owner"
        article_service._article_repository.create_article.return_value = space_id
        article_service._article_version_repository.create_version.return_value = uuid4()

        result = await article_service.create_article(space_id, title, content, user_id)

        assert result == space_id
        article_service._space_repository.get_membership_role.assert_called_once_with(space_id, user_id)
        article_service._article_repository.create_article.assert_called_once_with(space_id, title, user_id)
        article_service._article_version_repository.create_version.assert_called_once_with(space_id, 1, title, content, user_id)

    @pytest.mark.asyncio
    async def test_create_article_not_owner(self, article_service):
        space_id = uuid4()
        user_id = 1
        title = "Test Article"
        content = "# Test Content"

        article_service._space_repository.get_membership_role.return_value = "member"

        with pytest.raises(PermissionError, match="Only space owner can create articles"):
            await article_service.create_article(space_id, title, content, user_id)

    @pytest.mark.asyncio
    async def test_create_article_empty_title(self, article_service):
        space_id = uuid4()
        user_id = 1
        title = ""
        content = "# Test Content"

        article_service._space_repository.get_membership_role.return_value = "owner"

        with pytest.raises(ValueError, match="Title cannot be empty"):
            await article_service.create_article(space_id, title, content, user_id)

    @pytest.mark.asyncio
    async def test_get_article_versions_success(self, article_service):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()
        versions = [{"id": uuid4(), "article_id": article_id, "version_number": 1}]

        article_service._article_repository.get_article_by_id.return_value = {"space_id": space_id}
        article_service._space_repository.get_membership_role.return_value = "member"
        article_service._article_version_repository.get_versions_by_article.return_value = versions

        result = await article_service.get_article_versions(article_id, user_id)

        assert result == versions
        article_service._article_repository.get_article_by_id.assert_called_once_with(article_id)
        article_service._space_repository.get_membership_role.assert_called_once_with(space_id, user_id)
        article_service._article_version_repository.get_versions_by_article.assert_called_once_with(article_id)

    @pytest.mark.asyncio
    async def test_get_article_versions_not_found(self, article_service):
        article_id = uuid4()
        user_id = 1

        article_service._article_repository.get_article_by_id.return_value = None

        with pytest.raises(ValueError, match="Article not found"):
            await article_service.get_article_versions(article_id, user_id)

    @pytest.mark.asyncio
    async def test_get_article_versions_no_access(self, article_service):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()

        article_service._article_repository.get_article_by_id.return_value = {"space_id": space_id}
        article_service._space_repository.get_membership_role.return_value = None

        with pytest.raises(PermissionError, match="Access denied"):
            await article_service.get_article_versions(article_id, user_id)

    @pytest.mark.asyncio
    async def test_get_article_version_success(self, article_service):
        version_id = uuid4()
        article_id = uuid4()
        space_id = uuid4()
        user_id = 1
        version = {"id": version_id, "article_id": article_id}

        article_service._article_version_repository.get_version_by_id.return_value = version
        article_service._article_repository.get_article_by_id.return_value = {"space_id": space_id}
        article_service._space_repository.get_membership_role.return_value = "member"

        result = await article_service.get_article_version(version_id, user_id)

        assert result == version
        article_service._article_version_repository.get_version_by_id.assert_called_once_with(version_id)
        article_service._article_repository.get_article_by_id.assert_called_once_with(article_id)
        article_service._space_repository.get_membership_role.assert_called_once_with(space_id, user_id)

    @pytest.mark.asyncio
    async def test_get_article_version_not_found(self, article_service):
        version_id = uuid4()
        user_id = 1

        article_service._article_version_repository.get_version_by_id.return_value = None

        with pytest.raises(ValueError, match="Version not found"):
            await article_service.get_article_version(version_id, user_id)