# Spaces Endpoints Integration Tests - Implementation Guide

## Overview

This guide explains the test infrastructure for the spaces endpoints. The tests use a **test token header** (`x-test-token`) for authentication in **development mode only**, allowing you to test endpoints without needing actual OAuth tokens from Telegram.

## Environment Setup

### 1. Environment Variables

Add these to your `.env` file (development only):

```bash
ENVIRONMENT=development
TEST_TOKEN=32u5g34u45gi243u4g23iu
```

For production/staging, simply omit `ENVIRONMENT` or set it to `production`:
```bash
# Production - no test token support
ENVIRONMENT=production
```

## Architecture Changes

### Modified Files

#### 1. `app/core/config.py`
- Added `environment: str` field (default: "production")
- Added `test_token: str | None` field (default: None)
- Loads from `ENVIRONMENT` and `TEST_TOKEN` env variables

#### 2. `app/services/token_service.py`
- New parameter: `environment` and `test_token` in `__init__`
- New method: `verify_test_token(token: str, trace_id: str)` 
  - Only works when `environment == "development"`
  - Validates token matches `self._test_token`
  - Returns fixed `TokenPayload` for test user (telegram_id=9999999)

#### 3. `app/services/auth_service.py`
- New method: `verify_test_token(token: str, trace_id: str)`
  - Uses TokenService's `verify_test_token()`
  - Returns a **fake test user** (id=9999999) without DB upsert
  - User is NOT persisted in the database

#### 4. `app/api/deps.py`
- Updated `get_token_service()` to pass `environment` and `test_token` to TokenService

## How to Use in Endpoints

When implementing space endpoints, use the request header to determine authentication method:

```python
from fastapi import Depends, Header, Request
from app.api.deps import get_auth_service

@router.get("/spaces")
async def get_spaces(
    request: Request,
    x_test_token: str | None = Header(None),
    auth_service: Annotated[AuthService, Depends(get_auth_service)] = None,
) -> dict:
    trace_id = get_trace_id(request)
    
    # Try test token first (dev only)
    if x_test_token:
        user, _ = await auth_service.verify_test_token(x_test_token, trace_id)
    else:
        # Fall back to normal token verification
        token = extract_bearer_token(request)
        user, _ = await auth_service.verify_token(token, trace_id)
    
    # Use user.id to fetch/create spaces
    return {"spaces": [...]}
```

**Alternative simpler approach** - create a dependency that handles both:

```python
from typing import Annotated
from fastapi import Depends, Header, Request

async def get_current_user(
    request: Request,
    x_test_token: str | None = Header(None),
    auth_service: Annotated[AuthService, Depends(get_auth_service)] = None,
) -> UserProfile:
    """Resolve current user from either test token or bearer token."""
    trace_id = get_trace_id(request)
    
    if x_test_token:
        user, _ = await auth_service.verify_test_token(x_test_token, trace_id)
        return user
    
    token = extract_bearer_token(request)
    user, _ = await auth_service.verify_token(token, trace_id)
    return user
```

Then use it in endpoints:
```python
@router.get("/spaces")
async def get_spaces(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> dict:
    return {"spaces": [...]}
```

## Test Template Structure

The test file ([test_spaces_endpoints.py](test_spaces_endpoints.py)) provides:

### Test User
```python
TEST_TOKEN = "32u5g34u45gi243u4g23iu"
TEST_USER_ID = 9999999
```

### Fake Auth Service Classes

1. **`FakeAuthService`** - Returns fixed test user for both methods
2. **`FakeAuthServiceError`** - Raises predefined errors

### Test Classes by Endpoint

#### `TestGetSpaces` (GET /spaces)
- ✅ Success case (200)
- ✅ Missing header (401)
- ✅ Invalid token (401)

#### `TestGetSpaceById` (GET /spaces/{space_id})
- ✅ Success case (200)
- ✅ Not found (404)
- ✅ Missing header (401)
- ✅ Forbidden (403) - user doesn't own space

#### `TestCreateSpace` (POST /spaces)
- ✅ Success case (201)
- ✅ Missing body (400)
- ✅ Invalid payload (400)
- ✅ Missing header (401)

#### `TestDeleteSpace` (DELETE /spaces/{space_id})
- ✅ Success case (200)
- ✅ Not found (404)
- ✅ Forbidden (403) - user doesn't own space
- ✅ Missing header (401)

#### `TestRestoreSpace` (POST /spaces/{space_id}/restore) - **Superuser only**
- ✅ Success case - superuser (200)
- ✅ Forbidden - non-superuser (403)
- ✅ Not found (404)
- ✅ Missing header (401)

## Test Token vs Real Token

| Aspect | Test Token | Real Token |
|--------|-----------|-----------|
| Header | `x-test-token` | `Authorization: Bearer ...` |
| Environment | `development` only | All environments |
| DB Upsert | No | Yes (creates/updates user) |
| User ID | Fixed 9999999 | From Telegram OAuth |
| Permissions | None (test only) | From Telegram |
| Use Case | Integration tests | Production auth |

## Running Tests

```bash
# Run all spaces tests
pytest tests/integration/test_spaces_endpoints.py -v

# Run specific test class
pytest tests/integration/test_spaces_endpoints.py::TestGetSpaces -v

# Run specific test
pytest tests/integration/test_spaces_endpoints.py::TestGetSpaces::test_get_spaces_success_returns_200 -v
```

## Security Notes

⚠️ **IMPORTANT**: Test token support is **disabled in production**
- `verify_test_token()` checks `environment == "development"`
- If `environment != "development"`, it raises `OAUTH_CODE_INVALID` (401)
- Safe to keep test code in both environments

## Example Endpoint Implementation

```python
from typing import Annotated
from fastapi import APIRouter, Depends, Header, Request, status
from app.api.deps import get_auth_service
from app.core.trace import get_trace_id
from app.services.models import UserProfile

router = APIRouter(prefix="/spaces", tags=["spaces"])

@router.get("", status_code=status.HTTP_200_OK)
async def get_spaces(
    request: Request,
    x_test_token: str | None = Header(None),
    auth_service: Annotated[AuthService, Depends(get_auth_service)] = None,
) -> dict:
    trace_id = get_trace_id(request)
    
    if x_test_token:
        user, _ = await auth_service.verify_test_token(x_test_token, trace_id)
    else:
        token = extract_bearer_token(request)
        user, _ = await auth_service.verify_token(token, trace_id)
    
    # Fetch user's spaces from database
    spaces = []  # TODO: implement
    
    return {"spaces": spaces}


@router.post("/{space_id}/restore", status_code=status.HTTP_200_OK)
async def restore_space(
    space_id: str,
    request: Request,
    x_test_token: str | None = Header(None),
    auth_service: Annotated[AuthService, Depends(get_auth_service)] = None,
) -> dict:
    trace_id = get_trace_id(request)
    
    if x_test_token:
        user, _ = await auth_service.verify_test_token(x_test_token, trace_id)
    else:
        token = extract_bearer_token(request)
        user, _ = await auth_service.verify_token(token, trace_id)
    
    # Check superuser permission
    if user.permission != "admin":
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.PERMISSION_DENIED)
    
    # Restore space logic
    # TODO: implement
    
    return {"deleted_at": None}
```

## Next Steps

1. ✅ Test infrastructure is ready
2. 📝 Implement endpoints following the test template
3. 🧪 Run tests to verify endpoints work correctly
4. 📊 Add integration with actual database repositories
5. 🔒 Add permission checks for delete/restore operations
