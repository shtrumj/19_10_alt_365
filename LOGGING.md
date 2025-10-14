### ActiveSync Split Logging

Location: `logs/activesync/{YYYY-MM-DD}/`

Files:

- comm.log: high-level request/response events (wbxml_response, header_only_initial_batch, sync_initial_with_items)
- data.log: payload sizes and hex previews (wbxml_preview, body_data_write)
- state.log: SyncKey transitions, MoreAvailable, pending state commits
- errors.log: exceptions and spec violations during handling/building
- perf.log: timing metrics between parse → build → respond

Usage in code:

```python
from app.diagnostic_logger2 import aslog
aslog("comm", "wbxml_response", status_code=200, response_sync_key="1")
aslog("data", "wbxml_preview", preview_hex=wb[:64].hex(), length=len(wb))
aslog("state", "sync_key_update", old="0", new="1", has_more=True)
```

Environment flags (config.py):

- AS_LOG_SPLIT=1 to enable split logs (default)
- AS_REDACT=1 to redact PII (addresses, auth headers)
- AS_MAX_WINDOW_SIZE=25 to clamp WindowSize

Grep examples:

```bash
grep '"wbxml_response"' logs/activesync/$(date -u +%F)/comm.log | jq '.content_length'
grep '"header_only_initial_batch"' logs/activesync/$(date -u +%F)/comm.log
grep '"wbxml_preview"' logs/activesync/$(date -u +%F)/data.log | tail -1 | jq -r '.preview_hex'
```
