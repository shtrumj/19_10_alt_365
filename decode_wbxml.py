#!/usr/bin/env python3
"""Quick WBXML decoder to analyze our Sync response structure"""

import sys

# Use command line argument if provided
if len(sys.argv) > 1:
    hex_string = sys.argv[1]
else:
    hex_string = "03016a000000454e033100015c4f4b0332000152033100014e033100015003456d61696c000156474d03313a323600015d000254034677643a20596f757220726566756e642066726f6d20437572736f722023333230382d373332340001580373687472756d6a40676d61696c2e636f6d00015603796f6e6174616e4073687472756d2e636f6d00014f03323032352d31302d30395430363a34353a32332e3830355a0001530349504d2e4e6f74650001790336353030310001550331000100114a46033100014c0331383800014d033100014b032d2d2d2d2d2d2d2d2d2d20466f72776172646564206d657373616765202d2d2d2d2d2d2d2d2d0d0ad79ed790d7aa3a20437572736f72203c696e766f6963652b73746174656d656e74732b616363745f314c62354c7a4234545a577853494755407374726970652e636f6d3e0d0ae280aa446174653a20d799d795d79d20d792d7b32c20333020d791d7a1d7a4d798d7b3203230323520d7912d31313a3338e280ac0d0a5375626a6563743a20596f757220726566756e642066726f00014e03746578742f706c61696e3b20636861727365743d7574662d38000101560331000100000101474d03313a323500015d000254034677643a2044696420796f75206a75737420726573657420796f75722070617373776f72643f0001580373687472756d6a40676d61696c2e636f6d00015603796f6e6174616e4073687472756d2e636f6d00014f03323032352d31302d30385431393a35303a31332e3738315a0001530349504d2e4e6f74650001790336353030310001550331000100114a46033100014c0331383800014d033100014b032d2d2d2d2d2d2d2d2d2d20466f72776172646564206d657373616765202d2d2d2d2d2d2d2d2d0d0ad79ed790d7aa3a2046616365626f6f6b203c73656375726974794066616365626f6f6b6d61696c2e636f6d3e0d0ae280aa446174653a20d799d795d79d20d795d7b32c20323620d791d7a1d7a4d798d7b3203230323520d7912d373a3235e280ac0d0a5375626a6563743a2044696420796f75206a75737420726573657420796f75722070617373776f72643f0d0a546f3a205900014e03746578742f706c61696e3b20636861727365743d7574662d38000101560331000100000101474d03313a323400015d000254034677643a20d7a9d798d7a8d795d79d2057656220536974653a20d7a2d793d79bd795d7a0d79920d794d7aad790d79ed795d7aa20d797d793d7a9d795d7aa2028d7a4d7a8d7a1d795d79ed7aa290001580373687472756d6a40676d61696c2e636f6d00015603796f6e6174616e4073687472756d2e636f6d00014f03323032352d31302d30385431393a34343a32332e3032385a0001530349504d2e4e6f74650001790336353030310001550331000100114a46033100014c0332303100014d033100014b032d2d2d2d2d2d2d2d2d2d20466f72776172646564206d657373616765202d2d2d2d2d2d2d2d2d0d0ad79ed790d7aa3a204d79486572697461676520536d617274204d617463686573203c736d6172746d6174636832406d7968657269746167652e636f6d3e0d0ae280aa446174653a20d7a9d791d7aa2c20323720d791d7a1d7a4d798d7b3203230323520d7912d383a3234e280ac0d0ae280aa5375626a6563743a20d7a9d798d7a8d795d79d2057656220536974653a20d7a2d793d79bd795d7a0d79920d794d7aa00014e03746578742f706c61696e3b20636861727365743d7574662d380001015603310001000001010114010101"

