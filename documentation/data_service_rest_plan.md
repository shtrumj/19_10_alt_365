# Data Service Separation Plan (REST)

## Goals
- Move all database and ORM usage into a dedicated data-service container.
- Expose CRUD and workflow primitives over HTTP/REST so the API gateway (SMTP, ActiveSync, EWS, MAPI, Web UI) becomes stateless.
- Maintain existing behaviours (queue processing, push notifications) via API contracts.

## Current Direct Database Usage
| Area | Models | Operations |
| --- | --- | --- |
| `app/smtp_server.EmailHandler` | `User`, `Email` | Lookup user by email, insert incoming email, trigger notifications. |
| `app/email_queue` & `queue_processor` | `EmailQueue` tables | Enqueue outbound mail, update delivery state. |
| `app/email_delivery` | `SessionLocal`, `Email` | Persist MIME content for outbound emails. |
| `app/routers/ews` | `Email`, `EmailAttachment`, `CalendarEvent`, `Contact` | Query lists by owner, save sent items. |
| `app/routers/mapihttp` & `app/mapi_store` | `User`, `Email`, `Mailbox`, `Folder`, `ActiveSyncState` | Authenticate, enumerate folders/items, update read state. |
| `app/routers/autodiscover` | `User` | Fetch display name by email. |
| ActiveSync (`app/routers/activesync` etc.) | `ActiveSyncDevice`, `ActiveSyncState`, `Email` | Device registration, sync state, change tracking. |

## Target REST Service
- **Framework**: FastAPI + SQLAlchemy (existing models reused).
- **Authentication**: Internal shared token (`X-Internal-Auth`) with optional mTLS in future.
- **Endpoints (initial set)**:
  - `/internal/auth/login` – validate credentials, return user metadata.
  - `/internal/users/{id}` & `/internal/users:lookup` – fetch user by id/email.
  - `/internal/emails` – create/list/update emails (filters by user/folder).
  - `/internal/emails/{id}/attachments` – fetch attachment metadata/content.
  - `/internal/folders` – enumerate distinguished folders per user.
  - `/internal/calendar` – list events per user.
  - `/internal/contacts` – list contacts per user/search.
  - `/internal/queue` – enqueue outbound email, dequeue for worker, ack results.
  - `/internal/activesync/state` – CRUD for device + sync state.
- **Background jobs**: queue processor lives inside data-service (reuse current logic), exposed via REST for control.

## Client Integration
- Create `app/data_client.py` with typed helper functions wrapping `httpx.AsyncClient`.
- Replace direct `SessionLocal` usage with client calls, starting with SMTP handler to validate workflow.
- Ensure serialization matches existing models (e.g., ISO timestamps, base64 for MIME/attachments).

## Deployment
- New Docker image `data-service` with gunicorn/uvicorn server.
- Update `docker-compose` to run `data-service` and point main `email-system` container to it via environment variables (`DATA_SERVICE_URL`, `DATA_SERVICE_TOKEN`).
- Health checks for both services.

## Testing Strategy
- Unit tests for REST handlers (using FastAPI `TestClient`).
- Integration tests that spin up both FastAPI apps (data-service + primary API) and run SMTP/ActiveSync flows.
- Contract tests verifying client DTOs against service responses (pydantic models).

## Next Steps
1. Scaffold FastAPI data-service with health/auth endpoints and Dockerfile.
2. Introduce client library and migrate SMTP server to REST calls.
3. Expand to ActiveSync, EWS, and MAPI progressively, ensuring regression coverage after each subsystem migration.
