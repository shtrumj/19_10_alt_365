#!/usr/bin/env python3
"""
Comprehensive WBXML Sync Response Analyzer
Compares our implementation against MS-ASCMD specification requirements
"""

# Token definitions from MS-ASCMD specification
CP_AIRSYNC = 0
CP_EMAIL = 2
CP_AIRSYNCBASE = 17

# AirSync tokens (CP 0)
AIRSYNC_TOKENS = {
    0x05: "Sync",
    0x06: "Responses",
    0x07: "Add",
    0x08: "Change",
    0x09: "Delete",
    0x0B: "SyncKey",
    0x0C: "ClientId",
    0x0D: "ServerId",
    0x0E: "Status",
    0x0F: "Collection",
    0x10: "Class",
    0x12: "CollectionId",
    0x14: "MoreAvailable",
    0x15: "WindowSize",
    0x16: "Commands",
    0x1C: "Collections",
    0x1D: "ApplicationData",
}

# Email tokens (CP 2)
EMAIL_TOKENS = {
    0x0F: "DateReceived",
    0x13: "MessageClass",
    0x14: "Subject",
    0x15: "Read",
    0x16: "To",
    0x18: "From",
    0x39: "InternetCPID",
}

# AirSyncBase tokens (CP 17)
AIRSYNCBASE_TOKENS = {
    0x06: "Type",
    0x0A: "Body",
    0x0B: "Data",
    0x0C: "EstimatedDataSize",
    0x0D: "Truncated",
    0x0E: "ContentType",
    0x16: "NativeBodyType",
}

CODEPAGES = {
    0: ("AirSync", AIRSYNC_TOKENS),
    2: ("Email", EMAIL_TOKENS),
    17: ("AirSyncBase", AIRSYNCBASE_TOKENS),
}