# Token names by codepage
tokens_by_cp = {
    # AirSync codepage 0
    0: {
        0x00: "SWITCH_PAGE",
        0x01: "END",
        0x03: "STR_I",
        0x05: "Sync",
        0x45: "Sync+",
        0x0B: "SyncKey",
        0x4B: "SyncKey+",
        0x0D: "ServerId",
        0x4D: "ServerId+",
        0x0E: "Status",
        0x4E: "Status+",
        0x0F: "Collection",
        0x4F: "Collection+",
        0x10: "Class",
        0x50: "Class+",
        0x12: "CollectionId",
        0x52: "CollectionId+",
        0x14: "MoreAvailable",
        0x16: "Commands",
        0x56: "Commands+",
        0x1C: "Collections",
        0x5C: "Collections+",
        0x1D: "ApplicationData",
        0x5D: "ApplicationData+",
        0x07: "Add",
        0x47: "Add+",
    },
    # Email codepage 2
    2: {
        0x0F: "EM_DateReceived",
        0x4F: "EM_DateReceived+",
        0x13: "EM_MessageClass",
        0x53: "EM_MessageClass+",
        0x14: "EM_Subject",
        0x54: "EM_Subject+",
        0x15: "EM_Read",
        0x55: "EM_Read+",
        0x16: "EM_To",
        0x56: "EM_To+",
        0x18: "EM_From",
        0x58: "EM_From+",
        0x39: "EM_InternetCPID",
        0x79: "EM_InternetCPID+",
    },
    # AirSyncBase codepage 17
    17: {
        0x06: "ASB_Type",
        0x46: "ASB_Type+",
        0x0A: "ASB_Body",
        0x4A: "ASB_Body+",
        0x0B: "ASB_Data",
        0x4B: "ASB_Data+",
        0x0C: "ASB_EstimatedDataSize",
        0x4C: "ASB_EstimatedDataSize+",
        0x0D: "ASB_Truncated",
        0x4D: "ASB_Truncated+",
        0x0E: "ASB_ContentType",
        0x4E: "ASB_ContentType+",
        0x14: "ASB_Preview",
        0x54: "ASB_Preview+",
        0x16: "ASB_NativeBodyType",
        0x56: "ASB_NativeBodyType+",
    },
}


def get_token_name(cp, token):
    """Get token name for given codepage and token value"""
    if cp in tokens_by_cp and token in tokens_by_cp[cp]:
        return tokens_by_cp[cp][token]
    return f"UNKNOWN_0x{token:02X}"


def decode_wbxml(hex_str):
    """Decode WBXML hex string to readable structure"""
    data = bytes.fromhex(hex_str)
    pos = 0
    indent = 0

    # Parse header
    if len(data) < 4:
        print("Invalid WBXML: too short")
        return

    version = data[0]
    public_id = data[1]
    charset = data[2]
    string_table_len = data[3]

    print(
        f"Header: {version:02x}{public_id:02x}{charset:02x}{string_table_len:02x} (WBXML {version}, public ID, charset {charset}, string table = {string_table_len})"
    )

    pos = 4

    # Skip string table if present
    if string_table_len > 0:
        pos += string_table_len

    current_cp = 0  # Default to AirSync codepage

    while pos < len(data):
        byte = data[pos]
        pos += 1

        if byte == 0x00:  # SWITCH_PAGE
            if pos < len(data):
                current_cp = data[pos]
                pos += 1
                print(f"[SWITCH to page {current_cp}]")
                continue
        elif byte == 0x01:  # END
            indent -= 1
            print("  " * indent + "</END>")
            continue
        elif byte == 0x03:  # STR_I
            # Read string until null terminator
            start = pos
            while pos < len(data) and data[pos] != 0x00:
                pos += 1
            if pos < len(data):
                pos += 1  # skip null terminator
            try:
                string_val = data[start : pos - 1].decode("utf-8")
                print("  " * indent + f'"{string_val}"')
            except:
                print("  " * indent + f"<invalid_utf8>")
            continue

        # Check if it's a start tag with content
        if byte & 0x40:  # WITH_CONTENT bit set
            token = byte & 0x3F
            token_name = get_token_name(current_cp, byte)
            print("  " * indent + f"<{token_name}>")
            indent += 1
        else:
            token = byte
            token_name = get_token_name(current_cp, byte)
            print("  " * indent + f"<{token_name}>")


if __name__ == "__main__":
    print("WBXML Structure Analysis:")
    print("=" * 60)
    decode_wbxml(hex_string)
