#!/usr/bin/env python3
"""
Analyze iPhone's WBXML request vs our response
"""

def analyze_wbxml():
    # iPhone request
    iphone_request = bytes.fromhex("03016a00000756520330000101")
    print("📱 iPhone WBXML Request Analysis:")
    print(f"   Length: {len(iphone_request)} bytes")
    print(f"   Hex: {iphone_request.hex()}")
    print(f"   Header: {iphone_request[:6].hex()}")
    print(f"   String table length: {iphone_request[6:9].hex()}")
    print(f"   Namespace switch: {iphone_request[9:11].hex()}")
    print(f"   FolderSync data: {iphone_request[11:].hex()}")
    print()
    
    # Our response
    our_response = bytes.fromhex("03016a000007000145460331000147033100014849033100014a4b033100014c033000014d03496e626f7800014e03320001010101")
    print("🖥️  Our WBXML Response Analysis:")
    print(f"   Length: {len(our_response)} bytes")
    print(f"   Hex: {our_response.hex()}")
    print(f"   Header: {our_response[:6].hex()}")
    print(f"   String table length: {our_response[6:9].hex()}")
    print(f"   Namespace switch: {our_response[9:11].hex()}")
    print(f"   FolderSync start: {our_response[11:20].hex()}")
    print()
    
    # Compare namespace switches
    print("🔍 Namespace Switch Comparison:")
    print(f"   iPhone sends: {iphone_request[9:11].hex()} (VR)")
    print(f"   We respond with: {our_response[9:11].hex()} (00 01)")
    print()
    
    # The iPhone is sending "VR" (0x5652) but we're responding with "00 01"
    # This suggests the iPhone expects a different namespace or encoding
    
    print("⚠️  Potential Issue:")
    print("   The iPhone is sending namespace switch 'VR' (0x5652)")
    print("   But we're responding with '00 01' (SWITCH_PAGE to codepage 1)")
    print("   This mismatch might be causing the iPhone to reject our response")
    print()
    
    # Let's try to decode what "VR" means
    print("🔬 Decoding iPhone's namespace switch:")
    print(f"   0x56 = {0x56} (decimal)")
    print(f"   0x52 = {0x52} (decimal)")
    print("   This might be a different namespace or encoding format")
    print()
    
    print("💡 Solution:")
    print("   We need to match the iPhone's namespace switch pattern")
    print("   Instead of '00 01', we should respond with 'VR' or equivalent")

if __name__ == "__main__":
    analyze_wbxml()
