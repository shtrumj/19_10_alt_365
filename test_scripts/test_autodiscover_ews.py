#!/usr/bin/env python3
import requests
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "https://owa.shtrum.com"

def post_autodiscover(email: str):
    xml = f'''<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006"><Request><EMailAddress>{email}</EMailAddress><AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006</AcceptableResponseSchema></Request></Autodiscover>'''
    r = requests.post(f"{HOST}/Autodiscover/Autodiscover.xml", data=xml, headers={"Content-Type":"text/xml"}, timeout=10)
    print("Autodiscover status:", r.status_code)
    print(r.text[:1000])

def post_ews_finditem():
    xml = '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><FindItem xmlns="http://schemas.microsoft.com/exchange/services/2006/messages" xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"><ItemShape><t:BaseShape>IdOnly</t:BaseShape></ItemShape><IndexedPageItemView MaxEntriesReturned="2" Offset="0" BasePoint="Beginning"/></FindItem></s:Body></s:Envelope>'
    r = requests.post(f"{HOST}/EWS/Exchange.asmx", data=xml, headers={"Content-Type":"text/xml"}, timeout=10)
    print("EWS FindItem status:", r.status_code)
    print(r.text[:1000])

if __name__ == "__main__":
    post_autodiscover("yonatan@shtrum.com")
    post_ews_finditem()