def decode_wbxml_detailed(hex_string: str):
    """Decode WBXML and show detailed structure with codepage tracking"""
    data = bytes.fromhex(hex_string)

    print("=" * 80)
    print("WBXML STRUCTURE ANALYSIS (MS-ASCMD Compliance Check)")
    print("=" * 80)

    # Header
    print(f"\n[HEADER] {data[:4].hex()}")
    print(f"  Version: {data[0]:02x} (WBXML 1.{data[0]})")
    print(f"  Public ID: {data[1]:02x}")
    print(f"  Charset: {data[2]:02x} (UTF-8)")
    print(f"  String Table Length: {data[3]:02x}")

    i = 4
    indent = 0
    current_page = 0
    element_stack = []

    print("\n[BODY]")

    while i < len(data):
        byte = data[i]

        if byte == 0x00:  # SWITCH_PAGE
            i += 1
            current_page = data[i]
            page_name = CODEPAGES.get(current_page, ("Unknown", {}))[0]
            print(f"{'  ' * indent}[SWITCH_PAGE → CP{current_page}: {page_name}]")
            i += 1

        elif byte == 0x01:  # END
            if element_stack:
                closing_tag = element_stack.pop()
                indent -= 1
                print(f"{'  ' * indent}</{closing_tag}>")
            else:
                print(f"{'  ' * indent}[END - NO MATCHING OPEN TAG!] ⚠️")
            i += 1

        elif byte == 0x03:  # STR_I
            i += 1
            start = i
            while i < len(data) and data[i] != 0x00:
                i += 1
            string_val = data[start:i].decode("utf-8", errors="replace")
            # Truncate long strings for readability
            if len(string_val) > 60:
                string_val = string_val[:60] + "..."
            print(f"{'  ' * indent}  \"{string_val}\"")
            i += 1  # skip null terminator

        elif byte == 0xC3:  # OPAQUE
            i += 1
            # Read multi-byte length
            length = 0
            while True:
                b = data[i]
                length = (length << 7) | (b & 0x7F)
                i += 1
                if (b & 0x80) == 0:
                    break
            print(f"{'  ' * indent}  [OPAQUE {length} bytes]")
            i += length

        else:
            # Token
            has_content = (byte & 0x40) != 0
            token_code = byte & 0x3F

            page_name, tokens = CODEPAGES.get(current_page, ("Unknown", {}))
            token_name = tokens.get(token_code, f"Unknown_0x{token_code:02X}")

            if has_content:
                print(
                    f"{'  ' * indent}<{token_name}> [CP{current_page}:{page_name}, token=0x{byte:02X}]"
                )
                element_stack.append(token_name)
                indent += 1
            else:
                print(
                    f"{'  ' * indent}<{token_name}/> [CP{current_page}:{page_name}, token=0x{byte:02X}, EMPTY]"
                )
            i += 1

    print("\n" + "=" * 80)
    print("MS-ASCMD COMPLIANCE CHECKS:")
    print("=" * 80)

    # Analyze structure
    hex_lower = hex_string.lower()

    checks = []

    # Check 1: Top-level Status
    if "454e0331" in hex_lower[:100]:  # 45=Sync+, 4e=Status+, 03=STR_I, 31=1
        checks.append(("✅", "Top-level <Status>1</Status> present"))
    else:
        checks.append(("❌", "Top-level <Status>1</Status> MISSING"))

    # Check 2: Collection-level Status
    if "52033100014e03310001" in hex_lower:  # CollectionId + Status
        checks.append(("✅", "Collection-level <Status>1</Status> present"))
    else:
        checks.append(("❌", "Collection-level <Status>1</Status> MISSING"))

    # Check 3: Class element
    if "5003456d61696c" in hex_lower:  # 50=Class+, 03=STR_I, "Email"
        checks.append(("✅", "<Class>Email</Class> present"))
    else:
        checks.append(("❌", "<Class>Email</Class> MISSING"))

    # Check 4: Commands section
    if "56" in hex_lower:  # 56=Commands+
        checks.append(("✅", "<Commands> section present"))
    else:
        checks.append(("❌", "<Commands> section MISSING"))

    # Check 5: MoreAvailable placement (should be after Commands close, before Collection close)
    # Pattern: ...01 (Commands END) ... 14 (MoreAvailable) ... 01 01 01 (Collection/Collections/Sync END)
    if "14" in hex_lower:
        # Find position of 0x14
        pos_14 = hex_lower.index("14")
        context_before = hex_lower[max(0, pos_14 - 20) : pos_14]
        context_after = hex_lower[pos_14 : min(len(hex_lower), pos_14 + 20)]

        # Check if there's a codepage switch before MoreAvailable
        if "0000" in context_before[-10:]:  # SWITCH_PAGE to CP0
            checks.append(("✅", "<MoreAvailable/> on correct codepage (AirSync)"))
        else:
            checks.append(("⚠️", "<MoreAvailable/> codepage may be incorrect"))

        # Check if it's after Commands
        if "01" in context_before[-4:]:  # END tag before MoreAvailable
            checks.append(("✅", "<MoreAvailable/> after <Commands>"))
        else:
            checks.append(("⚠️", "<MoreAvailable/> position unclear"))
    else:
        checks.append(("ℹ️", "<MoreAvailable/> not present (was removed in experiment)"))

    # Check 6: Body structure (AirSyncBase)
    if "114a" in hex_lower:  # 11=SWITCH to CP17, 4a=Body+
        checks.append(("✅", "AirSyncBase <Body> present"))
    else:
        checks.append(("❌", "AirSyncBase <Body> MISSING"))

    # Check 7: NativeBodyType
    if "1156" in hex_lower:  # 11=SWITCH to CP17, 56=NativeBodyType+
        checks.append(("✅", "<NativeBodyType> present"))
    else:
        checks.append(("⚠️", "<NativeBodyType> might be missing"))

    for status, msg in checks:
        print(f"  {status} {msg}")

    print("\n" + "=" * 80)
    print("ELEMENT ORDER VALIDATION (MS-ASCMD § 2.2.3.166.2):")
    print("=" * 80)
    print("  Required order within <Collection>:")
    print("    1. <SyncKey>")
    print("    2. <CollectionId>")
    print("    3. <Status>")
    print("    4. <Class>")
    print("    5. <Commands> (if items to send)")
    print("    6. <MoreAvailable/> (if more items)")
    print("    7. <Responses> (if confirmations)")
    print("=" * 80)


