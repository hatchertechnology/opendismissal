#!/usr/bin/env python
"""
Test script to verify Django admin cache control headers
Run this to test the admin caching fixes programmatically
"""

import requests
import sys
from datetime import datetime

def test_admin_cache_headers():
    """Test that admin pages have proper no-cache headers"""
    
    print("Testing Django Admin Cache Control Headers")
    print("=" * 50)
    
    # Test URLs
    urls = [
        "http://localhost:8010/admin/",
        "http://localhost:8010/admin/dissmissal/student/",
        "http://localhost:8010/admin/dissmissal/student/add/",
    ]
    
    # Expected headers
    expected_headers = {
        'Cache-Control': ['no-cache', 'no-store', 'must-revalidate'],
        'Pragma': 'no-cache',
        'Expires': '0'
    }
    
    for url in urls:
        print(f"\nTesting: {url}")
        print("-" * 30)
        
        try:
            # Make request (this will likely get redirected to login)
            response = requests.get(url, allow_redirects=False, timeout=5)
            
            print(f"Status Code: {response.status_code}")
            
            # Check cache control headers
            cache_control = response.headers.get('Cache-Control', '')
            pragma = response.headers.get('Pragma', '')
            expires = response.headers.get('Expires', '')
            
            print(f"Cache-Control: {cache_control}")
            print(f"Pragma: {pragma}")
            print(f"Expires: {expires}")
            
            # Verify headers
            cache_ok = all(header in cache_control.lower() for header in expected_headers['Cache-Control'])
            pragma_ok = expected_headers['Pragma'] in pragma.lower()
            expires_ok = expected_headers['Expires'] in expires or 'max-age=0' in cache_control.lower()
            
            if cache_ok and (pragma_ok or 'no-cache' in cache_control):
                print("✅ Cache headers look good!")
            else:
                print("❌ Cache headers may need attention")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection error: {e}")
            print("Make sure the Django development server is running on localhost:8010")
    
    print(f"\nTest completed at {datetime.now()}")
    print("\nNote: Authentication may be required for full admin access")
    print("The headers shown are for the public/redirect responses")

if __name__ == "__main__":
    test_admin_cache_headers()