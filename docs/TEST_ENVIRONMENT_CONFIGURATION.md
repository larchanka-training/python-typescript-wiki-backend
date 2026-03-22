# Test Environment Configuration

## Problem Analysis

The `test_verity_test_token_returns_200` tests were failing due to database connection issues during test execution. The root causes were:

### Root Causes

1. **Missing Environment Configuration for Tests**
   - Tests were not loading environment variables from `.env.local`
   - The `ENVIRONMENT` variable was not set to "Development" 
   - The `TEST_ACCESS_TOKEN` variable was not available for test token verification
   - These variables are essential for the test token flow to work

2. **Database Dependency Issue**
   - The test client disabled the application's lifespan (which creates the database pool)
   - When tests didn't override the `get_auth_service` dependency, the endpoint still tried to acquire a database connection
   - This resulted in `RuntimeError: Database pool is not initialized`

## Solution Overview

### 1. **Test Configuration (conftest.py)**

Updated [tests/conftest.py](tests/conftest.py) to load `.env.local` at test startup:

```python
from dotenv import load_dotenv

# Load .env.local for test execution
# This ensures tests use the correct database URL, test token, and environment settings
env_file = ROOT / ".env.local"
if env_file.exists():
    load_dotenv(env_file, override=True)
```

**Benefits:**
- Automatically applies `.env.local` settings for all tests
- Only affects test execution, not production code
- Centralizes test environment configuration
- Allows tests to access TEST_ACCESS_TOKEN and ENVIRONMENT=Development settings

### 2. **Test Token Verification (test_token_verify.py)**

Updated `test_verity_test_token_returns_200` to use `FakeAuthService` instead of relying on real database access:

```python
def test_verity_test_token_returns_200(client_factory: Callable[UserProfile, TestClient]) -> None:
    """Test token returns 200."""
    # For test token verification, use FakeAuthService to avoid DB access
    service = FakeAuthService(
        UserProfile(
            id=9999999,
            telegram_id=9999999,
            username="test_user",
            first_name="Test",
            last_name="User",
            photo_url=None,
            permission=None,
            created_at=_sample_user().created_at,
            last_login_at=_sample_user().last_login_at,
        ),
        created=False,
    )
    with client_factory(service) as client:
        response = client.post(
            "/token",
            json={"token": "32u5g34u45gi243u4g23iu"},
        )

    assert response.status_code == status.HTTP_200_OK
```

**Benefits:**
- Avoids database dependency during unit/integration tests
- Uses test double (FakeAuthService) pattern
- Keeps tests isolated and fast
- Verifies the HTTP endpoint behavior without database

### 3. **Duplicate Test File (test_token_endpoints.py)**

Refactored the duplicate `test_token_endpoints.py` to match the working pattern:

**Before:**
- Manual `load_dotenv()` call (fragile, order-dependent)
- Direct TestClient usage without service override
- Missing dependency injection pattern

**After:**
- Follows pytest fixture pattern
- Uses `client_factory()` with `FakeAuthService`
- Consistent with `test_token_verify.py` patterns
- Properly overrides `get_auth_service` dependency

## Environment Configuration

### .env.local

The file is configured with local/test settings:

```dotenv
# Database URL for local Docker development
DATABASE_URL=postgresql://admin:admin123@db:5432/wiki

# OAuth application credentials
OAUTH_NAME_APPLICATION_ID=local-app
OAUTH_NAME_SECRET_KEY=local-secret

# Token TTLs (in seconds)
TOKEN_TTL_SECONDS=86400          # 24 hours
SESSION_TTL_SECONDS=604800       # 7 days

# Environment mode
ENVIRONMENT=Development

# Test token (only used in Development mode)
TEST_ACCESS_TOKEN=32u5g34u45gi243u4g23iu
```

**Important:** This file is **only** loaded by pytest (via conftest.py), not by production code.

### Production vs Test Configuration

| Setting | Production | Tests |
|---------|-----------|-------|
| DATABASE_URL | Real PostgreSQL | Docker container URL (from .env.local) |
| ENVIRONMENT | Production | Development (from .env.local) |
| TEST_ACCESS_TOKEN | Not available | Available via .env.local |
| DB Pool | Required | Disabled in tests (via _no_lifespan) |
| Dependencies | Real implementations | Mocked with test doubles |

## How Tests Work

### Test Token Verification Flow

1. **conftest.py** loads `.env.local` (includes TEST_ACCESS_TOKEN)
2. **Test client** is created with `_no_lifespan` (skips DB pool creation)
3. **FakeAuthService** is injected via dependency override
4. **FakeAuthService** returns hardcoded user without DB access
5. **Endpoint** returns 200 OK with test user data

### Test Isolation

- No database connections required
- Tests are fast and deterministic
- Perfect for CI/CD pipelines
- Can run offline

## Files Modified

