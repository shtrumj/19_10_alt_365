#!/usr/bin/env python3
"""
Test email parsing functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.email_parser import parse_email_content, get_email_preview

def test_email_parsing():
    """Test the email parsing functionality"""
    print("🧪 Testing email parsing...")
    
    # Sample raw email content (similar to what you're seeing)
    raw_email = """From: shtrumj@gmail.com> SIZE=5853
To: yonatan@shtrum.com
Date: 2025-09-28 12:26:55
(using TLS with cipher ECDHE-RSA-AES128-GCM-SHA256 (128/128 bits))
(Client did not present a certificate)
by mx4.trot.co.il (Symantec Messaging Gateway) with SMTP id D1.14.07284.38929D86; Sun, 28 Sep 2025 15:26:43 +0300 (IDT)
Received: by mail-wr1-f51.google.com with SMTP id ffacd0b85a97d-3ee12807d97so3551065f8f.0
for ; Sun, 28 Sep 2025 05:26:54 -0700 (PDT)
DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed;
d=gmail.com; s=20230601; t=1759062413; x=1759667213; darn=shtrum.com;
h=to:subject:message-id:date:from:in-reply-to:references:mime-version
:from:to:cc:subject:date:message-id:reply-to;
bh=aCTni3druUmvWBFDONt+S30V29HsSGTkEvZ2XyRjeLU=;
b=fxBjqzafJ9dy5xZpZ1S2D3t4KAM0mmKfFcmrLHvoKC99huOlqX14DLltlY5Qyref/4
k1dWhg40UWEgWAgAj2ZmRSvG6xcLmtVxMMuSpnjQJNt1htWcqasP/BSVxAi/1yBsvGMT
Ie8+PWlRum3PC59EUA3JUQJ2ysx8WAqSZIdqyn96z57bOvmdFvUZyacr+Ue5OHXAiX2l
hub2bOAEYOvfoUqcOFygGCDTnPN1gIQ5a3neIoC1qGTP0+knSu3p/3jvgq3dDTYksBv8
wcrsh203zqKbas2nggjUmX0rhTexleuKCXlZpAXwnKI54vfhPYIW34beJs9OuKzt22yU
sgMQ==
X-Google-DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed;
d=1e100.net; s=20230601; t=1759062413; x=1759667213;
h=to:subject:message-id:date:from:in-reply-to:references:mime-version
:x-gm-message-state:from:to:cc:subject:date:message-id:reply-to;
bh=aCTni3druUmvWBFDONt+S30V29HsSGTkEvZ2XyRjeLU=;
b=aP5n5lG9unlBB8qjEjkEHpWGNyUM2F1VWwv6Z7MH/d9I6uUCs2sx/2aPvC80LtcmAs
HoUPkqhJro/Ws+2bYndlGjBUgA25ikgsgmWhQS6MFcCDlwLEoxQWm3w9+s6K2/cYrndR
glh5cAFgc6hfaTaHRAdVi/HWqIIMBf5Z4KVh+swCDSWqEfqh86J8+gV9FDMY3xn+39rO
BBOIAt+RrLbwbEv3aMAIwNkvjJcf1KsgMWsKxctpvRHggq9M0F5Cr2M2e8mZp9xkWUDM
AlZJmAtfXhkgH0QCXw6Q062qWX93WLE6N+pV3AyaATQ+o2cQN32oNXDV5iR5aCx6AxJH
j6WQ==
X-Gm-Message-State: AOJu0YyPevXCBgKIRxdNGEG62D3wCPkpk9OKB+bpVV+Ly8swlLtWoUQt
LhDRGNlLs8W9bRXXJTpmEFJovAvfR8C49A6cytvVarn09FylGaaUikPqzSn/0+CSkJt0Ns/R+8H
bGWj+maU7gVNmmkKQL5jQn77CCflwgqdYIw==
X-Gm-Gg: ASbGncvQZNkNXdIgKUqSfka9U0pArMryUs1BqHXSJb4gxlo+kWmzKR9gcM+YY3zyY9g
qTnYCqkxEBxsOxYIZ2zAzr6q4P9tbnx6xUXU1BSN9+3t0o4/naqHSab9VfmBDHn2beorh9INImp
HKgkNSEKoghCzC5uQC9OMkoGrUKaS4kkFNlaeSVJKcDXYNmsAIMm+wvozuP7JVi73qiRQUEv1A6
xdjERU+DNukwTzHIYVtNWq1ku/j2NGFjw9kLME=
X-Google-Smtp-Source: AGHT+IFjhg138FWtd93UayVbTVwBqOt6igHuEFRpGMC1oC/fzs9gpCVMpxDvLhbEf/2DqG9ctjtRajYLPrqtEH7fUGo=
X-Received: by 2002:a05:6000:2484:b0:3ee:1461:165f with SMTP id
ffacd0b85a97d-40e4bb2f907mr12226055f8f.31.1759062412612; Sun, 28 Sep 2025
05:26:52 -0700 (PDT)
MIME-Version: 1.0
References:
In-Reply-To:
From: Jonathan Shtrum
Date: Sun, 28 Sep 2025 15:26:41 +0300
X-Gm-Features: AS18NWDkiMbd8SKB4jlqF53ZBnVj_L-cJM7BT3w1xDYJh_5V4WvmhNQbu9XFKdU
Message-ID:
Subject: Fwd: 15:26
To: yonatan shtrum
Content-Type: multipart/alternative; boundary="0000000000003dd81b063fdba2c8"
X-Brightmail-Tracker: H4sIAAAAAAAAA+NgFrrBKsWRWlGSWpSXmKPExsVyMfSusW6z5s0Mg9MnRCzOnD3E7MDo0dDX
yh7AGMVlk5Kak1mWWqRvl8CVMW/6fZaCr5wVR24uY29gXMzZxcjJISFgInHw1QLGLkYuDiGB
HUwSD/ufskM4ixgl/k06BuawCDxglZi37QoziCMh8JpV4ujDhUwQziFGickbl0NlJjFJ3Dyw
iRVicpHEn9X3oaqAhv2dOocFJMErIChxcuYTMFtIIEDi0vkrjCA2p0CgxPazs9i6GDk42AQ0
JZqn+YGEWQRUJa7N+MUMMdNPYtsGkHIOoDEBEuufZ4KEhQWEJe7MOwBWIiKgLvH71momEJtZ
wEdi/d3PrBMYhWchWTwLSQrC1pRo3f6bHcJWlJjS/RDK1pBYcGcfI4StLbFs4WvmBYxsqxj5
citM9EqK8kv0kvP1MnM2MQKjgZ+Xm2kH4/NrzfqHGJk4GA8xSjIwKYnyvg67niHEl5SfUpmR
WJwRX1Sak1oMDDEOZiUR3rrNNzKEeFMSK6tSi/JhUtIcLErivH178zOEBNITS1KzU1MLUotg
skwc7IcYZTg4lCR4UzRuZggJFqWmp1akZeaUIKvhBNnAA7ThIxNQDW9xQWJucWY6Qp7/FKMr
x/qW/XuZOd59OQ8kVx6+AiR3g8kVS6YeZBZiycvPy5US592mCjRBAGRCRmke3BJYurvEKCsl
zMvIwMAgxAN0ZW5mCar8LUZBjlNMUMOgYq8YxTkYlYR5NVSAJvNk5pXAnSbVwFT54X2Zxe+d
sVJcV+Njp1y12cRqwfjE2c87b9MrrmVWv6Z8jJySsCQtw4PxY9fv20bnux0i7lzJltIKXOrx
74l5mYFOauGbjywtq9wucB2W/vjXS65dSXGVjP7dSeGtLQf8zvT8NY/Z/cljAqsxb/jVJUUH
Q3Lj+EzWWfl/mSVZwyy0SSqz4GjVwxY1519zkzTfHW2xddT6/iNG4IRwacnRX3yHrfjE1FS6
J4plCiX/8Oifl+QScvbrlvIv6ttaX15mvXvn6mkmc4bHTfvnvdl079wXqSMLrvCm+irNLcri
bWR2b79qVXNW8P72/ONH/lgGOJ1qydM0Mv9W3HJiT8DjObO8ugqmnS2vvdtnr8RSnJFoqMVc
VJwIAIRunzDrAwAA

