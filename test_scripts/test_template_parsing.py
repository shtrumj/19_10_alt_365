#!/usr/bin/env python3
"""
Test template parsing directly
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.email_parser import parse_email_content
from jinja2 import Template

def test_template_parsing():
    """Test if the template parsing is working"""
    
    # Sample raw email content
    raw_email = """From: shtrumj@gmail.com> SIZE=4458
To: yonatan@shtrum.com
Date: 2025-09-28 12:42:24
(using TLS with cipher ECDHE-RSA-AES128-GCM-SHA256 (128/128 bits))
(Client did not present a certificate)

Received: by mail-wr1-f43.google.com with SMTP id ffacd0b85a97d-3f2ae6fadb4s03230071f8f.1
for ; Sun, 28 Sep 2025 05:42:24 -0700 (PDT)
DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed;
d=gmail.com; s=20230601; t=1759062743; x=1759667543; darn=shtrum.com;
h=to:subject:message-id:date:from:mime-version:from:to:cc:subject
:date:message-id:reply-to;
bh=hzVtnjRlCu0OC7ZfnIXOdTW48GRCej4rPSdyJ0SzfAg=;
b=WlhCaOCaTHvUSKvEKGKD6Qz+Jke/1gYalrc0OMeE7dAu/x+WIsiqE+MSwB/TRgdYys

U73g==
X-Google-DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed;
d=1e100.net; s=20230601; t=1759062743; x=1759667543;
h=to:subject:message-id:date:from:mime-version:x-gm-message-state
:from:to:cc:subject:date:message-id:reply-to;
bh=hzVtnjRlCu0OC7ZfnIXOdTW48GRCej4rPSdyJ0SzfAg=;
b=JFV0TiU/NtMRZ6wLmSKkA+tAXu0DclsXkl6lMDJEdQCu1zrqo5kwqwudICXwa7xjkc

GSPQ==
X-Gm-Message-State: AOJu0Yzn7TR6HfrTDySrBm/KRUgYUfPofTq8mwT7q4uZYlI89r1oZ40L

fTlByDzMW4Q5FWfbxyA7bL3ieqjClYak01w==
X-Gm-Gg: ASbGncs2oSs5kow5SBpL7uZlC9kEqth67BiIGYjWBD494iKuPRTv+FCCzeJ4hDz0gUp

X-Received: by 2002:a05:6000:1884:b0:3ec:ea72:ad53 with SMTP id
ffacd0b85a97d-40e4bb2f8famr13080146f8f.33.1759062617653; Sun, 28 Sep 2025
05:30:17 -0700 (PDT)
MIME-Version: 1.0
From: Jonathan Shtrum
Date: Sun, 28 Sep 2025 15:42:11 +0300
X-Gm-Features: AS18NWDy9q3d4_DC3JoGXZejLnOFIPIUAxd7Ad8122rg19dhqrOapXpiQT9UPHs
Message-ID:
Subject: 15:42
To: yonatan shtrum
Content-Type: multipart/alternative; boundary="000000000000768644063fdbae79"
X-Brightmail-Tracker: H4sIAAAAAAAAA+NgFprBIsWRWlGSWpSXmKPExsVyMfSurm6A1s0Mg7cveC3OnD3E7MDo0dDX

--000000000000768644063fdbae79
Content-Type: text/plain; charset="UTF-8"

Bizzzbazzz

--000000000000768644063fdbae79
Content-Type: text/html; charset="UTF-8"

Bizzzbazzz


--000000000000768644063fdbae79--"""
    
    print("🧪 Testing template parsing...")
    
    # Test direct parsing
    parsed = parse_email_content(raw_email)
    print(f"✅ Direct parsing result: '{parsed}'")
    
    # Test template rendering
    template_str = "{{ parse_email_content(email.body)|replace('\n', '<br>')|safe }}"
    template = Template(template_str)
    
    # Mock email object
    class MockEmail:
        def __init__(self, body):
            self.body = body
    
    email = MockEmail(raw_email)
    
    # Test with function available
    try:
        result = template.render(email=email, parse_email_content=parse_email_content)
        print(f"✅ Template with function: '{result}'")
    except Exception as e:
        print(f"❌ Template with function failed: {e}")
    
    # Test without function (what might be happening)
    try:
        result = template.render(email=email)
        print(f"❌ Template without function: '{result}'")
    except Exception as e:
        print(f"✅ Template without function correctly failed: {e}")

if __name__ == "__main__":
    test_template_parsing()
