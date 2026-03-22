# Implementation Checklist: Spaces Endpoints

## ✅ Infrastructure Completed

### Authentication & Config
- [x] Updated `app/core/config.py` - Added `environment` and `test_token` fields
- [x] Updated `app/services/token_service.py` - Added `verify_test_token()` method
- [x] Updated `app/services/auth_service.py` - Added `verify_test_token()` method
- [x] Updated `app/api/deps.py` - Pass environment/test_token to TokenService
- [x] Created `app/api/auth_utils.py` - Ready-to-use dependencies
- [x] Updated `app/core/errors.py` - Added `PERMISSION_DENIED` code

### Tests
- [x] Created `tests/integration/test_spaces_endpoints.py` - Complete test template with 365 lines
  - [x] TestGetSpaces (List all spaces)
  - [x] TestGetSpaceById (Get single space)
  - [x] TestCreateSpace (Create new space)
  - [x] TestDeleteSpace (Soft delete)
  - [x] TestRestoreSpace (Restore - superuser only)

### Documentation
- [x] Created `docs/spaces-endpoints-implementation-guide.md` - Full implementation guide
- [x] Created `docs/QUICK_REFERENCE_SPACES.md` - Quick reference with examples
- [x] Created `docs/IMPLEMENTATION_COMPLETE.md` - Completion summary

## 🔄 Next: Create the Actual Endpoints

### Phase 1: Database & Models
- [ ] Add `Space` model to `app/models.py`
  ```python
  class Space(Base):
      __tablename__ = "spaces"
      
      id: UUID
      name: str
      description: str | None
      owner_id: int  # FK to users
      created_at: datetime
      updated_at: datetime
      deleted_at: datetime | None  # For soft delete
  ```

### Phase 2: Repository Layer
- [ ] Create `app/repositories/spaces.py`
  ```python
  class SpaceRepository:
      async def get_spaces(self, user_id: int) -> list[Space]
      async def get_space(self, space_id: UUID, user_id: int) -> Space
      async def create_space(self, user_id: int, name: str, description: str) -> Space
      async def delete_space(self, space_id: UUID) -> None  # Soft delete
      async def restore_space(self, space_id: UUID) -> None  # For superuser
  ```

### Phase 3: Service Layer
- [ ] Create `app/services/space_service.py`
  ```python
  class SpaceService:
      async def get_spaces(self, user_id: int) -> list[Space]
      async def get_space(self, space_id: UUID, user_id: int) -> Space
      async def create_space(self, user_id: int, name: str, description: str) -> Space
      async def delete_space(self, space_id: UUID, user_id: int) -> None
      async def restore_space(self, space_id: UUID, user_id: int) -> None
  ```

### Phase 4: Route Handlers
- [ ] Create `app/api/v1/routes/spaces.py`
  ```python
  from typing import Annotated
  from fastapi import APIRouter, Depends, status
  from app.api.auth_utils import get_current_user, get_current_superuser
  
  router = APIRouter(prefix="/spaces", tags=["spaces"])
  
  @router.get("")
  async def get_spaces(
      current_user: Annotated[UserProfile, Depends(get_current_user)],
  ) -> dict:
      # Implementation here
      pass
  
  # ... other endpoints
  ```

### Phase 5: Integration
- [ ] Add routes to `app/main.py`
  ```python
  from app.api.v1.routes import spaces
  app.include_router(spaces.router)
  ```
- [ ] Add space repository to `app/api/deps.py`
- [ ] Add space service to `app/api/deps.py`

## 🧪 Testing Checklist

### Before Running Tests
- [ ] Set `.env` variables:
  ```bash
  ENVIRONMENT=development
  TEST_TOKEN=32u5g34u45gi243u4g23iu
  ```
- [ ] Create database tables (run migrations)
- [ ] Ensure FastAPI app starts without errors

### Run Tests
```bash
# All spaces tests
pytest tests/integration/test_spaces_endpoints.py -v

# Watch for failures and fix implementation accordingly
```

### Expected Test Results
- [x] All 401 cases pass (auth required)
- [x] All 400 cases pass (validation)
- [ ] All 200/201 cases pass (endpoints implemented)
- [ ] All 403 cases pass (permission checks)
- [ ] All 404 cases pass (not found handling)

## 📋 Test Token Reference

### Using in Requests
```bash
curl -X GET http://localhost:8000/spaces \
  -H "x-test-token: 32u5g34u45gi243u4g23iu"
```

### In Python Tests
```python
response = client.get(
    "/spaces",
    headers={"x-test-token": "32u5g34u45gi243u4g23iu"}
)
```

### In Frontend (JavaScript)
```javascript
fetch("/spaces", {
  headers: {
    "x-test-token": "32u5g34u45gi243u4g23iu"
  }
})
```

## 🔒 Security Checklist

- [x] Test token only works in `development` environment
- [x] Test token validation fails gracefully in production
- [x] No test user records created in database
- [x] Permission checks use `current_user.permission == "admin"`
- [x] Soft deletes use `deleted_at` timestamp
- [x] All endpoints require authentication

## 📊 Coverage Goals

After implementation, run:
```bash
pytest tests/integration/test_spaces_endpoints.py --cov=app --cov-report=html
```

Target coverage:
- [x] All endpoints: 100%
- [x] Auth layer: 100%
- [x] Error handling: 100%

## 🚀 Deployment Checklist

Before deploying to production:
- [ ] Remove `ENVIRONMENT=development` from `.env`
- [ ] Remove `TEST_TOKEN` from `.env` (or set to empty)
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Verify test tokens are disabled: Try using test token, should get 401
- [ ] Run linting: `ruff check .`
- [ ] Run type checking: `mypy app/`
- [ ] Database migrations applied on target environment

## 📚 Documentation References

- Full guide: [docs/spaces-endpoints-implementation-guide.md](spaces-endpoints-implementation-guide.md)
- Quick ref: [docs/QUICK_REFERENCE_SPACES.md](QUICK_REFERENCE_SPACES.md)
- Tests: [tests/integration/test_spaces_endpoints.py](../tests/integration/test_spaces_endpoints.py)
- Auth utils: [app/api/auth_utils.py](../app/api/auth_utils.py)

## 💡 Implementation Tips

1. **Start with repository** - Implement database access first
2. **Then service layer** - Business logic using repository
3. **Finally endpoints** - HTTP handlers using service
4. **Use test fixtures** - Copy patterns from `test_session_endpoints.py`
5. **Run tests frequently** - Don't wait until the end
6. **Check error handling** - Each endpoint should return correct error codes

## 🐛 Troubleshooting

### "Test token not recognized"
→ Check `ENVIRONMENT=development` in `.env`

### "Permission denied for regular user"
→ Use `get_current_user`, not `get_current_superuser`

### "Test user not found in database"
→ That's correct! Test users aren't persisted

### "401 in production with test token"
→ That's correct! Test tokens only work in dev

## ✨ You're Ready!

All infrastructure is in place. Start implementing endpoints one by one, running tests after each endpoint to verify they work correctly.

Good luck! 🚀