--0000000000003dd81b063fdba2c8
Content-Type: text/plain; charset="UTF-8"
Content-Transfer-Encoding: base64

LS0tLS0tLS0tLSBGb3J3YXJkZWQgbWVzc2FnZSAtLS0tLS0tLS0NCtee15DXqjogSm9uYXRoYW4g
U2h0cnVtIDxzaHRydW1qQGdtYWlsLmNvbT4NCuKAqkRhdGU6INeZ15XXnSDXkNezLCAyOCDXkdeh
16TXmNezIDIwMjUg15EtMTU6MjbigKwNClN1YmplY3Q6IDE1OjI2DQpUbzogSm9uYXRoYW4gU2h0
cnVtIDxzaHRydW1qQGdtYWlsLmNvbT4NCg0KDQrXkdeT15nXp9eUINep15XXkQ0K
--0000000000003dd81b063fdba2c8
Content-Type: text/html; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable

<div dir="ltr" class="gmail_attr">---------- Forwarded message ---------=
=D7=9E=D7=90=D7=AA: Jon=
athan Shtrum <l.com">shtrumj@gmail.com>
=E2=80=AADate: =D7=99=D7=95=D7=
=9D =D7=90=D7=B3, 28 =D7=91=D7=A1=D7=A4=D7=98=D7=B3 2025 =D7=91-15:26=E2=80=
=AC
Subject: 15:26
To: Jonathan Shtrum <gmail.com">shtrumj@gmail.com>


>=D7=91=D7=93=D7=99=D7=A7=D7=94 =D7=A9=D7=95=D7=91

--0000000000003dd81b063fdba2c8--"""
    
    print("📧 Raw email content:")
    print("=" * 50)
    print(raw_email[:200] + "...")
    print("=" * 50)
    
    # Parse the email
    parsed_content = parse_email_content(raw_email)
    print("\n✅ Parsed email content:")
    print("=" * 50)
    print(parsed_content)
    print("=" * 50)
    
    # Get preview
    preview = get_email_preview(raw_email, 100)
    print(f"\n📝 Email preview (100 chars):")
    print("=" * 50)
    print(preview)
    print("=" * 50)
    
    if parsed_content and len(parsed_content.strip()) > 0:
        print("✅ Email parsing successful!")
        return True
    else:
        print("❌ Email parsing failed - no content extracted")
        return False

if __name__ == "__main__":
    test_email_parsing()
