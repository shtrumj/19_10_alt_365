#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test ActiveSync HTML Download - Compare WBXML Response to Database

This script:
1. Performs real ActiveSync Sync commands
2. Parses WBXML responses
3. Compares HTML content received vs database content
4. Identifies discrepancies in HTML rendering
"""

import base64
import json
import sqlite3
from typing import Any, Dict, List

import requests

# Configuration
ACTIVESYNC_URL = "http://localhost:8001/Microsoft-Server-ActiveSync"
USERNAME = "yonatan@shtrum.com"
PASSWORD = "Gib$0n579!"
DEVICE_ID = "TESTDEVICE123"
DEVICE_TYPE = "TestClient"
DATABASE_PATH = "/Users/jonathanshtrum/Dev/4_09_365_alt/data/email_system.db"

# WBXML Constants
SWITCH_PAGE = 0x00
END = 0x01
STR_I = 0x03
OPAQUE = 0xC3

# Code pages
CP_AIRSYNC = 0
CP_EMAIL = 2
CP_AIRSYNCBASE = 17

# AirSync tokens
AS_Sync = 0x05
AS_Collections = 0x1C
AS_Collection = 0x0F
AS_SyncKey = 0x0B
AS_CollectionId = 0x12
AS_WindowSize = 0x15
AS_Commands = 0x16
AS_Add = 0x07
AS_ServerId = 0x0D
AS_ApplicationData = 0x1D
AS_Status = 0x0E
AS_MoreAvailable = 0x14

# Email tokens
EM_Subject = 0x14
EM_From = 0x18
EM_To = 0x16
EM_DateReceived = 0x0F
EM_Read = 0x15
EM_MessageClass = 0x13
EM_InternetCPID = 0x39

# AirSyncBase tokens
ASB_Body = 0x0A
ASB_Type = 0x06
ASB_EstimatedDataSize = 0x0C
ASB_Truncated = 0x0D
ASB_Data = 0x0B
ASB_Preview = 0x14
ASB_NativeBodyType = 0x16
ASB_ContentType = 0x0E


class WBXMLParser:
    """Simple WBXML parser for ActiveSync responses"""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.current_codepage = 0

    def read_byte(self) -> int:
        if self.pos >= len(self.data):
            return None
        b = self.data[self.pos]
        self.pos += 1
        return b

    def read_string(self) -> str:
        """Read inline string (STR_I)"""
        result = []
        while True:
            b = self.read_byte()
            if b is None or b == 0:
                break
            result.append(b)
        return bytes(result).decode("utf-8", errors="ignore")

    def read_opaque(self) -> bytes:
        """Read opaque data"""
        length = self.read_multibyte_int()
        data = self.data[self.pos : self.pos + length]
        self.pos += length
        return data

    def read_multibyte_int(self) -> int:
        """Read multi-byte integer"""
        result = 0
        while True:
            b = self.read_byte()
            if b is None:
                break
            result = (result << 7) | (b & 0x7F)
            if (b & 0x80) == 0:
                break
        return result

    def parse_emails(self) -> List[Dict[str, Any]]:
        """Parse WBXML and extract email data"""
        emails = []
        current_email = {}
        in_body = False
        body_data = {}

        # Skip WBXML header
        if self.pos < 3:
            self.pos = 3

        while self.pos < len(self.data):
            b = self.read_byte()
            if b is None:
                break

            if b == SWITCH_PAGE:
                self.current_codepage = self.read_byte()
                continue

            if b == END:
                if in_body:
                    current_email["body"] = body_data.copy()
                    body_data = {}
                    in_body = False
                elif current_email:
                    emails.append(current_email.copy())
                    current_email = {}
                continue

            if b == STR_I:
                # Inline string
                s = self.read_string()
                continue

            # Check if it's a tag
            tag = b & 0x3F
            has_content = (b & 0x40) != 0

            if not has_content:
                continue

            # Read the content
            next_b = self.read_byte()
            if next_b is None:
                break

            if next_b == STR_I:
                value = self.read_string()
            elif next_b == OPAQUE:
                value = self.read_opaque()
            elif next_b == END:
                value = None
            else:
                self.pos -= 1
                value = None

            # Store based on token
            if self.current_codepage == CP_AIRSYNC:
                if tag == AS_ServerId:
                    current_email["server_id"] = value
            elif self.current_codepage == CP_EMAIL:
                if tag == EM_Subject:
                    current_email["subject"] = value
                elif tag == EM_From:
                    current_email["from"] = value
                elif tag == EM_To:
                    current_email["to"] = value
                elif tag == EM_DateReceived:
                    current_email["date"] = value
            elif self.current_codepage == CP_AIRSYNCBASE:
                if tag == ASB_Body:
                    in_body = True
                elif in_body:
                    if tag == ASB_Type:
                        body_data["type"] = value
                    elif tag == ASB_EstimatedDataSize:
                        body_data["estimated_size"] = value
                    elif tag == ASB_Truncated:
                        body_data["truncated"] = value
                    elif tag == ASB_Data:
                        body_data["data"] = value
                    elif tag == ASB_Preview:
                        body_data["preview"] = value
                elif tag == ASB_NativeBodyType:
                    current_email["native_body_type"] = value

        return emails


def create_wbxml_sync_request(sync_key: str, collection_id: str) -> bytes:
    """Create WBXML Sync request"""
    wbxml = bytearray()

    # WBXML header
    wbxml.extend([0x03, 0x01, 0x6A, 0x00])

    # <Sync>
    wbxml.append(0x45)  # SWITCH_PAGE to AirSync
    wbxml.append(AS_Sync | 0x40)

    # <Collections>
    wbxml.append(AS_Collections | 0x40)

    # <Collection>
    wbxml.append(AS_Collection | 0x40)

    # <SyncKey>
    wbxml.append(AS_SyncKey | 0x40)
    wbxml.append(STR_I)
    wbxml.extend(sync_key.encode("utf-8"))
    wbxml.append(0x00)
    wbxml.append(END)

    # <CollectionId>
    wbxml.append(AS_CollectionId | 0x40)
    wbxml.append(STR_I)
    wbxml.extend(collection_id.encode("utf-8"))
    wbxml.append(0x00)
    wbxml.append(END)

    # <WindowSize>
    wbxml.append(AS_WindowSize | 0x40)
    wbxml.append(STR_I)
    wbxml.extend(b"25")
    wbxml.append(0x00)
    wbxml.append(END)

    # Switch to AirSyncBase codepage for body preferences
    wbxml.append(SWITCH_PAGE)
    wbxml.append(CP_AIRSYNCBASE)

    # <BodyPreference>
    wbxml.append(0x05 | 0x40)  # BodyPreference

    # <Type>2</Type> (HTML)
    wbxml.append(ASB_Type | 0x40)
    wbxml.append(STR_I)
    wbxml.extend(b"2")
    wbxml.append(0x00)
    wbxml.append(END)

    # <TruncationSize>32768</TruncationSize>
    wbxml.append(0x07 | 0x40)  # TruncationSize
    wbxml.append(STR_I)
    wbxml.extend(b"32768")
    wbxml.append(0x00)
    wbxml.append(END)

    wbxml.append(END)  # </BodyPreference>

    # Switch back to AirSync
    wbxml.append(SWITCH_PAGE)
    wbxml.append(CP_AIRSYNC)

    wbxml.append(END)  # </Collection>
    wbxml.append(END)  # </Collections>
    wbxml.append(END)  # </Sync>

    return bytes(wbxml)


def perform_activesync_sync() -> List[Dict[str, Any]]:
    """Perform ActiveSync Sync command"""
    print("=" * 80)
    print("STEP 1: Performing ActiveSync FolderSync")
    print("=" * 80)

    # First, get sync key via FolderSync
    foldersync_url = f"{ACTIVESYNC_URL}?User={USERNAME}&DeviceId={DEVICE_ID}&DeviceType={DEVICE_TYPE}&Cmd=FolderSync"

    # Simple FolderSync request (SyncKey=0)
    foldersync_body = bytes(
        [0x03, 0x01, 0x6A, 0x00, 0x07, 0x56, 0x52, 0x03, 0x30, 0x00, 0x01, 0x01]
    )

    auth = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/vnd.ms-sync.wbxml",
        "MS-ASProtocolVersion": "16.1",
        "User-Agent": "TestClient/1.0",
    }

    response = requests.post(foldersync_url, data=foldersync_body, headers=headers)
    print(f"FolderSync Response: {response.status_code}")
    print(f"Response length: {len(response.content)} bytes\n")

    # Now perform Sync with collection_id=1 (inbox)
    print("=" * 80)
    print("STEP 2: Performing ActiveSync Sync (Initial)")
    print("=" * 80)

    sync_url = f"{ACTIVESYNC_URL}?User={USERNAME}&DeviceId={DEVICE_ID}&DeviceType={DEVICE_TYPE}&Cmd=Sync"

    # Initial sync (SyncKey=0)
    sync_body = create_wbxml_sync_request("0", "1")

    print(f"Sync Request URL: {sync_url}")
    print(f"Request body length: {len(sync_body)} bytes")
    print(f"Request body hex: {sync_body.hex()[:100]}...\n")

    response = requests.post(sync_url, data=sync_body, headers=headers)
    print(f"Sync Response: {response.status_code}")
    print(f"Response length: {len(response.content)} bytes")

    if response.status_code != 200:
        print(f"ERROR: {response.text}")
        return []

    # Parse WBXML response
    print("\n" + "=" * 80)
    print("STEP 3: Parsing WBXML Response")
    print("=" * 80)

    parser = WBXMLParser(response.content)
    emails = parser.parse_emails()

    print(f"Parsed {len(emails)} emails from WBXML\n")

    return emails


def get_database_emails() -> List[Dict[str, Any]]:
    """Get emails from database"""
    print("=" * 80)
    print("STEP 4: Fetching Emails from Database")
    print("=" * 80)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, subject, sender, recipient, body, body_html, mime_content, 
               is_read, created_at
        FROM emails
        WHERE recipient = ?
        ORDER BY created_at DESC
        LIMIT 10
    """,
        (USERNAME,),
    )

    emails = []
    for row in cursor.fetchall():
        email = {
            "id": row["id"],
            "subject": row["subject"],
            "from": row["sender"],
            "to": row["recipient"],
            "body": row["body"],
            "body_html": row["body_html"],
            "mime_content": row["mime_content"],
            "is_read": bool(row["is_read"]),
            "date": row["created_at"],
        }
        emails.append(email)

    conn.close()

    print(f"Fetched {len(emails)} emails from database\n")

    return emails


