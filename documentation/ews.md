## EWS Endpoint Specification (Current Implementation)

This document describes the current behavior of the EWS endpoint implemented by the server so the endpoint can be recreated from this spec alone.

### Overview

- URL: `/EWS/Exchange.asmx`
- Protocol: HTTPS, SOAP 1.1
- Media type: `text/xml; charset=utf-8`
- Supported auth: HTTP Basic only
- Not supported: NTLM/Kerberos/Bearer/OAuth

### Authentication and HTTP behavior

- Unauthenticated requests return `401 Unauthorized` with headers:
  - `WWW-Authenticate: Basic realm="EWS"`
  - `Connection: close`
  - Body is an empty SOAP envelope with a simple error string (IIS-like minimal body).
- Successful requests return `200 OK` with a SOAP envelope as content.

Example 401:

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Basic realm="EWS"
Connection: close
Content-Type: text/xml; charset=utf-8
```

### Namespaces used

- SOAP envelope: `http://schemas.xmlsoap.org/soap/envelope/` (prefix `s`)
- EWS messages: `http://schemas.microsoft.com/exchange/services/2006/messages` (prefix `m`)
- EWS types: `http://schemas.microsoft.com/exchange/services/2006/types` (prefix `t`)

### SOAP Envelope contract

- Every response includes a SOAP Header with `t:ServerVersionInfo`:

```xml
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Header>
    <t:ServerVersionInfo xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
      MajorVersion="15" MinorVersion="1" MajorBuildNumber="1531" MinorBuildNumber="3" Version="V2_23"/>
  </s:Header>
  <s:Body>
    <!-- operation response here -->
  </s:Body>
</s:Envelope>
```

### Folder identity model

- Distinguished folder IDs accepted in requests: `msgfolderroot`, `inbox`, `deleteditems`, `drafts`, `outbox`, `sentitems`, `junkemail`, `archive`, `contacts`, `calendar`.
- Server also accepts internal IDs via `t:FolderId Id="DF_*"` for all of the above. Mapping:
  - `DF_root` ↔ `msgfolderroot`
  - `DF_inbox`, `DF_deleteditems`, `DF_drafts`, `DF_outbox`, `DF_sentitems`, `DF_junkemail`, `DF_archive`, `DF_contacts`, `DF_calendar`
- Parent relationships:
  - All folders listed above are direct children of `DF_root` (except `DF_root`).
- Folder classes:
  - Mail: `IPF.Note`
  - Contacts: `IPF.Contact` (exposed as `t:ContactsFolder`)
  - Calendar: `IPF.Appointment` (exposed as `t:CalendarFolder`)
- Counts:
  - `msgfolderroot` advertises `ChildFolderCount=9`.
  - Other folders include `TotalCount`, `ChildFolderCount=0`, `UnreadCount=0`.
  - `inbox` and `sentitems` `TotalCount` are computed from the database per authenticated user.

### Item identity model

- Email rows in DB map to `t:ItemId Id="ITEM_<email_id>" ChangeKey="0"`.
- Parent folder in item responses uses `DF_*` ids (e.g., `DF_inbox`, `DF_sentitems`).

### Supported operations (implemented)

#### GetFolder

Purpose: return properties for requested folders.

Request (examples accept either `t:DistinguishedFolderId` or `t:FolderId Id="DF_*"`):

```xml
<m:GetFolder xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
  <m:FolderShape><t:BaseShape>IdOnly</t:BaseShape></m:FolderShape>
  <m:FolderIds>
    <t:DistinguishedFolderId Id="msgfolderroot"/>
    <t:DistinguishedFolderId Id="inbox"/>
  </m:FolderIds>
  <!-- or: <t:FolderId Id="DF_inbox"/> -->
</m:GetFolder>
```

Response (one `m:GetFolderResponseMessage` per requested folder, `ResponseClass="Success"`, `ResponseCode NoError`):

```xml
<m:GetFolderResponse xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages" xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
  <m:ResponseMessages>
    <m:GetFolderResponseMessage ResponseClass="Success">
      <m:ResponseCode>NoError</m:ResponseCode>
      <m:Folders>
        <t:Folder>
          <t:FolderId Id="DF_root" ChangeKey="0"/>
          <t:DisplayName>Root</t:DisplayName>
          <t:ChildFolderCount>9</t:ChildFolderCount>
        </t:Folder>
      </m:Folders>
    </m:GetFolderResponseMessage>
    <!-- additional response messages for other requested folders -->
  </m:ResponseMessages>
  </m:GetFolderResponse>
```

