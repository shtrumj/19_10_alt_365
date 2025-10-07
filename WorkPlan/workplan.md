# workplan.md

## 0) Purpose & scope

Design and implement an **Exchange-like mail platform** using open-source components with a **stateless protocol layer**, a **typed core API**, and an **asynchronous pipeline** backed by **Valkey** and **PostgreSQL**, storing message blobs in **S3-compatible object storage (MinIO)** and exposing rich **observability**.

This workplan describes **what to build and how it should behave** (architecture, interfaces, data flows, SLOs, security, deployment, and milestones). It is **text-only** and implementation-agnostic (compatible with Python/FastAPI and/or Rust/Axum).

---

## 1) High-level architecture (target state)

- **Edge/Gateway**
  - `NGINX` terminates TLS, enforces rate limits, request size limits, and maps paths to internal services.
  - Supports HTTP/2 and HTTP/3 (QUIC). gRPC-web proxy enabled for any browser-based admin/UI.

- **Identity & Access**
  - `Keycloak` for user auth (OIDC/SAML). Issues access tokens (JWT).
  - Service-to-service auth via mTLS + short-lived client credentials (Keycloak client credentials or Vault-issued certs).
  - Role-based access control (RBAC) for admin endpoints.

- **Protocol services (stateless)**
  - `ActiveSync/OWA` service (FastAPI or Axum).
  - `MAPI/EWS` gateway (subset necessary for calendar, contacts, tasks).
  - `SMTP` submission & inbound via `Postfix` or `OpenSMTPD`.
  - Optional `IMAP` (Dovecot) for compatibility.
  - All protocol services export `/healthz`, `/readyz`, `/metrics`, and include correlation ids.

- **Core API (typed contract)**
  - `gRPC` service as the **single source of truth** for mailbox state transitions, search queries, ACLs, and task orchestration.
  - Versioned protobufs with backward compatibility and explicit error codes.

- **Async backbone**
  - `Valkey cluster` for:
    - **Cache** (hot mailbox metadata, rate limiting, dedupe keys).
    - **Streams** (queues) with consumer groups:
      - `mail_ingest`
      - `index`
      - `notify`
      - `retention`

    - Dead-letter queues: `dlq:*`.

  - Workers are idempotent and checkpoint via stream offsets.

- **Storage**
  - `PostgreSQL`:
    - `mail_state` schema (folders, flags, threading, ACLs).
    - `audit` schema (protocol and admin actions).
    - `queue` schema (task registry, retries).

  - `MinIO`:
    - Buckets per tenant/domain.
    - Stores RFC822 messages, attachments, and large blobs.

  - Search:
    - `OpenSearch` or `Meilisearch` for full-text and multilingual search.
    - Indexers consume from `index` stream.

- **Observability**
  - Metrics: `Prometheus` + `Grafana`.
  - Logs: `Loki`.
  - Traces: `Tempo` or `Jaeger` with OpenTelemetry.
  - Dashboards for per-protocol latency, queue depth, DB health, and error budgets.

---

## 2) Functional requirements

1. **Mail send/receive**
   - SMTP submission with DKIM signing option.
   - Inbound SMTP accepts mail, normalizes, enqueues to `mail_ingest`.

2. **Sync**
   - ActiveSync: FolderSync, Sync, GetItemEstimate, ItemOperations (bodies/attachments).
   - MAPI/EWS: minimal subset for calendar/contacts (phase 2).
   - Optional IMAP read-only compatibility (phase 3).

3. **Search**
   - Full-text queries (subject, body, attachments OCR phase 3).
   - Fast prefix/term queries; ranking by recency & thread position.

4. **Mailbox state**
   - Flags (read, flagged), categories/labels (extensible), threading.

5. **Notifications**
   - Push/WS to OWA; APNs/FCM for mobile (phase 2).

6. **Admin**
   - Tenants, domains, users, quotas, retention policies, journaling.

7. **Auditing**
   - Every protocol action and admin operation recorded with correlation id.

---

## 3) Non-functional requirements (SLOs & constraints)

- **Availability**: 99.9% monthly for API and SMTP submission.
- **Latency p95**:
  - ActiveSync Sync (no body fetch): ≤ 250 ms.
  - ItemOperations small body: ≤ 700 ms.
  - Search API: ≤ 800 ms for indexed queries.

- **Throughput**: sustain 100 msgs/sec ingest (baseline), scale linearly.
- **Durability**: no message loss; at-least-once processing with idempotency.
- **Security**: TLS everywhere, mTLS internal, secrets via Vault, least-privilege RBAC.
- **Portability**: deployable on Docker Compose (dev) and Kubernetes (prod).

---

## 4) Data model (essential tables & keys)

### 4.1 `mail_state` schema

- `users(id, tenant_id, email, display_name, status, created_at)`
- `mailboxes(id, user_id, name, type, parent_id, created_at, attributes jsonb)`
- `messages(id, mailbox_id, uid, thread_id, subject, from, to_cc_bcc jsonb, date, flags text[], size_bytes, headers jsonb, blob_key, checksum, created_at)`
- `message_parts(id, message_id, part_id, mime_type, size_bytes, blob_key, inline bool, filename)`
- `acl(id, mailbox_id, grantee, rights text[])`
- Indexing:
  - `(mailbox_id, uid)` unique
  - GIN on `headers`, `to_cc_bcc`, `flags`

