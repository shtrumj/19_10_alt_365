# WBXML Builder Comparison: Our Implementation vs grommunio-sync

## Reference

- **grommunio-sync**: https://github.com/grommunio/grommunio-sync/blob/master/lib/wbxml/wbxmldefs.php
- **Microsoft ActiveSync Protocol**: MS-ASAIRS (AirSyncBase), MS-ASCMD (Commands)

## Token Definitions Comparison

### Code Pages

| Token            | Our Value | Standard | Status     |
| ---------------- | --------- | -------- | ---------- |
| `CP_AIRSYNC`     | 0         | 0        | ✅ Correct |
| `CP_EMAIL`       | 2         | 2        | ✅ Correct |
| `CP_AIRSYNCBASE` | 17        | 17       | ✅ Correct |
| `CP_SETTINGS`    | 18        | 18       | ✅ Correct |

### AirSync (Codepage 0) Tokens

| Token                | Our Value | Standard | Status     |
| -------------------- | --------- | -------- | ---------- |
| `AS_Sync`            | 0x05      | 0x05     | ✅ Correct |
| `AS_Add`             | 0x07      | 0x07     | ✅ Correct |
| `AS_SyncKey`         | 0x0B      | 0x0B     | ✅ Correct |
| `AS_ServerId`        | 0x0D      | 0x0D     | ✅ Correct |
| `AS_Status`          | 0x0E      | 0x0E     | ✅ Correct |
| `AS_Collection`      | 0x0F      | 0x0F     | ✅ Correct |
| `AS_WindowSize`      | 0x15      | 0x15     | ✅ Correct |
| `AS_Commands`        | 0x16      | 0x16     | ✅ Correct |
| `AS_Collections`     | 0x1C      | 0x1C     | ✅ Correct |
| `AS_ApplicationData` | 0x1D      | 0x1D     | ✅ Correct |

### Email (Codepage 2) Tokens

| Token             | Our Value | Standard | Status     |
| ----------------- | --------- | -------- | ---------- |
| `EM_Subject`      | 0x14      | 0x14     | ✅ Correct |
| `EM_From`         | 0x18      | 0x18     | ✅ Correct |
| `EM_To`           | 0x16      | 0x16     | ✅ Correct |
| `EM_DateReceived` | 0x0F      | 0x0F     | ✅ Correct |
| `EM_MessageClass` | 0x13      | 0x13     | ✅ Correct |
| `EM_Read`         | 0x15      | 0x15     | ✅ Correct |
| `EM_InternetCPID` | 0x39      | 0x39     | ✅ Correct |

### AirSyncBase (Codepage 17) Tokens

| Token                   | Our Value | Standard | Status     |
| ----------------------- | --------- | -------- | ---------- |
| `ASB_Type`              | 0x06      | 0x06     | ✅ Correct |
| `ASB_Body`              | 0x0A      | 0x0A     | ✅ Correct |
| `ASB_Data`              | 0x0B      | 0x0B     | ✅ Correct |
| `ASB_EstimatedDataSize` | 0x0C      | 0x0C     | ✅ Correct |
| `ASB_Truncated`         | 0x0D      | 0x0D     | ✅ Correct |
| `ASB_ContentType`       | 0x0E      | 0x0E     | ✅ Correct |
| `ASB_Preview`           | 0x14      | 0x14     | ✅ Correct |
| `ASB_NativeBodyType`    | 0x16      | 0x16     | ✅ Correct |

## WBXML Structure Comparison

### Our Current Structure

```xml
<ApplicationData>                    <!-- CP 0 (AirSync) -->
  <Subject>...</Subject>             <!-- CP 2 (Email) -->
  <From>...</From>
  <To>...</To>
  <DateReceived>...</DateReceived>
  <MessageClass>IPM.Note</MessageClass>
  <InternetCPID>65001</InternetCPID>
  <Read>1</Read>

  <Body>                             <!-- CP 17 (AirSyncBase) -->
    <Type>2</Type>
    <EstimatedDataSize>13456</EstimatedDataSize>
    <Truncated>0</Truncated>
    <Data><!DOCTYPE html>...</Data>
    <Preview>First 255 chars...</Preview>
    <ContentType>text/html; charset=utf-8</ContentType>
  </Body>

  <NativeBodyType>2</NativeBodyType> <!-- CP 17 (AirSyncBase), OUTSIDE Body -->
</ApplicationData>
```

