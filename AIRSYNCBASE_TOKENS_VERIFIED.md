# AirSyncBase Codepage (14 / 0x0E) Token Definitions

## Source: MS-ASWBXML Specification + Z-Push wbxmldefs.php

### Official Tokens (AirSyncBase)

Based on Microsoft MS-ASWBXML and Z-Push implementation:

```
Base Token | With Content | Element Name           | Our Implementation
-----------|--------------|-----------------------|-------------------
0x05       | 0x45         | Attachment            | N/A
0x06       | 0x46         | Attachments           | N/A
0x07       | 0x47         | ContentId             | N/A
0x08       | 0x48         | Body                  | ✅ 0x48 (CORRECT)
0x09       | 0x49         | Data                  | ✅ 0x49 (CORRECT)
0x0A       | 0x4A         | Type                  | ✅ 0x4A (CORRECT)
0x0B       | 0x4B         | EstimatedDataSize     | ✅ 0x4B (CORRECT)
0x0C       | 0x4C         | Truncated             | ❌ 0x0C (empty tag) - Should use content flag!
0x0D       | 0x4D         | ContentType           | N/A
0x0E       | 0x4E         | Preview               | N/A
0x0F       | 0x4F         | BodyPartPreference    | N/A
0x10       | 0x50         | BodyPart              | N/A
0x11       | 0x51         | Status                | N/A
0x12       | 0x52         | Add                   | N/A
0x13       | 0x53         | Delete                | N/A
0x14       | 0x54         | ClientId              | N/A
0x15       | 0x55         | Content               | N/A
0x16       | 0x56         | Location              | N/A
0x17       | 0x57         | Annotations           | N/A
0x18       | 0x58         | Street                | N/A
0x19       | 0x59         | City                  | N/A
0x1A       | 0x5A         | State                 | N/A
0x1B       | 0x5B         | Country               | N/A
0x1C       | 0x5C         | PostalCode            | N/A
0x1D       | 0x5D         | Latitude              | N/A
0x1E       | 0x5E         | Longitude             | N/A
0x1F       | 0x5F         | Accuracy              | N/A
0x20       | 0x60         | Altitude              | N/A
0x21       | 0x61         | AltitudeAccuracy      | N/A
0x22       | 0x62         | LocationUri           | N/A
0x23       | 0x63         | InstanceId            | N/A
```

### 🎯 **KEY FINDING: Truncated Tag Usage**

**Our Current Implementation:**
```python
# Line 317: Truncated EMPTY TAG (0x0C, no 0x40!)
if original_body_size > len(body_text):
    output.write(b'\x0C')  # ❌ Empty tag
```

**Z-Push/Grommunio-Sync:**
```php
// Truncated is sent as empty tag when no truncation
// But as tag with content when truncation indicator needed
if ($truncated) {
    self::_putTag(SYNC_AIRSYNCBASE_TRUNCATED, false, $truncated);
    // This writes 0x4C (with content) for value
}
```

**Microsoft Spec:**
> Truncated: A boolean indicating whether the body was truncated.
> Type: container (has content)

## 🐛 **BUG FOUND: Truncated Should Use 0x4C (with content flag)!**

We're sending:
```
0x0C  # ❌ Empty tag - WRONG!
```

Should be:
```
0x4C 03 30 00 01  # With content "0" (not truncated)
OR
0x4C 03 31 00 01  # With content "1" (truncated)
```

## ✅ **Correct Implementation**

```python
# Truncated (0x0C + 0x40 = 0x4C) - WITH CONTENT!
output.write(b'\x4C')  # Truncated with content
output.write(b'\x03')  # STR_I
if original_body_size > len(body_text):
    output.write(b'1')  # Truncated = true
else:
    output.write(b'0')  # Truncated = false
output.write(b'\x00')  # String terminator
output.write(b'\x01')  # END Truncated
```

## 📊 **Summary**

| Token             | Base | With Content | Status |
|-------------------|------|--------------|--------|
| Body              | 0x08 | 0x48         | ✅ CORRECT |
| Data              | 0x09 | 0x49         | ✅ CORRECT |
| Type              | 0x0A | 0x4A         | ✅ CORRECT |
| EstimatedDataSize | 0x0B | 0x4B         | ✅ CORRECT |
| Truncated         | 0x0C | 0x4C         | ❌ **WRONG!** Using 0x0C (empty) instead of 0x4C (with content) |