def compare_emails(activesync_emails: List[Dict], db_emails: List[Dict]):
    """Compare ActiveSync downloaded emails with database"""
    print("=" * 80)
    print("STEP 5: Comparing ActiveSync vs Database")
    print("=" * 80)

    for i, as_email in enumerate(activesync_emails[:5]):  # First 5
        print(f"\n{'=' * 80}")
        print(f"EMAIL #{i+1}")
        print("=" * 80)

        # Extract email ID from server_id (format: "1:26")
        server_id = as_email.get("server_id", "")
        if ":" in server_id:
            email_id = int(server_id.split(":")[1])
        else:
            print(f"⚠️  Cannot parse server_id: {server_id}")
            continue

        # Find matching DB email
        db_email = next((e for e in db_emails if e["id"] == email_id), None)
        if not db_email:
            print(f"❌ Email ID {email_id} not found in database!")
            continue

        print(f"📧 Email ID: {email_id}")
        print(f"📝 Subject: {as_email.get('subject', 'N/A')}")
        print(f"👤 From: {as_email.get('from', 'N/A')}")
        print(f"📅 Date: {as_email.get('date', 'N/A')}")

        # Check body
        body_info = as_email.get("body", {})
        body_type = body_info.get("type", "N/A")
        body_data = body_info.get("data", "")
        body_size = len(body_data) if body_data else 0
        estimated_size = body_info.get("estimated_size", "N/A")
        truncated = body_info.get("truncated", "N/A")

        print(f"\n📄 BODY INFO (ActiveSync):")
        print(
            f"   Type: {body_type} ({'Plain Text' if body_type == '1' else 'HTML' if body_type == '2' else 'MIME' if body_type == '4' else 'Unknown'})"
        )
        print(f"   Estimated Size: {estimated_size} bytes")
        print(f"   Actual Size: {body_size} bytes")
        print(f"   Truncated: {truncated}")

        if body_data:
            preview = (
                body_data[:200] if isinstance(body_data, str) else str(body_data[:200])
            )
            print(f"   Preview: {preview}...")

        # Compare with database
        db_html = db_email.get("body_html", "")
        db_html_size = len(db_html) if db_html else 0

        print(f"\n💾 DATABASE INFO:")
        print(f"   HTML Size: {db_html_size} bytes")

        if db_html:
            db_preview = db_html[:200]
            print(f"   Preview: {db_preview}...")

        # Analysis
        print(f"\n🔍 ANALYSIS:")

        if body_type == "2":
            if body_size == 0:
                print("   ❌ ERROR: ActiveSync returned ZERO bytes for HTML body!")
            elif body_size < db_html_size * 0.9:
                print(
                    f"   ⚠️  WARNING: ActiveSync HTML ({body_size} bytes) is {db_html_size - body_size} bytes smaller than database ({db_html_size} bytes)"
                )
            else:
                print(
                    f"   ✅ Size looks good (AS: {body_size} bytes, DB: {db_html_size} bytes)"
                )

            # Check if it's wrapped HTML
            if body_data and isinstance(body_data, str):
                if body_data.strip().startswith(
                    "<!DOCTYPE"
                ) or body_data.strip().startswith("<html>"):
                    print("   ℹ️  HTML is wrapped in complete document")
                else:
                    print("   ℹ️  HTML is a fragment (not wrapped)")

                # Check for Hebrew content
                if any(ord(c) >= 0x0590 and ord(c) <= 0x05FF for c in body_data[:500]):
                    print("   🔤 Contains Hebrew characters")
        else:
            print(f"   ⚠️  Body type is {body_type}, not HTML (2)")

        # Check native body type
        native_type = as_email.get("native_body_type", "N/A")
        print(f"   Native Body Type: {native_type}")


def main():
    """Main test function"""
    print("\n" + "=" * 80)
    print("ActiveSync HTML Download Test")
    print("Testing: HTML content download and comparison")
    print("=" * 80 + "\n")

    try:
        # Step 1-3: Download via ActiveSync
        activesync_emails = perform_activesync_sync()

        if not activesync_emails:
            print("\n❌ No emails downloaded via ActiveSync!")
            return

        # Step 4: Get from database
        db_emails = get_database_emails()

        if not db_emails:
            print("\n❌ No emails found in database!")
            return

        # Step 5: Compare
        compare_emails(activesync_emails, db_emails)

        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
