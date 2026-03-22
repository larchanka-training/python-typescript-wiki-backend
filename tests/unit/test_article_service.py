"""Unit tests for ArticleService."""

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
        article_id = uuid4()

        self.mock_space_repo.get_membership_role.return_value = "owner"
        self.mock_article_repo.create_article_with_version.return_value = article_id

        async def run_test():
            result = await self.article_service.create_article(space_id, title, content, user_id)
            assert result == article_id
            self.mock_space_repo.get_membership_role.assert_called_once_with(space_id, user_id)
            self.mock_article_repo.create_article_with_version.assert_called_once_with(
                space_id, title, content, user_id,
                show_toc=False, parent_id=None, position=0,
            )

        asyncio.run(run_test())

    def test_create_article_not_owner(self):
        space_id = uuid4()
        user_id = 1
        title = "Test Article"
        content = "# Test Content"

        self.mock_space_repo.get_membership_role.return_value = "member"

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

        self.mock_space_repo.get_membership_role.return_value = "owner"

        async def run_test():
            try:
                await self.article_service.create_article(space_id, title, content, user_id)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "Title cannot be empty"

        asyncio.run(run_test())

    def test_delete_article_success(self):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = "owner"
        self.mock_article_repo.mark_deleted.return_value = None

        async def run_test():
            await self.article_service.delete_article(space_id, article_id, user_id, None)
            self.mock_article_repo.mark_deleted.assert_called_once()

        asyncio.run(run_test())

    def test_delete_article_not_found(self):
        article_id = uuid4()
        space_id = uuid4()
        user_id = 1

        self.mock_article_repo.get_article_by_id.return_value = None

        async def run_test():
            try:
                await self.article_service.delete_article(space_id, article_id, user_id, None)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "Article not found"

        asyncio.run(run_test())

    def test_delete_article_not_allowed(self):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = "member"

        async def run_test():
            try:
                await self.article_service.delete_article(space_id, article_id, user_id, None)
                assert False, "Expected PermissionError"
            except PermissionError as e:
                assert str(e) == "Only space owner or admin can perform this action"

        asyncio.run(run_test())

    def test_get_article_versions_success(self):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()
        versions = [{"id": uuid4(), "article_id": article_id, "version_number": 1}]

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = "member"
        self.mock_article_version_repo.get_versions_by_article.return_value = versions

        async def run_test():
            result = await self.article_service.get_article_versions(space_id, article_id, user_id, None)
            assert result == versions
            self.mock_article_repo.get_article_by_id.assert_called_once_with(article_id)
            self.mock_article_version_repo.get_versions_by_article.assert_called_once_with(article_id)

        asyncio.run(run_test())

    def test_get_article_versions_not_found(self):
        article_id = uuid4()
        space_id = uuid4()
        user_id = 1

        self.mock_article_repo.get_article_by_id.return_value = None

        async def run_test():
            try:
                await self.article_service.get_article_versions(space_id, article_id, user_id, None)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "Article not found"

        asyncio.run(run_test())

    def test_get_article_versions_no_access(self):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = None

        async def run_test():
            try:
                await self.article_service.get_article_versions(space_id, article_id, user_id, None)
                assert False, "Expected PermissionError"
            except PermissionError as e:
                assert str(e) == "Access denied"

        asyncio.run(run_test())

    def test_get_latest_article_version_success(self):
        article_id = uuid4()
        space_id = uuid4()
        user_id = 1
        version = {"id": uuid4(), "article_id": article_id, "version_number": 1}

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = "member"
        self.mock_article_version_repo.get_latest_version_by_article.return_value = version

        async def run_test():
            result = await self.article_service.get_latest_article_version(space_id, article_id, user_id, None)
            assert result == version
            self.mock_article_repo.get_article_by_id.assert_called_once_with(article_id)
            self.mock_article_version_repo.get_latest_version_by_article.assert_called_once_with(article_id)

        asyncio.run(run_test())

    def test_get_latest_article_version_not_found(self):
        article_id = uuid4()
        space_id = uuid4()
        user_id = 1

        self.mock_article_repo.get_article_by_id.return_value = None

        async def run_test():
            try:
                await self.article_service.get_latest_article_version(space_id, article_id, user_id, None)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "Article not found"

        asyncio.run(run_test())

    def test_get_latest_article_version_no_access(self):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = None

        async def run_test():
            try:
                await self.article_service.get_latest_article_version(space_id, article_id, user_id, None)
                assert False, "Expected PermissionError"
            except PermissionError as e:
                assert str(e) == "Access denied"

        asyncio.run(run_test())

    def test_get_latest_article_version_no_versions(self):
        article_id = uuid4()
        user_id = 1
        space_id = uuid4()

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = "member"
        self.mock_article_version_repo.get_latest_version_by_article.return_value = None

        async def run_test():
            try:
                await self.article_service.get_latest_article_version(space_id, article_id, user_id, None)
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "No versions found for article"

        asyncio.run(run_test())

    def test_get_article_version_by_number_success(self):
        article_id = uuid4()
        space_id = uuid4()
        user_id = 1
        version = {"id": uuid4(), "article_id": article_id, "version_number": 2}

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = "member"
        self.mock_article_version_repo.get_version_by_number.return_value = version

        async def run_test():
            result = await self.article_service.get_article_version_by_number(
                space_id, article_id, 2, user_id, None
            )
            assert result == version
            self.mock_article_version_repo.get_version_by_number.assert_called_once_with(article_id, 2)

        asyncio.run(run_test())

    def test_get_article_version_by_number_not_found(self):
        article_id = uuid4()
        space_id = uuid4()
        user_id = 1

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = "member"
        self.mock_article_version_repo.get_version_by_number.return_value = None

        async def run_test():
            try:
                await self.article_service.get_article_version_by_number(
                    space_id, article_id, 99, user_id, None
                )
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "Version not found"

        asyncio.run(run_test())

    def test_list_articles_success(self):
        space_id = uuid4()
        user_id = 1
        articles = [{"id": uuid4(), "title": "Art 1"}, {"id": uuid4(), "title": "Art 2"}]

        self.mock_space_repo.get_membership_role.return_value = "member"
        self.mock_article_repo.get_articles_by_space.return_value = articles

        async def run_test():
            result = await self.article_service.list_articles(space_id, user_id, None)
            assert result == articles
            self.mock_article_repo.get_articles_by_space.assert_called_once_with(space_id, None, False)

        asyncio.run(run_test())

    def test_list_articles_no_access(self):
        space_id = uuid4()
        user_id = 1

        self.mock_space_repo.get_membership_role.return_value = None

        async def run_test():
            try:
                await self.article_service.list_articles(space_id, user_id, None)
                assert False, "Expected PermissionError"
            except PermissionError:
                pass

        asyncio.run(run_test())

    def test_list_articles_with_filters(self):
        space_id = uuid4()
        user_id = 1
        parent_id = uuid4()
        articles = [{"id": uuid4(), "title": "Child Art"}]

        self.mock_space_repo.get_membership_role.return_value = "member"
        self.mock_article_repo.get_articles_by_space.return_value = articles

        async def run_test():
            result = await self.article_service.list_articles(
                space_id, user_id, None, parent_id=parent_id, filter_by_parent=True
            )
            assert result == articles
            self.mock_article_repo.get_articles_by_space.assert_called_once_with(
                space_id, parent_id, True
            )

        asyncio.run(run_test())

    def test_get_article_path_success(self):
        space_id = uuid4()
        article_id = uuid4()
        user_id = 1
        path = [{"id": article_id, "title": "Art", "parent_id": None}]

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = "member"
        self.mock_article_repo.get_article_ancestors.return_value = path

        async def run_test():
            result = await self.article_service.get_article_path(
                space_id, article_id, user_id, None
            )
            assert result == path
            self.mock_article_repo.get_article_ancestors.assert_called_once_with(article_id)

        asyncio.run(run_test())

    def test_save_article_version_success(self):
        article_id = uuid4()
        space_id = uuid4()
        user_id = 1
        new_version_id = uuid4()

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = "owner"
        self.mock_article_repo.save_new_version.return_value = new_version_id

        async def run_test():
            result = await self.article_service.save_article_version(
                space_id, article_id, "Updated", "# Content", user_id, None,
            )
            assert result == new_version_id
            self.mock_article_repo.save_new_version.assert_called_once()

        asyncio.run(run_test())

    def test_save_article_version_not_allowed(self):
        article_id = uuid4()
        space_id = uuid4()
        user_id = 1

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": space_id, "is_locked": False}
        self.mock_space_repo.get_membership_role.return_value = "member"

        async def run_test():
            try:
                await self.article_service.save_article_version(
                    space_id, article_id, "Title", "Content", user_id, None,
                )
                assert False, "Expected PermissionError"
            except PermissionError:
                pass

        asyncio.run(run_test())

    def test_save_article_version_wrong_space(self):
        article_id = uuid4()
        space_id = uuid4()
        wrong_space_id = uuid4()
        user_id = 1

        self.mock_article_repo.get_article_by_id.return_value = {"space_id": wrong_space_id}

        async def run_test():
            try:
                await self.article_service.save_article_version(
                    space_id, article_id, "Title", "Content", user_id, None,
                )
                assert False, "Expected ValueError"
            except ValueError as e:
                assert str(e) == "Article not found in this space"

        asyncio.run(run_test())