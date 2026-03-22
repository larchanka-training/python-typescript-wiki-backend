from datetime import datetime, timedelta, timezone

from app.services.space_service import SpaceService


def test_format_spaces_excludes_spaces_deleted_more_than_7_days_ago() -> None:
    now = datetime.now(timezone.utc)
    old_deleted = now - timedelta(days=8)
    recent_deleted = now - timedelta(days=2)

    spaces = [
        {"id": 2, "name": "B", "role": "member", "deleted_at": old_deleted},
        {"id": 3, "name": "C", "role": "owner", "deleted_at": None},
        {"id": 1, "name": "A", "role": "member", "deleted_at": recent_deleted},
        {"id": 4, "name": "D", "role": "owner", "deleted_at": recent_deleted},
    ]

    formatted = SpaceService.format_spaces(spaces)

    # Old deleted (id=2) should be excluded
    assert [s["id"] for s in formatted] == [3, 4, 1]

    # Owners come first and are sorted by id
    assert formatted[0]["role"] == "owner"
    assert formatted[1]["role"] == "owner"

    # `is_deleted` flag and `deleted_at` preservation
    assert formatted[0]["is_deleted"] is False
    assert formatted[0]["deleted_at"] is None
    assert formatted[1]["is_deleted"] is True
    assert formatted[1]["deleted_at"] == recent_deleted
    assert formatted[2]["is_deleted"] is True
    assert formatted[2]["deleted_at"] == recent_deleted


def test_format_spaces_fields_and_sorting_without_owners() -> None:
    spaces = [
        {"id": 5, "name": "E", "role": "member", "deleted_at": None},
        {"id": 3, "name": "C", "role": "member", "deleted_at": None},
    ]

    formatted = SpaceService.format_spaces(spaces)

    # Sorted by id for non-owners
    assert [s["id"] for s in formatted] == [3, 5]

    # All expected keys are present and not marked deleted
    for s in formatted:
        assert set(s.keys()) == {"id", "name", "role", "is_deleted", "deleted_at"}
        assert s["is_deleted"] is False
