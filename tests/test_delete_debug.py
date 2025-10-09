#!/usr/bin/env python3
"""
Debug script to test delete functionality in email view
"""
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_delete_in_email_view():
    """Test the delete functionality from the email view"""
    print("🧪 Testing delete functionality in email view...")
    
    base_url = "https://localhost:443"
    session = requests.Session()
    session.verify = False
    
    try:
        # 1. Get login page
        print("1. Getting login page...")
        login_response = session.get(f"{base_url}/auth/login")
        print(f"   Login page status: {login_response.status_code}")
        
        # 2. Login
        print("2. Attempting login...")
        login_data = {
            "username": "yonatan",
            "password": "Gib$0n579!"
        }
        login_response = session.post(f"{base_url}/auth/login", data=login_data, allow_redirects=False)
        print(f"   Login response status: {login_response.status_code}")
        
        if login_response.status_code == 302:
            print("   ✅ Login successful, redirected")
            
            # 3. Get inbox to see emails
            print("3. Getting inbox...")
            inbox_response = session.get(f"{base_url}/owa/inbox")
            print(f"   Inbox status: {inbox_response.status_code}")
            
            if inbox_response.status_code == 200:
                print("   ✅ Inbox accessible")
                
                # 4. Get emails via API to find an email to delete
                print("4. Getting emails via API...")
                emails_response = session.get(f"{base_url}/emails/")
                print(f"   Emails API status: {emails_response.status_code}")
                
                if emails_response.status_code == 200:
                    emails = emails_response.json()
                    print(f"   📧 Found {len(emails)} emails")
                    
                    if emails:
                        # 5. Get the first email's view page
                        email_id = emails[0]['id']
                        print(f"5. Getting email view page for email ID {email_id}...")
                        
                        email_view_response = session.get(f"{base_url}/owa/email/{email_id}")
                        print(f"   Email view status: {email_view_response.status_code}")
                        
                        if email_view_response.status_code == 200:
                            print("   ✅ Email view page accessible")
                            
                            # 6. Try to delete the email via API (simulating the button click)
                            print(f"6. Attempting to delete email ID {email_id}...")
                            
                            delete_response = session.delete(f"{base_url}/emails/{email_id}")
                            print(f"   Delete response status: {delete_response.status_code}")
                            print(f"   Delete response text: {delete_response.text}")
                            
                            if delete_response.status_code == 200:
                                print("   ✅ Email deleted successfully!")
                                
                                # 7. Verify email is deleted
                                print("7. Verifying email is deleted...")
                                emails_after = session.get(f"{base_url}/emails/")
                                if emails_after.status_code == 200:
                                    emails_after_data = emails_after.json()
                                    print(f"   📧 Emails after deletion: {len(emails_after_data)}")
                                    
                                    # Check if the deleted email is still there
                                    deleted_email_found = any(email['id'] == email_id for email in emails_after_data)
                                    if not deleted_email_found:
                                        print("   ✅ Email successfully removed from inbox")
                                    else:
                                        print("   ❌ Email still appears in inbox (soft delete)")
                            else:
                                print(f"   ❌ Delete failed: {delete_response.text}")
                        else:
                            print(f"   ❌ Failed to access email view: {email_view_response.status_code}")
                    else:
                        print("   ⚠️  No emails to delete")
                else:
                    print(f"   ❌ Failed to get emails: {emails_response.text}")
            else:
                print(f"   ❌ Failed to access inbox: {inbox_response.status_code}")
        else:
            print(f"   ❌ Login failed: {login_response.status_code}")
            print(f"   Response: {login_response.text[:200]}...")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_delete_in_email_view()
