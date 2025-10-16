# ActiveSync Provisioning Loop Analysis – 15 Oct 2025

## Symptoms Observed
- iOS 17 (iPadOS 26.0.1) device `MPSC4UO9KL193BQ8VB5TAL08AG` cannot download folder hierarchy (FolderSync returns HTTP 449).
- `logs/activesync/activesync.log` shows repeating `Cmd=FolderSync` immediately redirected to `Cmd=Provision`, never advancing past provisioning.
- No `provision_acknowledgment_final` or `provision_initial_*` instrumentation surfaced, indicating the server never recognized a successful MS-ASPROV phase 2 acknowledgment.

## Log Evidence (2025-10-15 04:59 UTC)
- `provisioning_required` gate fires with `client_policy_key: "0"` and `server_policy_key: "3492701102"` before every FolderSync request (logs/activesync/activesync.log:36).
- Provision requests are received and parsed, but `parsed_policy_key` is empty and `is_acknowledgment` remains `false` (logs/activesync/activesync.log:21,30,45,54).
- OPTIONS handshake continues to advertise `x-ms-policykey: 0`, confirming the client never transitions to the acknowledged policy key state.

## Code Comparison
- **FastAPI router gate** (`app/routers/activesync.py:1280-1325`): FolderSync is denied unless `device.policy_key` is non-zero *and* `device.is_provisioned == 1`. The handler injects a random policy key into 449 responses to guide the client, but never sets `is_provisioned` without an explicit acknowledgment.
- **Acknowledgment detection** (`app/routers/activesync.py:1374-1408`): Server expects a Provision request with `Status=1`, no policy data, and a `PolicyKey` that matches the value persisted in `activesync_devices.policy_key`. If this signature is not observed, provisioning stays in phase 1.
- **grommunio reference**: Native logic (`grommunio-sync/lib/request/foldersync.php:240-255` and `grommunio-sync/lib/core/provisioningmanager.php:110-133`) mirrors the requirement that FolderSync only proceeds after `ProvisioningManager::ProvisioningRequired` returns false. `Provisioning::Handle` generates a new policy key per request and finalizes it only after the client returns Status 1 with the prior key.

## Database Snapshot
- `activesync_devices` row for the affected device shows `policy_key = 3492701102`, `is_provisioned = 0`, `last_seen = 2025-10-15 04:59:19` (data/email_system.db).
- Relevant schema excerpts:
  - `activesync_devices(id, user_id, device_id, policy_key, is_provisioned, last_seen, created_at)`.
  - `activesync_state(id, user_id, device_id, collection_id, synckey_uuid, synckey_counter, sync_key, ... )` manages per-collection hierarchy and data state.
  - Supporting tables (`emails`, `calendar_events`, `contacts`, `mapi_*`) remain untouched during the failing transaction, confirming the block is purely at the provisioning gate.

## Root Cause Hypothesis
1. The device performs the MS-ASPROV phase 1 request (policy download) successfully.
2. The server issues a non-zero policy key (`3492701102`) but never records a valid acknowledgment; `is_provisioned` stays 0.
3. Because `is_provisioned != 1`, subsequent FolderSync commands are forced back to Provision with HTTP 449, preventing folder hierarchy download.
4. Likely contributors:
   - WBXML parser not extracting the PolicyKey/Status pair from the acknowledgment payload (string-table handling gap or token coverage in `parse_wbxml_provision_request`).
   - Client possibly re-sending phase 1 before receiving the full response; since the implementation re-generates random policy keys on each phase 1 response, any delayed acknowledgment that cites an older key will be rejected.
   - Absence of logged `provision_initial_*` events hints that the initial handler returned before emitting diagnostics (worth validating in runtime instrumentation).

This behavior violates MS-ASPROV 16.1 section 3.2.5.2, which mandates that servers allow the client to complete the two-step Provision sequence and only block FolderSync until a final acknowledgment (Status 1, PolicyKey match) is processed.

## Recommended Fix Path
1. **Harden acknowledgment detection**  
   - Accept the `X-MS-PolicyKey` header as a fallback when the body lacks a WBXML PolicyKey (some iOS builds send minimal ACK payloads).  
   - Ensure `parse_wbxml_provision_request` handles string-table encoded strings and all Provision tags defined in MS-ASPROV 16.1 section 2.2.2.
2. **Stabilize PolicyKey lifecycle**  
   - Avoid generating a new random key on every phase 1 response unless the previous transaction completed (track `provision_phase` in the database or store a `pending_policy_key`).  
   - Mirror grommunio’s pattern: temporary key in phase 1, final key committed after phase 2.
3. **Improve observability**  
   - Restore/verify `provision_initial_*` logging so missing phases are visible.  
   - Add explicit logging when `is_provisioned` transitions or when acknowledgments are rejected (include policy key values and reasons).
4. **Regression tests**  
   - Add an integration test harness that replays MS-ASPROV 16.1 handshake (phase 1 + phase 2) and asserts `is_provisioned` flips to 1 and FolderSync returns Status 1.  
   - Cover edge cases: duplicate ACK, delayed ACK after key rotation, legacy clients that respond with `PolicyKey=0`.

## Continuous Improvement Methodology
1. **Spec Alignment Reviews** – For every protocol-facing change, map implementation checkpoints to MS-AS* spec clauses (MS-ASPROV, MS-ASCMD) and capture the mapping in design docs.  
2. **Handshake Test Matrix** – Maintain automated WBXML conversational tests for iOS, Android, Outlook, and Windows Mail, executed on each release candidate.  
3. **State Validation Checklist** – Before production rollouts, snapshot `activesync_devices` and `activesync_state` to ensure policy keys, sync keys, and provisioning flags match expected transitions.  
4. **Observability Baseline** – Define required log events per command (OPTIONS, Provision phases, FolderSync). Failing to observe these events in staging marks the build as non-compliant.  
5. **Postmortem Template** – Document each incident with root cause, detection gaps, and mitigations; feed the action items back into the regression suite or monitoring configuration to prevent recurrence.  
6. **Change Guards** – Require code review sign-off from a protocol specialist whenever modifying provisioning logic, plus a “spec compliance” checklist attached to the PR/merge request.

## Database Structure Notes
- `activesync_devices`: authoritative store for policy state (non-null PolicyKey implies provisioning progress).  
- `activesync_state`: per-collection sync state, including FolderSync SyncKey counters.  
- `emails`, `calendar_events`, `contacts`: content repositories accessed once provisioning succeeds.  
- `mapi_objects`, `mapi_sessions`, `mapi_sync_states`: bridge tables for MAPI interoperability; untouched in this incident but relevant for comprehensive sync behavior analysis.

## Spec Pointers
- **MS-ASPROV 16.1**  
  - Section 3.1.5: two-phase provisioning overview.  
  - Section 3.2.5.2: server behavior when policies change—return Status 142 (HTTP 449) until acknowledgment.  
  - Section 2.2.2.69 (PolicyKey) and 2.2.2.71 (Status): mandatory elements for provisioning acknowledgment.
- **MS-ASCMD 16.1**  
  - Section 2.2.3.29 (FolderSync) references provisioning prerequisite via `Status` 142.

Use these sections as the authoritative checklist when adjusting provisioning logic or validating client interoperability.

