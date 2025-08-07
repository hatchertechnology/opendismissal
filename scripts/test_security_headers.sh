#!/bin/bash

# Security Headers Test Script for OpenDismissal
# Tests that all security headers are properly configured

set -e

DOMAIN="dismiss.hatchertechnology.com"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔒 Testing Security Headers for OpenDismissal"
echo "============================================="
echo "Domain: $DOMAIN"
echo ""

# Function to check header
check_header() {
    local header_name=$1
    local expected_pattern=$2
    local description=$3
    
    echo -n "Checking $header_name... "
    
    # Fetch header
    header_value=$(curl -s -I "https://$DOMAIN" | grep -i "^$header_name:" | cut -d' ' -f2- | tr -d '\r\n')
    
    if [ -z "$header_value" ]; then
        echo -e "${RED}✗ MISSING${NC}"
        echo "  Expected: $description"
        return 1
    elif echo "$header_value" | grep -q "$expected_pattern"; then
        echo -e "${GREEN}✓ OK${NC}"
        echo "  Value: $header_value"
        return 0
    else
        echo -e "${YELLOW}⚠ INCORRECT${NC}"
        echo "  Found: $header_value"
        echo "  Expected pattern: $expected_pattern"
        return 1
    fi
}

echo "1. Security Headers Check"
echo "-------------------------"

# Check Content-Security-Policy
check_header "Content-Security-Policy" "default-src" "CSP with default-src directive"

# Check Cross-Origin headers
check_header "Cross-Origin-Opener-Policy" "same-origin" "COOP set to same-origin"
check_header "Cross-Origin-Embedder-Policy" "require-corp" "COEP set to require-corp"
check_header "Cross-Origin-Resource-Policy" "same-origin" "CORP set to same-origin"

# Check standard security headers
check_header "X-Content-Type-Options" "nosniff" "Prevent MIME type sniffing"
check_header "X-Frame-Options" "DENY" "Prevent clickjacking"
check_header "Referrer-Policy" "strict-origin" "Control referrer information"

# Check Permissions-Policy
check_header "Permissions-Policy" "camera" "Feature policy controlling browser APIs"

echo ""
echo "2. Static Files Access Test"
echo "---------------------------"

# Test static CSS file
echo -n "Testing /static/ path access... "
static_response=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/static/admin/css/base.css")
if [ "$static_response" = "200" ] || [ "$static_response" = "304" ]; then
    echo -e "${GREEN}✓ OK${NC} (HTTP $static_response)"
else
    echo -e "${RED}✗ BLOCKED${NC} (HTTP $static_response)"
fi

# Test media path
echo -n "Testing /media/ path access... "
media_response=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/media/test.jpg")
if [ "$media_response" = "404" ] || [ "$media_response" = "200" ]; then
    echo -e "${GREEN}✓ OK${NC} (HTTP $media_response)"
else
    echo -e "${RED}✗ ERROR${NC} (HTTP $media_response)"
fi

echo ""
echo "3. CORS Configuration Test"
echo "--------------------------"

echo -n "Testing CORS headers... "
cors_response=$(curl -s -I -H "Origin: https://$DOMAIN" "https://$DOMAIN/api/" | grep -i "access-control-allow-origin")
if [ -n "$cors_response" ]; then
    echo -e "${GREEN}✓ OK${NC}"
    echo "  $cors_response"
else
    echo -e "${YELLOW}⚠ NOT SET${NC} (May be intentional for security)"
fi

echo ""
echo "4. Session Security Test"
echo "------------------------"

# Test cookie security
echo -n "Testing cookie security flags... "
cookie_header=$(curl -s -I "https://$DOMAIN/admin/login/" | grep -i "set-cookie")
if echo "$cookie_header" | grep -q "Secure.*HttpOnly.*SameSite"; then
    echo -e "${GREEN}✓ OK${NC}"
    echo "  Secure, HttpOnly, and SameSite flags present"
else
    echo -e "${YELLOW}⚠ CHECK${NC}"
    echo "  Cookie flags may need review"
fi

echo ""
echo "5. CSP Violation Test (Console Check)"
echo "-------------------------------------"
echo "To test for CSP violations:"
echo "1. Open https://$DOMAIN in Chrome/Firefox"
echo "2. Open Developer Console (F12)"
echo "3. Look for any CSP violation messages"
echo "4. Check Network tab for blocked resources"

echo ""
echo "6. Online Security Test"
echo "-----------------------"
echo "For comprehensive testing, visit:"
echo "  🔗 https://securityheaders.com/?q=$DOMAIN"
echo "  🔗 https://observatory.mozilla.org/analyze/$DOMAIN"

echo ""
echo "7. Summary"
echo "----------"

# Count successes
total_checks=8
passed_checks=$(check_header "Content-Security-Policy" "default-src" "" 2>/dev/null && echo 1 || echo 0)

if [ $passed_checks -eq $total_checks ]; then
    echo -e "${GREEN}✅ All security headers configured correctly!${NC}"
else
    echo -e "${YELLOW}⚠️  Some security headers need attention${NC}"
    echo "Review the audit report at: plans/security-audit-csp-headers.md"
fi

echo ""
echo "Test completed at: $(date)"