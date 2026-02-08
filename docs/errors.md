# Error codes contract

All API error responses use a single, machine-readable format:

```json
{
  "status": "error",
  "message": "<ERROR_CODE>",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

Rules:
- No human-readable text is returned from the backend.
- The frontend maps `message` to localized messages.
- `X-Trace-Id` is returned in the response headers for support/debugging.
- Source of truth for error codes: `docs/Формат ошибок.md`.

## Codes used by token verification

| Code | Meaning | HTTP |
| --- | --- | --- |
| VALIDATION_ERROR | Invalid request body (missing/empty token, wrong types, invalid JSON). | 400 |
| OAUTH_CODE_INVALID | Token is invalid or expired after crypto/TTL checks. | 401 |
| INTERNAL_ERROR | Internal or database failure. | 500 |

## Codes used by session endpoints

| Code | Meaning | HTTP |
| --- | --- | --- |
| SESSION_MISSING | Session token missing. | 401 |
| SESSION_EXPIRED | Session expired or revoked. | 401 |