### Expected Structure (per MS-ASAIRS)

```xml
<ApplicationData>
  <!-- Email properties (CP 2) -->
  <Subject>...</Subject>
  <From>...</From>
  <To>...</To>
  <DateReceived>...</DateReceived>
  <MessageClass>IPM.Note</MessageClass>
  <InternetCPID>65001</InternetCPID>
  <Read>1</Read>

  <!-- Body (CP 17 - AirSyncBase) -->
  <Body>
    <Type>2</Type>
    <EstimatedDataSize>13456</EstimatedDataSize>
    <Truncated>0</Truncated>
    <Data><!DOCTYPE html>...</Data>
    <Preview>First 255 chars...</Preview>
  </Body>

  <!-- NativeBodyType OUTSIDE Body element -->
  <NativeBodyType>2</NativeBodyType>
</ApplicationData>
```

## Key Differences & Issues

### ✅ Correct Implementation

1. **Token values**: All token hex values match the Microsoft specification
2. **Element order within Body**: Type → EstimatedDataSize → Truncated → Data → Preview
3. **NativeBodyType placement**: Correctly placed OUTSIDE the Body element
4. **InternetCPID**: Correctly set to 65001 (UTF-8)
5. **MessageClass**: Correctly set to "IPM.Note"
6. **HTML Wrapping**: Now wrapping HTML fragments in complete documents

### ⚠️ Potential Issues

#### 1. ContentType Element Placement

**Current**: ContentType is inside `<Body>` element (line 1280-1284)
**Issue**: According to MS-ASAIRS spec, ContentType should only be used for attachments, not for the main body
**Recommendation**: Remove ContentType from inside Body element, or verify iOS compatibility

#### 2. HTML Document Wrapping

**Current**: Wrapping all HTML Type 2 content in complete HTML documents
**Verification Needed**: Ensure the wrapped HTML is well-formed and doesn't exceed size limits

#### 3. Codepage Switching

**Current**: Switching between CP 0 (AirSync), CP 2 (Email), CP 17 (AirSyncBase)
**Status**: Appears correct, but needs verification in logs

## Recommendations

### 1. Remove ContentType from Body Element (if causing issues)

```python
# BEFORE (lines 1280-1284):
content_type = body_payload.get("content_type")
if content_type:
    w.start(ASB_ContentType)
    w.write_str(content_type)
    w.end()

# AFTER (remove or comment out):
# ContentType should not be in Body element per MS-ASAIRS
```

### 2. Verify HTML Wrapping is Not Too Large

- Check if wrapped HTML exceeds iOS limits
- Consider stripping unnecessary whitespace from HTML wrapper
- Log actual size of wrapped content

### 3. Test with Minimal HTML First

Try sending simple HTML without the wrapper to verify if wrapping is the issue:

```html
<html>
  <body>
    Test
  </body>
</html>
```

### 4. Verify Codepage Switches in Binary Output

- Check WBXML hex output to ensure codepage switches (0x00) are correct
- Verify no missing END tags (0x01)

## grommunio-sync Implementation Notes

Based on the [grommunio-sync wbxmldefs.php](https://github.com/grommunio/grommunio-sync/blob/master/lib/wbxml/wbxmldefs.php):

- Uses identical token definitions
- Follows Microsoft ActiveSync Protocol specification
- Does NOT wrap HTML in complete documents by default
- Uses ContentType sparingly, primarily for attachments

## Conclusion

Our token definitions and WBXML structure are **correct** according to the Microsoft ActiveSync specification. The issue with HTML not rendering is likely due to:

1. ❌ **Adding ContentType inside Body element** - Should be removed
2. ❓ **HTML document wrapping** - May be incompatible with iOS expectations
3. ❓ **HTML size** - Wrapped HTML may exceed limits

### Next Steps

1. Remove ContentType from Body element
2. Test with UNWRAPPED HTML fragments (as grommunio-sync does)
3. Check logs for actual WBXML output
4. Verify iOS is receiving and parsing the WBXML correctly