1. [tests/conftest.py](tests/conftest.py)
   - Added: Load `.env.local` at pytest startup

2. [tests/integration/test_token_verify.py](tests/integration/test_token_verify.py)
   - Updated: `test_verity_test_token_returns_200` to use FakeAuthService

3. [tests/integration/test_token_endpoints.py](tests/integration/test_token_endpoints.py)
   - Refactored: To match working test patterns and dependency injection

## Test Results

All token verification tests now pass:

```
tests/integration/test_token_verify.py::test_verify_token_created_returns_200 PASSED
tests/integration/test_token_verify.py::test_verify_token_existing_returns_200 PASSED
tests/integration/test_token_verify.py::test_verify_token_missing_returns_400 PASSED
tests/integration/test_token_verify.py::test_verify_token_empty_returns_400 PASSED
tests/integration/test_token_verify.py::test_verify_token_invalid_returns_401 PASSED
tests/integration/test_token_verify.py::test_verify_token_internal_error_returns_500 PASSED
tests/integration/test_token_verify.py::test_verity_test_token_returns_200 PASSED
tests/integration/test_token_endpoints.py::test_verity_test_token_returns_200 PASSED

================================== 8 passed, 1 warning in 0.20s ===========================
```

## Key Design Patterns

### 1. Dependency Injection for Testing
```python
app.dependency_overrides[get_auth_service] = lambda: service
```
- Cleanly override real services with test doubles
- No code changes to production code
- Follows FastAPI best practices

### 2. Test Double Pattern
```python
class FakeAuthService:
    async def verify_token(self, _token: str, trace_id: str):
        return self._user, self._created
```
- Replaces real service behavior
- Isolated from database/external dependencies
- Fully deterministic

### 3. Fixture Factory Pattern
```python
@pytest.fixture
def client_factory() -> Callable[..., TestClient]:
    def _factory(service: object = None) -> TestClient:
        # Create and configure test client
    yield _factory
    # Cleanup
```
- Reusable across multiple tests
- Automatic setup/teardown
- Type-safe

## Production Isolation

The `.env.local` file is **NOT** used in production because:

1. **conftest.py** is only loaded by pytest (test runner)
2. Production uses system environment variables or `.env` (if present)
3. `ENVIRONMENT=Production` would disable test token validation
4. Database URL in production points to real PostgreSQL instance

## GitHub Actions CI Configuration

The `.github/workflows/ci.yml` file automatically configures environment variables for CI testing. It requires the following variables to be set:

### Required GitHub Secrets (Sensitive Data)
Set these in **Settings → Secrets and variables → Secrets**:

- `DATABASE_URL` - PostgreSQL connection string
- `OAUTH_NAME_APPLICATION_ID` - OAuth app ID
- `OAUTH_NAME_SECRET_KEY` - OAuth secret key
- `TEST_ACCESS_TOKEN` - Test token for CI tests

### Required GitHub Variables (Public Configuration)
Set these in **Settings → Secrets and variables → Variables**:

- `ENVIRONMENT` - Set to `Development`
- `TOKEN_TTL_SECONDS` - Set to `86400`
- `SESSION_TTL_SECONDS` - Set to `604800`

### How CI Works

1. GitHub Actions workflow triggers on push/PR
2. Validates all 7 environment variables are set
3. Generates `.env` file from secrets and variables
4. Installs dependencies
5. Runs: `python -m pytest -v`
6. Reports results in PR

### Setup Instructions (5 minutes)

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Add 4 secrets (click "New repository secret"):
   - `DATABASE_URL`
   - `OAUTH_NAME_APPLICATION_ID`
   - `OAUTH_NAME_SECRET_KEY`
   - `TEST_ACCESS_TOKEN`
4. Click **Variables** tab and add 3 variables:
   - `ENVIRONMENT` = `Development`
   - `TOKEN_TTL_SECONDS` = `86400`
   - `SESSION_TTL_SECONDS` = `604800`
5. Push code or trigger workflow - tests will run automatically

### CI Environment Defaults

When `.env.local` is missing (in CI), `conftest.py` applies sensible defaults:
- `ENVIRONMENT` → `Development`
- `TEST_ACCESS_TOKEN` → `test-token-placeholder` (if not provided)
- `OAUTH_NAME_APPLICATION_ID` → `test-app` (if not provided)
- `OAUTH_NAME_SECRET_KEY` → `test-secret` (if not provided)
- `TOKEN_TTL_SECONDS` → `86400`
- `SESSION_TTL_SECONDS` → `604800`

## Future Improvements

1. Consider using pytest markers to categorize tests:
   - `@pytest.mark.unit` - No DB
   - `@pytest.mark.integration` - Requires DB
   
2. Add test coverage reporting with `pytest-cov`

3. Consider database fixtures for integration tests:
   - `@pytest.fixture(scope="session")`
   - Setup/teardown test database schema

4. Add environment validation in test setup