Notes:

- `contacts` returns `t:ContactsFolder`; `calendar` returns `t:CalendarFolder` including appropriate `FolderClass`.
- Mail folders are returned as `t:Folder` with `FolderClass IPF.Note` and `ParentFolderId Id="DF_root"`.

#### FindFolder (Traversal="Shallow")

Purpose: list default folders under `msgfolderroot`.

Behavior:

- Returns shallow listing of the default set with basic properties.

#### SyncFolderHierarchy

Purpose: synchronize folder tree.

Behavior:

- Stateful.
- First call (no `<SyncState>`) returns `Creates` for the 9 default folders, a server-generated `<SyncState>HIER_BASE_1</SyncState>`, and `<IncludesLastFolderInRange>true</IncludesLastFolderInRange>`.
- Subsequent calls that include the same `<SyncState>` echo the state and return `<m:Changes/>` empty.

Response order strictly follows Microsoft schema: `ResponseCode` → `SyncState` → `IncludesLastFolderInRange` → `Changes`.

#### SyncFolderItems

Purpose: synchronize items within a folder.

Behavior:

- Target folder is read from `<t:FolderId Id="..."/>`.
- Selection rules:
  - Inbox-like (default): items where `Email.recipient_id == user.id`.
  - Sent Items: items where `Email.sender_id == user.id`.
- Returns up to 10 recent items as `<t:Create><t:Message>...</t:Message></t:Create>` with `t:ItemId` and `t:ParentFolderId`.
- Sync state:
  - First call without state returns `ITEMS_BASE_1` and the creates.
  - Calls with a provided `<SyncState>` return the same state and empty changes.
- `<m:IncludesLastItemInRange>true</m:IncludesLastItemInRange>` is always set.

#### FindItem

Purpose: list items in a folder.

Behavior:

- If `ItemShape/BaseShape == IdOnly`: returns `t:Items` with `t:Message` containing `t:ItemId` only.
- Default shape returns minimal fields: `Subject`, `From`, `DateTimeReceived`, `ItemClass`, `IsRead`, `HasAttachments`, and `ParentFolderId`.
- Page view elements are accepted but currently not enforced (fixed upper bound of 10 items).

#### GetItem

Purpose: fetch message details.

Behavior:

- Filters by authenticated user and requested `ItemId`s.
- Returns, when requested via shape/properties, the following:
  - `Subject`, `From`, `ToRecipients`, `DateTimeReceived`, `ItemClass`, `Size`, `IsRead`, `ParentFolderId`.
  - `Body` (Text or HTML) mapped from DB `Email.body` / `Email.body_html`.
  - `MimeContent` (base64) mapped from DB `Email.mime_content` (already base64-encoded internally for ActiveSync compatibility).
  - `InternetMessageHeaders` (subset).

#### CreateItem (SendOnly, SaveOnly, SendAndSaveCopy)

Purpose: create and/or send messages.

Behavior:

- Parses `<t:MimeContent>` (base64) and extracts: subject, recipients, plain body, and HTML body (if multipart).
- `MessageDisposition` influences actions:
  - `SaveOnly`: stores a copy under `DF_sentitems` (DB row created with `sender_id=user.id`).
  - `SendOnly`: enqueues the message for external delivery and triggers processing.
  - `SendAndSaveCopy`: both of the above.
- If `<SavedItemFolderId>` absent, defaults to `DF_sentitems`.
- HTML forwarding: if HTML part is detected, the outbound queued body is HTML; a plain-text fallback is generated for SMTP multipart/alternative.
- Delivery pipeline:
  - Queued via `email_delivery.queue_email()` which writes to `queued_emails` table.
  - Immediately calls `email_delivery.process_queue()` to attempt delivery.
  - External SMTP constructed as multipart/alternative (UTF‑8). If body looks like HTML, both text/plain fallback and text/html are sent.

Logging for CreateItem (JSON lines in `logs/web/ews/ews.log`):

