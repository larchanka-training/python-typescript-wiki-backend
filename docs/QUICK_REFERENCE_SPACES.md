# Quick Reference: Spaces Endpoints with Test Tokens

## TL;DR

### Setup (.env)
```bash
ENVIRONMENT=development
TEST_TOKEN=32u5g34u45gi243u4g23iu
```

### Test Request Example
```bash
curl -X GET http://localhost:8000/spaces \
  -H "x-test-token: 32u5g34u45gi243u4g23iu"
```

### Endpoint Implementation Pattern
```python
from typing import Annotated
from fastapi import APIRouter, Depends, Header, Request, status
from app.api.auth_utils import get_current_user, get_current_superuser
from app.services.models import UserProfile

router = APIRouter(prefix="/spaces", tags=["spaces"])

# GET /spaces - List all spaces
@router.get("", status_code=status.HTTP_200_OK)
async def get_spaces(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> dict:
    """List all spaces for authenticated user."""
    # Use current_user.id to fetch spaces from DB
    return {"spaces": []}

# GET /spaces/{space_id} - Get single space
@router.get("/{space_id}", status_code=status.HTTP_200_OK)
async def get_space(
    space_id: str,
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> dict:
    """Get a space by ID."""
    return {}

# POST /spaces - Create space
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_space(
    payload: dict,
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> dict:
    """Create a new space."""
    # Use current_user.id as owner
    return {}

# DELETE /spaces/{space_id} - Soft delete space
@router.delete("/{space_id}", status_code=status.HTTP_200_OK)
async def delete_space(
    space_id: str,
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> dict:
    """Soft delete a space."""
    # Check ownership before deleting
    return {}

# POST /spaces/{space_id}/restore - Restore deleted space (superuser only)
@router.post("/{space_id}/restore", status_code=status.HTTP_200_OK)
async def restore_space(
    space_id: str,
    current_user: Annotated[UserProfile, Depends(get_current_superuser)],
) -> dict:
    """Restore a deleted space (superuser only)."""
    # Superuser permission is already checked by dependency
    return {}
```

## Test User Credentials
| Property | Value |
|----------|-------|
| Test Token Header | `x-test-token` |
| Test Token Value | `32u5g34u45gi243u4g23iu` |
| User ID | 9999999 |
| Username | `test_user` |
| Telegram ID | 9999999 |
| Permission | `None` (regular user) |
| First Name | `Test` |
| Last Name | `User` |

## Superuser Test
```python
# For testing superuser-only endpoints, create a user with admin permission:
now = datetime.now(timezone.utc)
superuser = UserProfile(
    id=9999999,
    telegram_id=9999999,
    username="test_superuser",
    first_name="Test",
    last_name="Admin",
    photo_url=None,
    permission="admin",  # This makes them a superuser
    created_at=now,
    last_login_at=now,
)
```

## HTTP Status Codes by Scenario

| Scenario | Status | Error Code |
|----------|--------|-----------|
| Success | 200/201 | - |
| Invalid JSON body | 400 | `VALIDATION_ERROR` |
| Invalid token | 401 | `OAUTH_CODE_INVALID` |
| Missing auth header | 401 | `SESSION_MISSING` |
| Insufficient permissions | 403 | `PERMISSION_DENIED` |
| Not found | 404 | - |
| Rate limit | 429 | `RATE_LIMIT_EXCEEDED` |
| Server error | 500 | `INTERNAL_ERROR` |

## Response Format
All errors follow this format:
```json
{
  "status": "error",
  "message": "ERROR_CODE",
  "timestamp": "2025-01-18T12:00:00Z"
}
```

## Files Modified/Created

| File | Purpose |
|------|---------|
| `app/core/config.py` | Added `environment` and `test_token` settings |
| `app/services/token_service.py` | Added `verify_test_token()` method |
| `app/services/auth_service.py` | Added `verify_test_token()` method |
| `app/api/deps.py` | Updated `get_token_service()` |
| `app/api/auth_utils.py` | **NEW** - Auth helper functions |
| `app/core/errors.py` | Added `PERMISSION_DENIED` error code |
| `tests/integration/test_spaces_endpoints.py` | **NEW** - Complete test template |
| `docs/spaces-endpoints-implementation-guide.md` | **NEW** - Full implementation guide |

## Key Features

✅ Dev-only test tokens (production-safe)
✅ No database writes for test users
✅ Support for both test and production auth
✅ Automatic permission checks for superuser endpoints
✅ Consistent error handling
✅ Ready-to-use test fixtures and mocks

## Running Tests

```bash
# All spaces tests
pytest tests/integration/test_spaces_endpoints.py -v

# Specific test class
pytest tests/integration/test_spaces_endpoints.py::TestGetSpaces -v

# Specific test
pytest tests/integration/test_spaces_endpoints.py::TestGetSpaces::test_get_spaces_success_returns_200 -v
```
