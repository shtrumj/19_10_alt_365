#!/usr/bin/env python3
"""
Compare HTML in Database vs What's Being Sent via ActiveSync

This script analyzes what's actually in the database and what's being logged
as sent via ActiveSync to identify any discrepancies.
"""

import json
import sqlite3

DATABASE_PATH = "data/email_system.db"
LOG_PATH = "logs/activesync/activesync.log"


def get_db_emails():
    """Get email HTML content from database"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, subject, body_html, mime_content
        FROM emails
        WHERE recipient_id = 1
        ORDER BY id DESC
        LIMIT 10
    """
    )

    emails = {}
    for row in cursor.fetchall():
        emails[row["id"]] = {
            "subject": row["subject"],
            "body_html": row["body_html"],
            "html_length": len(row["body_html"]) if row["body_html"] else 0,
            "mime_content": row["mime_content"],
        }

    conn.close()
    return emails


def parse_activesync_log():
    """Parse ActiveSync log for HTML content being sent"""
    sent_emails = {}

    with open(LOG_PATH, "r") as f:
        for line in f:
            try:
                log = json.loads(line)

                # Look for body_content_selected events
                if log.get("event") == "body_content_selected":
                    email_id = log.get("email_id")
                    if email_id:
                        sent_emails[email_id] = {
                            "preference": log.get("preference"),
                            "selected_native": log.get("selected_native"),
                            "plain_length": log.get("plain_length"),
                            "html_length": log.get("html_length"),
                            "selected_content_length": log.get(
                                "selected_content_length"
                            ),
                            "content_preview": log.get("content_preview", ""),
                        }

                # Look for wbxml_body_data_write events
                elif log.get("event") == "wbxml_body_data_write":
                    # This is what's actually written to WBXML
                    pass

            except json.JSONDecodeError:
                continue

    return sent_emails


def main():
    print("=" * 80)
    print("HTML Content Comparison: Database vs ActiveSync Logs")
    print("=" * 80 + "\n")

    # Get database emails
    print("📊 Loading database emails...")
    db_emails = get_db_emails()
    print(f"   Found {len(db_emails)} emails in database\n")

    # Parse ActiveSync logs
    print("📝 Parsing ActiveSync logs...")
    sent_emails = parse_activesync_log()
    print(f"   Found {len(sent_emails)} emails in logs\n")

    # Compare
    print("=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80 + "\n")

    for email_id in sorted(db_emails.keys(), reverse=True)[:5]:
        db_email = db_emails[email_id]
        sent_email = sent_emails.get(email_id)

        print(f"📧 Email ID: {email_id}")
        print(f"   Subject: {db_email['subject'][:50]}...")
        print(f"\n   💾 DATABASE:")
        print(f"      HTML Length: {db_email['html_length']} bytes")

        if db_email["body_html"]:
            preview = db_email["body_html"][:150]
            print(f"      Preview: {preview}...")

            # Check if it's a complete HTML document
            html_lower = db_email["body_html"][:200].lower()
            if "<!doctype" in html_lower or html_lower.strip().startswith("<html"):
                print(f"      Structure: ✅ Complete HTML document")
            else:
                print(
                    f"      Structure: ⚠️  HTML Fragment (starts with {db_email['body_html'][:20]}...)"
                )

        if sent_email:
            print(f"\n   📡 ACTIVESYNC SENT:")
            print(f"      Preference: Type {sent_email['preference']}")
            print(
                f"      Selected Length: {sent_email['selected_content_length']} bytes"
            )
            print(f"      HTML in DB: {sent_email['html_length']} bytes")
            print(f"      Plain in DB: {sent_email['plain_length']} bytes")
            print(f"      Preview: {sent_email['content_preview'][:150]}...")

            # Analysis
            print(f"\n   🔍 ANALYSIS:")
            if sent_email["selected_content_length"] == db_email["html_length"]:
                print(
                    f"      ✅ Sent full HTML from database ({sent_email['selected_content_length']} bytes)"
                )
            elif sent_email["selected_content_length"] < db_email["html_length"]:
                diff = db_email["html_length"] - sent_email["selected_content_length"]
                print(f"      ⚠️  Sent {diff} bytes LESS than database")
            elif sent_email["selected_content_length"] > db_email["html_length"]:
                diff = sent_email["selected_content_length"] - db_email["html_length"]
                print(f"      ⚠️  Sent {diff} bytes MORE than database (wrapped?)")

            # Check content structure
            sent_preview = sent_email["content_preview"]
            db_preview = db_email["body_html"][:150] if db_email["body_html"] else ""

            if sent_preview and db_preview:
                if sent_preview.strip().startswith(
                    "<!DOCTYPE"
                ) or sent_preview.strip().startswith("<html>"):
                    if not (
                        db_preview.strip().startswith("<!DOCTYPE")
                        or db_preview.strip().lower().startswith("<html")
                    ):
                        print(
                            f"      ⚠️  WARNING: Server WRAPPED HTML fragment in complete document!"
                        )
                        print(f"      ⚠️  This may cause rendering issues on iOS!")
                elif db_preview.strip().startswith(
                    "<!DOCTYPE"
                ) or db_preview.strip().lower().startswith("<html"):
                    if not (
                        sent_preview.strip().startswith("<!DOCTYPE")
                        or sent_preview.strip().startswith("<html>")
                    ):
                        print(
                            f"      ⚠️  WARNING: Database has complete HTML, but sending fragment!"
                        )
                else:
                    if sent_preview[:50] == db_preview[:50]:
                        print(f"      ✅ Content matches (HTML fragment preserved)")
                    else:
                        print(f"      ⚠️  Content mismatch detected")
        else:
            print(f"\n   ❌ NOT FOUND in ActiveSync logs")

        print("\n" + "-" * 80 + "\n")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Database emails: {len(db_emails)}")
    print(f"✅ Logged as sent: {len(sent_emails)}")
    print(f"\n📌 Check if HTML fragments are being sent correctly")
    print(f"📌 Verify iOS is receiving HTML Type 2 (not plain text)")
    print(f"📌 Ensure no HTML wrapping is being added server-side")


if __name__ == "__main__":
    main()