### 4.2 `queue` schema

- `tasks(task_id uuid pk, type, status, attempt, created_at, updated_at, error text)`
- `task_events(task_id, ts, event, payload jsonb)`

### 4.3 `audit` schema

- `events(id bigserial pk, ts, actor, actor_ip, action, resource, correlation_id, details jsonb)`

### 4.4 Object store keys (MinIO)

- `blobs/{tenant}/{yyyy}/{mm}/{dd}/{message_id}.eml`
- `parts/{tenant}/{message_id}/{part_id}`

---

## 5) Message/processing flows (happy paths)

### 5.1 Inbound mail (SMTP → store)

1. Postfix accepts message, performs basic checks (SPF/DMARC phase 2).
2. Postfix hands off to `smtp_ingest` service (LMTP or pipe).
3. `smtp_ingest` writes raw `.eml` to MinIO, computes checksum, emits to `mail_ingest` stream:
   - `{message_id, tenant, mailbox_hint, blob_key, checksum, correlation_id}`

4. `ingest_worker`:
   - Parse headers/MIME, extract parts metadata.
   - Create `messages` + `message_parts` rows in Postgres (atomic).
   - Enqueue to `index` stream with essential fields for search.
   - Enqueue to `notify` for clients.

### 5.2 ActiveSync sync/read

1. Client hits `ActiveSync` via NGINX with JWT.
2. Svc queries `mail_state` via gRPC; uses Valkey cache for recent folder state and `sync_key`.
3. If bodies needed: emit `mail_fetch` (or reuse `mail_ingest` with op=`fetch`) → worker reads blob from MinIO and serves (or caches).
4. Responses contain serverIds stable across moves (thread-safe).

### 5.3 Search

1. Query arrives at gRPC Search endpoint.
2. Query translated to OpenSearch/Meilisearch.
3. Return message ids + snippets; hydrate metadata from Postgres.

---

## 6) Valkey usage (required patterns)

- **Cache keys**
  - `mbx:{user_id}:{mailbox_id}:state` → JSON state, TTL 60s.
  - `dedupe:{checksum}` → NX set to avoid duplicate ingest.
  - `rate:{ip}:{route}` → counters for NGINX shadow decisions.

- **Streams & groups**
  - `mail_ingest` (group `ingesters`)
  - `index` (group `indexers`)
  - `notify` (group `notifiers`)
  - `retention` (group `janitors`)
  - Dead-letter policy: after `N` attempts (default 5) → `dlq:{stream}` with full payload and error.

- **Idempotency**
  - Workers compute a deterministic `work_key` (e.g., message checksum or message_id) and use `SET NX` to fence duplicates.

---

## 7) Security model

- **Transport**
  - TLS 1.2+ externally; mTLS for all internal east-west traffic.

- **Identity**
  - Human users via Keycloak realms (tenants) and OIDC; service accounts via Keycloak client creds.

- **Authorization**
  - RBAC: roles `admin`, `support`, `user`.
  - Mailbox ACLs enforced in gRPC (single choke-point).

- **Secrets**
  - HashiCorp Vault for DB creds, SMTP creds, DKIM keys, MinIO access keys; 24h rotation.

- **Data-at-rest**
  - MinIO SSE-S3 or SSE-C; PostgreSQL with disk encryption (LUKS/ZFS native).

- **Audit**
  - All admin/protocol actions logged to `audit.events` + Loki.

---

## 8) Observability standards

- **Metrics (Prometheus)**
  - `http_requests_total`, `request_duration_seconds{route,code}`
  - `queue_depth{stream}`, `consumer_lag{stream,group}`
  - DB: `pg_stat_activity`, `wal_rate`, `replication_lag`

- **Logs (Loki)**
  - JSON logs with `trace_id`, `correlation_id`, `tenant`, `user`, `service`.

- **Traces (OTel)**
  - NGINX → protocol svc → gRPC → worker → DB/MinIO; sampling 10% in prod.

- **Dashboards**
  - Protocol latency, error budget burn, queue health, top tenants, DB I/O, MinIO I/O.

---

## 9) Deployment & environments

- **Dev**
  - Docker Compose stack: NGINX, Keycloak, Valkey, Postgres, MinIO, Prometheus, Grafana, Loki, Tempo, protocol services, gRPC API, workers.
  - Seed scripts create demo tenant and users.

- **Stage**
  - Kubernetes: one namespace per environment, Helm charts per component.
  - pgBouncer in transaction mode; Postgres HA via Patroni or Cloud provider.
  - MinIO 4-node distributed mode.

- **Prod**
  - Multi-AZ deployment.
  - HPA rules:
    - Protocol services scale on p95 latency and CPU.
    - Workers scale on `queue_depth` and `consumer_lag`.

  - Zero-downtime deploys: rolling with readiness gates for DB/Valkey.