- `createitem_start` with `disposition` and `target_folder`.
- `createitem_parsed` (for SaveOnly path) with parsed subject and length.
- `createitem_saved_copy` with DB `ItemId`.
- `createitem_detected_html` with `has_html` boolean.
- `createitem_queued` with generated `Message-ID` and recipient.
- `createitem_queue_processed` after processing the queue.
- `createitem_queue_error` on failures.

#### ResolveNames / GetUserAvailability

- Implemented as minimal stubs sufficient for Thunderbird to proceed. Responses use `ResponseClass="Success"` and `ResponseCode NoError` with minimal, fixed content.

### Not implemented / limitations

- UpdateItem, DeleteItem: not implemented (may return Success stubs or NotImplemented in future).
- Attachments, extended properties beyond the set listed above are not implemented.
- Paging parameters are accepted but not strictly enforced; fixed limits are used (10 items).
- Only Basic authentication is supported.

### Database mapping summary

- Model: `Email`
  - `id` → `t:ItemId Id="ITEM_<id>"`
  - `recipient_id == user.id` → Inbox scope
  - `sender_id == user.id` → Sent Items scope
  - `subject`, `body` (plain), `body_html` (HTML), `mime_content` (base64), `mime_content_type`, `created_at`

### Logging

- File: `logs/web/ews/ews.log`
- Format: JSON per line with fields `{ ts, component: "ews", event, details }`.
- Typical events: `request`, `auth_challenge`, `auth_invalid`, `getfolder_response`, `finditem_response`, `syncfolderhierarchy_response`, `syncfolderitems_response`, `createitem_*`.

### Example requests

FindFolder under root:

```xml
<m:FindFolder xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
              xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
              Traversal="Shallow">
  <m:FolderShape><t:BaseShape>IdOnly</t:BaseShape></m:FolderShape>
  <m:IndexedPageFolderView MaxEntriesReturned="10" Offset="0" BasePoint="Beginning"/>
  <m:ParentFolderIds><t:DistinguishedFolderId Id="msgfolderroot"/></m:ParentFolderIds>
  </m:FindFolder>
```

FindItem (IdOnly) in Inbox:

```xml
<m:FindItem xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
            xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
            Traversal="Shallow">
  <m:ItemShape><t:BaseShape>IdOnly</t:BaseShape></m:ItemShape>
  <m:IndexedPageItemView MaxEntriesReturned="10" Offset="0" BasePoint="Beginning"/>
  <m:ParentFolderIds><t:DistinguishedFolderId Id="inbox"/></m:ParentFolderIds>
</m:FindItem>
```

GetItem with body and MIME content:

```xml
<m:GetItem xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
  <m:ItemShape>
    <t:BaseShape>IdOnly</t:BaseShape>
    <t:AdditionalProperties>
      <t:FieldURI FieldURI="item:MimeContent"/>
      <t:FieldURI FieldURI="item:Body"/>
      <t:FieldURI FieldURI="item:InternetMessageHeaders"/>
    </t:AdditionalProperties>
  </m:ItemShape>
  <m:ItemIds>
    <t:ItemId Id="ITEM_10"/>
  </m:ItemIds>
</m:GetItem>
```

CreateItem (SendAndSaveCopy) with encoded MIME:

```xml
<m:CreateItem xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
              xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
              MessageDisposition="SendAndSaveCopy">
  <m:SavedItemFolderId><t:FolderId Id="DF_sentitems"/></m:SavedItemFolderId>
  <m:Items>
    <t:Message>
      <t:MimeContent>BASE64_MIME_HERE</t:MimeContent>
    </t:Message>
  </m:Items>
</m:CreateItem>
```

### SMTP delivery notes

- Outbound delivery resolves MX via `dns.resolver` (`mx_lookup` service).
- The SMTP client sends multipart/alternative (UTF‑8). If HTML is detected, a plain fallback is generated.
- Delivery status and retry logic are recorded in the `queued_emails` table with statuses: `pending`, `processing`, `retry`, `sent`, `failed`.

### Operational tips

- Tail EWS logs: `tail -f logs/web/ews/ews.log`
- Common grep: `grep -E 'createitem_|SyncFolderItems|request' logs/web/ews/ews.log`
- If Thunderbird reports auth errors, verify the 401 challenge exists and Basic creds are correct.
