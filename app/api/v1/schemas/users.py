from pydantic import BaseModel, ConfigDict


class UserSearchResult(BaseModel):
    """Описание одного пользователя в результатах поиска."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    telegram_id: int
    username: str | None
    photo_url: str | None


class UserSearchResponse(BaseModel):
    """Ответ эндпойнта поиска пользователей."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "users": [
                    {
                        "telegram_id": 123456,
                        "username": "user1",
                        "photo_url": "https://example.com/photo.png",
                    }
                ]
            }
        }
    )

    users: list[UserSearchResult]