---

## 10) Backup, retention, and DR

- **PostgreSQL**
  - PITR via continuous WAL archiving (e.g., WAL-G to S3).
  - Daily base backups, retention 14–30 days.

- **MinIO**
  - Versioning + lifecycle rules; cross-region replication optional.

- **Valkey**
  - Persistence (AOF) for streams; scheduled RDB snapshots.

- **Runbooks**
  - Restore drills quarterly; document RTO/RPO (target RPO ≤ 5 min; RTO ≤ 30 min).

---

## 11) Performance & capacity planning

- **Sharding strategy**
  - Primary key space partitioned by `tenant_id` then `user_id`.
  - Postgres partitioning by `tenant_id` or by month for `messages`.

- **Indexes**
  - GIN on JSONB fields; btree on `(mailbox_id, uid)`.

- **Caching policy**
  - Positive cache for mailbox listings; negative cache for missing ids (short TTL).

---

## 12) Testing strategy

- **Unit tests**
  - MIME parsing, ACL enforcement, idempotent workers.

- **Integration tests**
  - Testcontainers: spin Postgres, MinIO, Valkey; run end-to-end ingest and ActiveSync Sync.

- **Protocol conformance**
  - Golden files for ActiveSync WBXML responses.

- **Chaos & load**
  - Fault injection: drop MinIO temporarily, slow Postgres, duplicate messages.
  - k6/gatling for protocol latency; stream pressure tests.

---

## 13) Phased delivery & milestones

**Phase 0 — Foundations (Week 1–2)**

- Repos, proto contracts, CI/CD scaffolding.
- Compose dev stack; hello-world endpoints; OTel wiring.

**Phase 1 — Core Mail Ingest (Week 3–5)**

- SMTP ingest → MinIO → `mail_ingest` → Postgres.
- Index worker → search engine.
- Basic OWA listing via gRPC.

**Phase 2 — ActiveSync (Week 6–9)**

- FolderSync/Sync/ItemOperations for plain-text + small HTML bodies.
- Push notifications (notify stream → WS/APNs/FCM stub).
- Caching and sync keys.

**Phase 3 — Admin & Security (Week 10–12)**

- Tenants, users, quotas; RBAC in gRPC.
- DKIM keys in Vault; SMTP submission with signing.

**Phase 4 — Resilience & Scale (Week 13–16)**

- HA Postgres (Patroni), distributed MinIO, Valkey cluster.
- DLQs, retry policies, dashboards, alerts.
- Load tests + DR drill.

**Phase 5 — Optional Protocols (ongoing)**

- MAPI/EWS subset; IMAP compatibility; OCR for attachments; advanced search.

---

## 14) Acceptance criteria (per phase)

- **Foundations**: All services start locally; `/healthz`, `/metrics` present; traces visible.
- **Ingest**: Sending a test email yields a stored `.eml`, DB rows, search index doc.
- **ActiveSync**: A mobile client performs initial sync and fetches bodies; p95 latencies met.
- **Security**: Users authenticate via Keycloak; RBAC enforced; audit entries created.
- **Resilience**: Forced failures trigger retries; no duplicates; DLQ visible and drainable.

---

## 15) Naming, conventions, and contracts

- **Service names**: `svc-activesync`, `svc-mapi`, `svc-smtp-ingest`, `svc-imap`, `svc-grpc`, `worker-ingest`, `worker-index`, `worker-notify`, `worker-retention`.
- **Headers**: `X-Trace-Id`, `X-Correlation-Id`, `X-Tenant`.
- **gRPC error model**: canonical codes (INVALID_ARGUMENT, NOT_FOUND, PERMISSION_DENIED, ABORTED, UNAVAILABLE).
- **Semantic versioning** for protobufs and REST shims.

---

## 16) Risks & mitigations

- **Protocol edge cases (ActiveSync/MAPI)** → start with minimal subset + robust server feature detection; use golden logs to validate.
- **Search consistency** → eventual consistency documented; fallback to DB for critical filters.
- **Blob/metadata divergence** → checksum on write, periodic reconciler worker.
- **Hot partitions** → mailbox-level rate limiting via Valkey; sharding strategy reviewed quarterly.

---

## 17) Open-source stack (baseline)

- NGINX, Keycloak, Valkey, PostgreSQL (+pgBouncer), MinIO, OpenSearch/Meilisearch, Prometheus, Grafana, Loki, Tempo/Jaeger.
- Language runtimes: Python 3.11+ (FastAPI, SQLAlchemy async) and/or Rust 1.79+ (Axum, sqlx).
- Containerization: Docker/Podman; Helm charts for K8s.

---

## 18) What “done” looks like (MVP)

- A user can:
  - Authenticate, receive email, view mailbox list and messages in OWA, and fetch message bodies on mobile via ActiveSync.
  - Search subject/body.

- Operators can:
  - Observe health/latency/queue depth in Grafana.
  - Replay failed items from DLQ.
  - Restore from backup in a documented runbook.

---

_End of workplan.md_
