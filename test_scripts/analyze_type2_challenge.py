#!/usr/bin/env python3
"""
Analyze NTLM Type2 challenge to identify Outlook compatibility issues
"""

import requests
import base64
import struct
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def analyze_type2_challenge():
    """Analyze the Type2 challenge in detail"""
    
    print("=== NTLM Type2 Challenge Analysis ===")
    
    # Get a Type2 challenge
    session = requests.Session()
    type1_token = "TlRMTVNTUAABAAAAB4IIAAAAAAAAAAAAAAAAAAAAAAA="
    headers = {
        "Authorization": f"NTLM {type1_token}",
        "Content-Type": "application/mapi-http"
    }
    
    response = session.post("https://owa.shtrum.com/mapi/emsmdb", 
                          headers=headers, data="", verify=False)
    
    if response.status_code != 401:
        print(f"❌ Expected 401, got {response.status_code}")
        return
    
    auth_header = response.headers.get('WWW-Authenticate', '')
    if not auth_header.startswith('NTLM '):
        print("❌ No NTLM challenge received")
        return
    
    type2_token = auth_header.split(' ', 1)[1]
    print(f"Type2 token: {type2_token}")
    print(f"Type2 token length: {len(type2_token)}")
    
    try:
        type2_raw = base64.b64decode(type2_token)
        print(f"Type2 raw length: {len(type2_raw)}")
        
        # Parse NTLM Type2 structure
        if len(type2_raw) < 48:
            print("❌ Type2 too short")
            return
        
        # Signature (8 bytes)
        signature = type2_raw[0:8]
        print(f"Signature: {signature}")
        if signature != b"NTLMSSP\x00":
            print("❌ Invalid NTLM signature")
        else:
            print("✅ Valid NTLM signature")
        
        # Message type (4 bytes)
        msg_type = struct.unpack('<I', type2_raw[8:12])[0]
        print(f"Message type: {msg_type}")
        if msg_type == 2:
            print("✅ Correct message type")
        else:
            print("❌ Wrong message type")
        
        # Target name security buffer (8 bytes)
        target_name_len = struct.unpack('<H', type2_raw[12:14])[0]
        target_name_max_len = struct.unpack('<H', type2_raw[14:16])[0]
        target_name_offset = struct.unpack('<I', type2_raw[16:20])[0]
        print(f"Target name: len={target_name_len}, max_len={target_name_max_len}, offset={target_name_offset}")
        
        # Negotiate flags (4 bytes)
        flags = struct.unpack('<I', type2_raw[20:24])[0]
        print(f"Negotiate flags: 0x{flags:08x}")
        
        # Check important flags
        flag_checks = [
            (0x00000001, "UNICODE", "Unicode strings supported"),
            (0x00000002, "OEM", "OEM strings supported"),
            (0x00000200, "SIGN", "Message signing required"),
            (0x00080000, "NTLM2_KEY", "NTLM2 session key"),
            (0x00010000, "TargetTypeServer", "Target is server"),
            (0x00020000, "NTLM", "NTLM authentication"),
            (0x00004000, "Target Info", "Target info present"),
            (0x00000004, "Request Target", "Request target name"),
            (0x00001000, "Negotiate Target", "Negotiate target"),
            (0x02000000, "Negotiate Version", "Version negotiation"),
            (0x20000000, "128-bit", "128-bit encryption"),
            (0x80000000, "56-bit", "56-bit encryption")
        ]
        
        for flag, name, description in flag_checks:
            if flags & flag:
                print(f"  ✅ {name}: {description}")
            else:
                print(f"  ❌ {name}: {description}")
        
        # Server challenge (8 bytes)
        challenge = type2_raw[24:32]
        print(f"Server challenge: {challenge.hex()}")
        
        # Context (8 bytes)
        context = type2_raw[32:40]
        print(f"Context: {context.hex()}")
        
        # Target info security buffer (8 bytes)
        if len(type2_raw) >= 48:
            target_info_len = struct.unpack('<H', type2_raw[40:42])[0]
            target_info_max_len = struct.unpack('<H', type2_raw[42:44])[0]
            target_info_offset = struct.unpack('<I', type2_raw[44:48])[0]
            print(f"Target info: len={target_info_len}, max_len={target_info_max_len}, offset={target_info_offset}")
            
            # Extract target info
            if target_info_offset < len(type2_raw) and target_info_len > 0:
                target_info_raw = type2_raw[target_info_offset:target_info_offset + target_info_len]
                print(f"Target info raw: {target_info_raw.hex()}")
                
                # Parse AV pairs
                pos = 0
                while pos < len(target_info_raw) - 4:
                    av_id = struct.unpack('<H', target_info_raw[pos:pos+2])[0]
                    av_len = struct.unpack('<H', target_info_raw[pos+2:pos+4])[0]
                    
                    if av_id == 0:  # EOL
                        print("  ✅ AV pair EOL found")
                        break
                    elif av_id == 1:  # NetBIOS computer name
                        av_value = target_info_raw[pos+4:pos+4+av_len]
                        print(f"  ✅ NetBIOS computer: {av_value.decode('utf-16le', errors='ignore')}")
                    elif av_id == 2:  # NetBIOS domain name
                        av_value = target_info_raw[pos+4:pos+4+av_len]
                        print(f"  ✅ NetBIOS domain: {av_value.decode('utf-16le', errors='ignore')}")
                    elif av_id == 3:  # DNS computer name
                        av_value = target_info_raw[pos+4:pos+4+av_len]
                        print(f"  ✅ DNS computer: {av_value.decode('utf-16le', errors='ignore')}")
                    elif av_id == 4:  # DNS domain name
                        av_value = target_info_raw[pos+4:pos+4+av_len]
                        print(f"  ✅ DNS domain: {av_value.decode('utf-16le', errors='ignore')}")
                    elif av_id == 7:  # Timestamp
                        av_value = target_info_raw[pos+4:pos+4+av_len]
                        print(f"  ✅ Timestamp: {av_value.hex()}")
                    else:
                        print(f"  ? AV pair {av_id}: {av_value.hex() if av_len > 0 else 'empty'}")
                    
                    pos += 4 + av_len
        
        # Version (8 bytes) - at the end
        if len(type2_raw) >= 8:
            version = type2_raw[-8:]
            print(f"Version: {version.hex()}")
            
            # Parse version
            major = version[0]
            minor = version[1]
            build = struct.unpack('<H', version[2:4])[0]
            print(f"  Version: {major}.{minor}.{build}")
        
        # Check for potential issues
        print("\n=== Potential Issues Analysis ===")
        
        issues = []
        
        # Check if target info is present
        if not (flags & 0x00004000):
            issues.append("Target Info flag not set")
        
        # Check if target info is empty
        if target_info_len == 0:
            issues.append("Target info is empty")
        
        # Check for required flags
        required_flags = [0x00000001, 0x00020000, 0x00004000]  # UNICODE, NTLM, Target Info
        for flag in required_flags:
            if not (flags & flag):
                issues.append(f"Missing required flag 0x{flag:08x}")
        
        # Check for problematic flags
        problematic_flags = [0x00000002]  # OEM flag might cause issues
        for flag in problematic_flags:
            if flags & flag:
                issues.append(f"Potentially problematic flag 0x{flag:08x}")
        
        if issues:
            print("❌ Potential issues found:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("✅ No obvious issues found")
        
        # Check Outlook-specific requirements
        print("\n=== Outlook Compatibility Check ===")
        
        # Outlook typically requires:
        # 1. Target info with proper AV pairs
        # 2. Correct version information
        # 3. Proper target name
        
        outlook_issues = []
        
        if target_name_len == 0:
            outlook_issues.append("Empty target name")
        
        if target_info_len == 0:
            outlook_issues.append("Empty target info")
        
        if not (flags & 0x00020000):  # NTLM flag
            outlook_issues.append("NTLM flag not set")
        
        if not (flags & 0x00000001):  # UNICODE flag
            outlook_issues.append("UNICODE flag not set")
        
        if outlook_issues:
            print("❌ Outlook compatibility issues:")
            for issue in outlook_issues:
                print(f"  - {issue}")
        else:
            print("✅ No obvious Outlook compatibility issues")
        
    except Exception as e:
        print(f"❌ Analysis error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_type2_challenge()
