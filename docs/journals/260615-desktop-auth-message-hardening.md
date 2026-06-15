# Desktop Authentication Message Hardening

## Problem

The Desktop login dialog exposed implementation details such as the database
technology, connection state, environment variable names, and exception types.

## Decision

- Show neutral operator messages for invalid credentials, access denial, and
  temporary authentication unavailability.
- Keep backend and exception details in local diagnostic logs only.
- Never include passwords, connection strings, hosts, or database names in UI text.

## Verification

- Unit tests cover invalid credentials, missing shared authentication
  configuration, service initialization failures, and data-store exceptions.
- UI tests confirm the dialog renders the neutral message without backend terms.
