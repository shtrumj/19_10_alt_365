#!/bin/bash
# =============================================================================
# Autodiscover, GAB, and OAB Testing Script (curl-based)
# =============================================================================
#
# Usage:
#   ./test_autodiscover_gab_oab.sh [hostname] [email]
#
# Examples:
#   ./test_autodiscover_gab_oab.sh localhost:8000 user@example.com
#   ./test_autodiscover_gab_oab.sh owa.shtrum.com user@shtrum.com
#
# =============================================================================

# Configuration
HOST="${1:-localhost:8000}"
EMAIL="${2:-user@example.com}"
PROTOCOL="http"  # Change to https for production

# Detect protocol
if [[ "$HOST" != "localhost"* ]] && [[ "$HOST" != "127.0.0.1"* ]]; then
    PROTOCOL="https"
fi

BASE_URL="${PROTOCOL}://${HOST}"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo ""
    echo "================================================================================"
    echo "  $1"
    echo "================================================================================"
}

print_test() {
    if [ "$2" = "PASS" ]; then
        echo -e "${GREEN}✅ PASS${NC} - $1"
    else
        echo -e "${RED}❌ FAIL${NC} - $1"
    fi
    if [ ! -z "$3" ]; then
        echo "         $3"
    fi
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Main header
echo "================================================================================"
echo "             AUTODISCOVER, GAB, OAB TEST SUITE (CURL)"
echo "================================================================================"
echo ""
echo "🎯 Target: $BASE_URL"
echo "📧 Test Email: $EMAIL"
echo ""

# =============================================================================
# TEST 1: Autodiscover (XML)
# =============================================================================
print_header "1. AUTODISCOVER (XML)"

AUTODISCOVER_REQUEST="<?xml version=\"1.0\" encoding=\"utf-8\"?>
<Autodiscover xmlns=\"http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006\">
  <Request>
    <EMailAddress>${EMAIL}</EMailAddress>
    <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
  </Request>
</Autodiscover>"

echo "$AUTODISCOVER_REQUEST" > /tmp/autodiscover_request.xml

RESPONSE=$(curl -s -X POST \
    -H "Content-Type: text/xml; charset=utf-8" \
    -H "User-Agent: Microsoft Office/16.0 (Windows NT 10.0; Microsoft Outlook 16.0.5266; Pro)" \
    --data "@/tmp/autodiscover_request.xml" \
    -k \
    -w "\n%{http_code}" \
    "${BASE_URL}/Autodiscover/Autodiscover.xml")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

echo ""
echo "📤 Request URL: ${BASE_URL}/Autodiscover/Autodiscover.xml"
echo "📥 Response Status: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    print_test "Autodiscover XML Response" "PASS" "HTTP 200"
    
    # Check for protocols
    if echo "$BODY" | grep -q "<Type>EXHTTP</Type>"; then
        print_test "Has EXHTTP protocol" "PASS" "MAPI/HTTP support"
    else
        print_test "Has EXHTTP protocol" "FAIL" "Missing MAPI/HTTP"
    fi
    
    if echo "$BODY" | grep -q "<Type>WEB</Type>"; then
        print_test "Has WEB protocol" "PASS" "OWA support"
    fi
    
    if echo "$BODY" | grep -q "<Type>MobileSync</Type>"; then
        print_test "Has MobileSync protocol" "PASS" "ActiveSync support"
    fi
    
    # Extract MAPI URL
    MAPI_URL=$(echo "$BODY" | grep -o '<Server>[^<]*</Server>' | head -1 | sed 's/<[^>]*>//g')
    if [ ! -z "$MAPI_URL" ]; then
        print_info "MAPI Server: $MAPI_URL"
    fi
    
    # Save response for inspection
    echo "$BODY" > /tmp/autodiscover_response.xml
    print_info "Response saved to: /tmp/autodiscover_response.xml"
else
    print_test "Autodiscover XML Response" "FAIL" "HTTP $HTTP_CODE"
fi

# =============================================================================
# TEST 2: Autodiscover (JSON)
# =============================================================================
print_header "2. AUTODISCOVER (JSON)"

RESPONSE=$(curl -s -X GET \
    -H "Accept: application/json" \
    -H "User-Agent: Microsoft Office/16.0" \
    -k \
    -w "\n%{http_code}" \
    "${BASE_URL}/autodiscover/autodiscover.json/v1.0/${EMAIL}")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

echo ""
echo "📤 Request URL: ${BASE_URL}/autodiscover/autodiscover.json/v1.0/${EMAIL}"
echo "📥 Response Status: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    print_test "Autodiscover JSON Response" "PASS" "HTTP 200"
    
    if echo "$BODY" | grep -q '"Protocol"'; then
        print_test "Has Protocol field" "PASS"
    fi
    
    if echo "$BODY" | grep -q '"AutodiscoverUrl"'; then
        print_test "Has AutodiscoverUrl" "PASS"
    fi
    
    echo ""
    echo "📋 JSON Response (preview):"
    echo "$BODY" | head -20
    
    echo "$BODY" > /tmp/autodiscover_response.json
    print_info "Response saved to: /tmp/autodiscover_response.json"
else
    print_test "Autodiscover JSON Response" "FAIL" "HTTP $HTTP_CODE"
fi

# =============================================================================
# TEST 3: OAB Manifest
# =============================================================================
print_header "3. OFFLINE ADDRESS BOOK (OAB) - Manifest"

RESPONSE=$(curl -s -X GET \
    -H "User-Agent: Microsoft Office/16.0" \
    -k \
    -w "\n%{http_code}" \
    "${BASE_URL}/oab/oab.xml")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

echo ""
echo "📤 Request URL: ${BASE_URL}/oab/oab.xml"
echo "📥 Response Status: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    print_test "OAB Manifest" "PASS" "HTTP 200"
    
    if echo "$BODY" | grep -q "<OAB"; then
        print_test "Has OAB structure" "PASS"
    fi
    
    if echo "$BODY" | grep -q "browse.oab"; then
        print_test "Has browse.oab file" "PASS"
    fi
    
    if echo "$BODY" | grep -q "details.oab"; then
        print_test "Has details.oab file" "PASS"
    fi
    
    if echo "$BODY" | grep -q "rdndex.oab"; then
        print_test "Has rdndex.oab file" "PASS"
    fi
    
    echo ""
    echo "📋 OAB Details:"
    echo "$BODY" | grep -E "(Name>|Version>|Size>)" | head -5
    
    echo "$BODY" > /tmp/oab_manifest.xml
    print_info "Response saved to: /tmp/oab_manifest.xml"
else
    print_test "OAB Manifest" "FAIL" "HTTP $HTTP_CODE"
fi

# =============================================================================
# TEST 4: OAB Data Files
# =============================================================================
print_header "4. OFFLINE ADDRESS BOOK (OAB) - Data Files"

OAB_ID="default-oab"

for FILE in "browse.oab" "details.oab" "rdndex.oab"; do
    echo ""
    echo "📤 Testing: $FILE"
    
    RESPONSE=$(curl -s -X GET \
        -H "User-Agent: Microsoft Office/16.0" \
        -k \
        -w "\n%{http_code}" \
        -o "/tmp/${FILE}" \
        "${BASE_URL}/oab/${OAB_ID}/${FILE}")
    
    HTTP_CODE="$RESPONSE"
    
    echo "   URL: ${BASE_URL}/oab/${OAB_ID}/${FILE}"
    echo "   Status: $HTTP_CODE"
    
    if [ "$HTTP_CODE" = "200" ]; then
        FILE_SIZE=$(wc -c < "/tmp/${FILE}" | tr -d ' ')
        print_test "$FILE" "PASS" "Size: $FILE_SIZE bytes"
    else
        print_test "$FILE" "FAIL" "HTTP $HTTP_CODE"
    fi
done

# =============================================================================
# TEST 5: NSPI/GAB
# =============================================================================
print_header "5. NSPI/GAB - Global Address List"

# Create binary NSPI request
printf '\x01\x00\x00\x00\x00\x00\x00\x00\x64\x00\x00\x00' > /tmp/nspi_request.bin

RESPONSE=$(curl -s -X POST \
    -H "Content-Type: application/mapi-http" \
    -H "User-Agent: Microsoft Office/16.0" \
    -H "X-RequestType: GetMatches" \
    --data-binary "@/tmp/nspi_request.bin" \
    -k \
    -w "\n%{http_code}" \
    -o "/tmp/nspi_response.bin" \
    "${BASE_URL}/mapi/nspi")

HTTP_CODE="$RESPONSE"

echo ""
echo "📤 Request URL: ${BASE_URL}/mapi/nspi"
echo "📥 Response Status: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    FILE_SIZE=$(wc -c < "/tmp/nspi_response.bin" | tr -d ' ')
    print_test "NSPI/GAB Response" "PASS" "Size: $FILE_SIZE bytes"
    
    if [ "$FILE_SIZE" -gt 8 ]; then
        print_test "Has response data" "PASS" "Response contains data"
        print_info "Response saved to: /tmp/nspi_response.bin"
    fi
else
    print_test "NSPI/GAB Response" "FAIL" "HTTP $HTTP_CODE"
fi

# =============================================================================
# Summary
# =============================================================================
print_header "TEST COMPLETE"

echo ""
echo "✅ All endpoints tested"
echo ""
echo "📁 Response files saved to /tmp/:"
echo "   - autodiscover_response.xml"
echo "   - autodiscover_response.json"
echo "   - oab_manifest.xml"
echo "   - browse.oab, details.oab, rdndex.oab"
echo "   - nspi_response.bin"
echo ""
echo "💡 TIP: Inspect response files for detailed information"
echo "💡 TIP: Check server logs for backend details"
echo ""

# Cleanup
rm -f /tmp/autodiscover_request.xml /tmp/nspi_request.bin

