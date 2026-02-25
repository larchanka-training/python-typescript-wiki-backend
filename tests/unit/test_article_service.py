import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock
from uuid import uuid4

from app.services.article_service import ArticleService


class TestArticleService(TestCase):
    def setUp(self):
        self.mock_article_repo = AsyncMock()
        self.mock_article_version_repo = AsyncMock()
        self.mock_space_repo = AsyncMock()
        self.article_service = ArticleService(
            self.mock_article_repo, self.mock_article_version_repo, self.mock_space_repo
        )

    def test_create_article_success(self):
        space_id = uuid4()
        user_id = 1
        title = "Test Article"
        content = "# Test Content"

        self.article_service._space_repository.get_membership_role.return_value = "owner"
        self.article_service._article_repository.create_article.return_value = space_id
        self.article_service._article_version_repository.create_version.return_value = uuid4()

        async def run_test():
            result = await self.article_service.create_article(space_id, title, content, user_id)
            assert result == space_id
            self.article_service._space_repository.get_membership_role.assert_called_once_with(space_id, user_id)
            self.article_service._article_repository.create_article.assert_called_once_with(space_id, title, user_id)
            self.article_service._article_version_repository.create_version.assert_called_once_with(space_id, 1, title, content, user_id)

        asyncio.run(run_test())

    def test_create_article_not_owner(self):
        space_id = uuid4()
        user_id = 1
        title = "Test Article"
        content = "# Test Content"

        self.article_service._space_repository.get_membership_role.return_value = "member"

        async def run_test():
            try:
                await self.article_service.create_article(space_id, title, content, user_id)
                assert False, "Expected PermissionError"
            except PermissionError as e:
                assert str(e) == "Only space owner can create articles"

        asyncio.run(run_test())

    def test_create_article_empty_title(self):
        space_id = uuid4()
        user_id = 1
        title = ""
        content = "# Test Content"

        self.article_service._space_repository.get_membership_role.return_value = "owner"

        async def run_test():
            try:
                await self.article_service.create_article(space_id, title, content, user_id)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "Title cannot be empty"

        asyncio.run(run_test())

    def test_get_article_versions_success(self):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()
        versions = [{"id": uuid4(), "article_id": article_id, "version_number": 1}]

        self.article_service._article_repository.get_article_by_id.return_value = {"space_id": space_id}
        self.article_service._space_repository.get_membership_role.return_value = "member"
        self.article_service._article_version_repository.get_versions_by_article.return_value = versions

        async def run_test():
            result = await self.article_service.get_article_versions(article_id, user_id)
            assert result == versions
            self.article_service._article_repository.get_article_by_id.assert_called_once_with(article_id)
            self.article_service._space_repository.get_membership_role.assert_called_once_with(space_id, user_id)
            self.article_service._article_version_repository.get_versions_by_article.assert_called_once_with(article_id)

        asyncio.run(run_test())

    def test_get_article_versions_not_found(self):
        article_id = uuid4()
        user_id = 1

        self.article_service._article_repository.get_article_by_id.return_value = None

        async def run_test():
            try:
                await self.article_service.get_article_versions(article_id, user_id)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "Article not found"

        asyncio.run(run_test())

    def test_get_article_versions_no_access(self):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()

        self.article_service._article_repository.get_article_by_id.return_value = {"space_id": space_id}
        self.article_service._space_repository.get_membership_role.return_value = None

        async def run_test():
            try:
                await self.article_service.get_article_versions(article_id, user_id)
                assert False, "Expected PermissionError"
            except PermissionError as e:
                assert str(e) == "Access denied"

        asyncio.run(run_test())

    def test_get_latest_article_version_success(self):
        article_id = uuid4()
        space_id = uuid4()
        user_id = 1
        version = {"id": uuid4(), "article_id": article_id, "version_number": 1}

        self.article_service._article_repository.get_article_by_id.return_value = {"space_id": space_id}
        self.article_service._space_repository.get_membership_role.return_value = "member"
        self.article_service._article_version_repository.get_latest_version_by_article.return_value = version

        async def run_test():
            result = await self.article_service.get_latest_article_version(article_id, user_id)
            assert result == version
            self.article_service._article_repository.get_article_by_id.assert_called_once_with(article_id)
            self.article_service._space_repository.get_membership_role.assert_called_once_with(space_id, user_id)
            self.article_service._article_version_repository.get_latest_version_by_article.assert_called_once_with(article_id)

        asyncio.run(run_test())

    def test_get_latest_article_version_not_found(self):
        article_id = uuid4()
        user_id = 1

        self.article_service._article_repository.get_article_by_id.return_value = None

        async def run_test():
            try:
                await self.article_service.get_latest_article_version(article_id, user_id)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "Article not found"

        asyncio.run(run_test())

    def test_get_latest_article_version_no_access(self):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()

        self.article_service._article_repository.get_article_by_id.return_value = {"space_id": space_id}
        self.article_service._space_repository.get_membership_role.return_value = None

        async def run_test():
            try:
                await self.article_service.get_latest_article_version(article_id, user_id)
                assert False, "Expected PermissionError"
            except PermissionError as e:
                assert str(e) == "Access denied"

        asyncio.run(run_test())

    def test_get_latest_article_version_no_versions(self):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()

        self.article_service._article_repository.get_article_by_id.return_value = {"space_id": space_id}
        self.article_service._space_repository.get_membership_role.return_value = "member"
        self.article_service._article_version_repository.get_latest_version_by_article.return_value = None

        async def run_test():
            try:
                await self.article_service.get_latest_article_version(article_id, user_id)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "No versions found for article"

        asyncio.run(run_test())

    def test_get_article_version_success(self):
        version_id = uuid4()
        article_id = uuid4()
        space_id = uuid4()
        user_id = 1
        version = {"id": version_id, "article_id": article_id}

        self.article_service._article_repository.get_article_by_id.return_value = {"space_id": space_id}
        self.article_service._space_repository.get_membership_role.return_value = "member"
        self.article_service._article_version_repository.get_version_by_id.return_value = version

        async def run_test():
            result = await self.article_service.get_article_version(article_id, version_id, user_id)
            assert result == version
            self.article_service._article_repository.get_article_by_id.assert_called_once_with(article_id)
            self.article_service._space_repository.get_membership_role.assert_called_once_with(space_id, user_id)
            self.article_service._article_version_repository.get_version_by_id.assert_called_once_with(version_id)

        asyncio.run(run_test())

    def test_get_article_version_not_found(self):
        article_id = uuid4()
        version_id = uuid4()
        user_id = 1
        space_id = uuid4()

        self.article_service._article_repository.get_article_by_id.return_value = {"space_id": space_id}
        self.article_service._space_repository.get_membership_role.return_value = "member"
        self.article_service._article_version_repository.get_version_by_id.return_value = None

        async def run_test():
            try:
                await self.article_service.get_article_version(article_id, version_id, user_id)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "Version not found"

        asyncio.run(run_test())

    def test_get_article_version_wrong_article(self):
        article_id = uuid4()
        wrong_article_id = uuid4()
        version_id = uuid4()
        user_id = 1
        space_id = uuid4()
        version = {"id": version_id, "article_id": wrong_article_id}

        self.article_service._article_repository.get_article_by_id.return_value = {"space_id": space_id}
        self.article_service._space_repository.get_membership_role.return_value = "member"
        self.article_service._article_version_repository.get_version_by_id.return_value = version

        async def run_test():
            try:
                await self.article_service.get_article_version(article_id, version_id, user_id)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "Version does not belong to the specified article"

        asyncio.run(run_test())