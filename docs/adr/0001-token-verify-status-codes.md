# ADR 0001: Token verify status codes

## Context
Issue #56 requests `201 Created` when a user is created and `202 Accepted` when the user already exists.

## Decision
Implement `201` for newly created users and `202` for existing users to match the requirement, even though `200 OK` is the more typical response for a synchronous read/update.

## Consequences
- Clients must not treat `202` as an async operation; it is used for compatibility with the current issue requirement.
- If the contract is revisited, `200 OK` should replace `202` for existing users.
