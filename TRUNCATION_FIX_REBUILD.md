# ActiveSync Truncation Fix - Docker Rebuild - October 10, 2025

## Issue

After implementing the 32KB minimum truncation fix for ActiveSync body downloads, the logs showed that the fix was not being applied in the running Docker container:

```json
{"event": "sync_body_pref_selected", "effective_truncation": 500}
{"event": "body_payload_prep_start", "truncation_size_param": 500}
{"event": "body_data_final", "data_length": 376, "truncated": "1"}
```

**Problem**: Email bodies were still being truncated to 500 bytes instead of the intended 32KB minimum.

## Root Cause

The Docker container was running with **cached/old code** that didn't include the truncation strategy fixes. Simply restarting the container (`docker-compose restart`) doesn't rebuild the image with new code changes.

## Solution Applied

### 1. Verified Strategy Code

Checked that the strategy files have the correct fix:

```python
# activesync/strategies/ios_strategy.py (and android, outlook)
def get_truncation_strategy(self, body_type: int, truncation_size: Optional[int], is_initial_sync: bool) -> Optional[int]:
    if body_type == 4:  # MIME
        return min(truncation_size or 512000, 512000)
    else:  # Type 1 or 2 (plain text or HTML)
        MIN_TEXT_TRUNCATION = 32768  # 32KB
        if truncation_size is None:
            return None  # Unlimited
        # CRITICAL: Enforce minimum
        return max(truncation_size, MIN_TEXT_TRUNCATION)  # ✅ Returns 32768 when client sends 500
```

### 2. Rebuilt Docker Image

```bash
docker-compose build email-system
```

This command:

- Reads the Dockerfile
- Copies ALL current source code into the image
- Installs dependencies
- Creates a fresh image with the latest code

### 3. Cleared ActiveSync Log

```bash
echo "" > logs/activesync/activesync.log
```

Cleared the log to get fresh data for analysis without old entries.

### 4. Started New Container

```bash
docker-compose up -d email-system
```

This recreated the container from the newly built image with the truncation fix.

## Expected Behavior After Fix

### Before (Old Code)

```json
{
  "event": "sync_body_pref_selected",
  "body_preferences": [{"type": 1, "truncation_size": 500}],
  "effective_truncation": 500  // ❌ BAD: Using client's tiny request
}
{
  "event": "body_data_final",
  "data_length": 376,  // ❌ Only ~400 bytes sent
  "truncated": "1"
}
```

### After (New Code)

```json
{
  "event": "sync_body_pref_selected",
  "body_preferences": [{"type": 1, "truncation_size": 500}],
  "effective_truncation": 32768  // ✅ GOOD: Enforcing 32KB minimum
}
{
  "event": "body_data_final",
  "data_length": 32768,  // ✅ Full 32KB sent (or less if email is smaller)
  "truncated": "0"
}
```

## Testing Instructions

### 1. Trigger a Sync from Client

From iPhone/Outlook, pull to refresh your mailbox.

### 2. Check New Log Entries

```bash
tail -f logs/activesync/activesync.log | grep effective_truncation
```

**Expected**: You should see `"effective_truncation": 32768` instead of `500`.

### 3. Verify Full Body Downloads

```bash
grep "body_data_final" logs/activesync/activesync.log | tail -5
```

**Expected**: `data_length` should be much larger (up to 32768) instead of ~300-500 bytes.

### 4. Check Email Display on Client

Open an email that was previously showing truncated content. It should now display the full body (up to 32KB).

## Docker Best Practices

### When to Use `docker-compose restart`

- Configuration changes (environment variables)
- Database schema updates
- Log rotation
- Memory/process issues

### When to Use `docker-compose build`

- **Code changes** (Python files, templates, etc.)
- Dependency updates (requirements.txt)
- Dockerfile modifications
- New files added to the project

### Full Rebuild Workflow

```bash
# 1. Build new image with latest code
docker-compose build email-system

# 2. Stop and remove old container
docker-compose down

# 3. Start new container from rebuilt image
docker-compose up -d

# 4. Verify it's running
docker-compose ps

# 5. Check logs
docker-compose logs -f email-system
```

## Files Modified (Previous Session)

These files were already updated with the truncation fix, but needed Docker rebuild:

- `activesync/strategies/ios_strategy.py` - Added 32KB minimum
- `activesync/strategies/android_strategy.py` - Added 32KB minimum
- `activesync/strategies/outlook_strategy.py` - Added 32KB minimum

## Verification Checklist

After rebuild, verify:

- [ ] Container rebuilt successfully
- [ ] Container is running (status: healthy)
- [ ] Log is cleared and ready for fresh data
- [ ] New sync shows `effective_truncation: 32768`
- [ ] Body data length is larger (not truncated to 500)
- [ ] Emails display properly on client

## Additional Notes

### Why Simple Restart Didn't Work

`docker-compose restart email-system` only:

- Stops the running container
- Starts it again with the **same image**

It does NOT:

- Rebuild the image
- Copy new code
- Update dependencies

### Verifying Code in Container

To verify what code is actually running in the container:

```bash
docker-compose exec email-system cat activesync/strategies/ios_strategy.py | grep -A 10 "MIN_TEXT_TRUNCATION"
```

This shows the actual code inside the container, not your local files.

## Status

✅ **Docker image rebuilt with truncation fix**
✅ **Container recreated and started**
✅ **Log cleared for fresh analysis**
✅ **Ready for client testing**

## Next Steps

1. **Sync from client** (iPhone/Outlook) - Pull to refresh
2. **Monitor logs** - Watch for `effective_truncation: 32768`
3. **Verify email bodies** - Check that full content displays
4. **Report results** - Confirm fix is working as expected

---

**Rebuild Date**: October 10, 2025  
**Issue**: Truncation fix not applied (old code in container)  
**Solution**: Full Docker rebuild with `docker-compose build`  
**Status**: Ready for testing