if __name__ == "__main__":
    # Analyze the most recent WBXML response
    # This is from logs: the 1303-byte response Outlook rejected
    wbxml_hex = "03016a000000454e033100015c4f4b0332000152033100014e033100015003456d61696c000156474d03313a323600015d000254034677643a20596f757220726566756e642066726f6d20437572736f722023333230382d373332340001580373687472756d6a40676d61696c2e636f6d00015603796f6e6174616e4073687472756d2e636f6d00014f03323032352d31302d30395430363a34353a32332e3830355a0001530349504d2e4e6f74650001790336353030310001550331000100114a46033100014c0331383800014d033100014b032d2d2d2d2d2d2d2d2d2d20466f72776172646564206d657373616765202d2d2d2d2d2d2d2d2d0d0ad79ed790d7aa3a20437572736f72203c696e766f6963652b73746174656d656e74732b616363745f314c62354c7a4234545a577853494755407374726970652e636f6d3e0d0ae280aa446174653a20d799d795d79d20d792d7b32c20333020d791d7a1d7a4d798d7b3203230323520d7912d31313a3338e280ac0d0a5375626a6563743a20596f757220726566756e642066726f00014e03746578742f706c61696e3b20636861727365743d7574662d38000101560331000100000101474d03313a323500015d000254034677643a2044696420796f75206a75737420726573657420796f75722070617373776f72643f0001580373687472756d6a40676d61696c2e636f6d00015603796f6e6174616e4073687472756d2e636f6d00014f03323032352d31302d30385431393a35303a31332e3738315a0001530349504d2e4e6f74650001790336353030310001550331000100114a46033100014c0331383800014d033100014b032d2d2d2d2d2d2d2d2d2d20466f72776172646564206d657373616765202d2d2d2d2d2d2d2d2d0d0ad79ed790d7aa3a2046616365626f6f6b203c73656375726974794066616365626f6f6b6d61696c2e636f6d3e0d0ae280aa446174653a20d799d795d79d20d795d7b32c20323620d791d7a1d7a4d798d7b3203230323520d7912d373a3235e280ac0d0a5375626a6563743a2044696420796f75206a75737420726573657420796f75722070617373776f72643f0d0a546f3a205900014e03746578742f706c61696e3b20636861727365743d7574662d38000101560331000100000101474d03313a323400015d000254034677643a20d7a9d798d7a8d795d79d2057656220536974653a20d7a2d793d79bd795d7a0d79920d794d7aad790d79ed795d7aa20d797d793d7a9d795d7aa2028d7a4d7a8d7a1d795d79ed7aa290001580373687472756d6a40676d61696c2e636f6d00015603796f6e6174616e4073687472756d2e636f6d00014f03323032352d31302d30385431393a34343a32332e3032385a0001530349504d2e4e6f74650001790336353030310001550331000100114a46033100014c0332303100014d033100014b032d2d2d2d2d2d2d2d2d2d20466f72776172646564206d657373616765202d2d2d2d2d2d2d2d2d0d0ad79ed790d7aa3a204d79486572697461676520536d617274204d617463686573203c736d6172746d6174636832406d7968657269746167652e636f6d3e0d0ae280aa446174653a20d7a9d791d7aa2c20323720d791d7a1d7a4d798d7b3203230323520d7912d383a3234e280ac0d0ae280aa5375626a6563743a20d7a9d798d7a8d795d79d2057656220536974653a20d7a2d793d79bd795d7a0d79920d794d7aa00014e03746578742f706c61696e3b20636861727365743d7574662d380001015603310001000001010114010101"

    decode_wbxml_detailed(wbxml_hex)
