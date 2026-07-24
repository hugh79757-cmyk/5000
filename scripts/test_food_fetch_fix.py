#!/usr/bin/env python3
"""
Test food fetch fix for Seoul Songpa-gu
"""

import sys
import os

# Add project root to path
sys.path.insert(0, '/Users/twinssn/Projects/5000')

from pipelines.travel.fetcher import fetch_food

def test_songpa_food_fetch():
    """Test food fetch for Seoul Songpa-gu specifically"""
    print("🔍 Testing food fetch for Seoul Songpa-gu...")
    
    try:
        # This will test the fetch function with the fix
        result = fetch_food()
        
        if result:
            print("✅ Food fetch successful!")
            print(f"   Items: {len(result.get('items', []))}")
            print(f"   Region: {result.get('display_region', 'N/A')}")
            print(f"   Source: {result.get('source_type', 'N/A')}")
            
            # Check if items are proper dictionaries
            items = result.get('items', [])
            dict_count = sum(1 for item in items if isinstance(item, dict))
            print(f"   Valid dictionary items: {dict_count}/{len(items)}")
            
            if dict_count == len(items) and len(items) > 0:
                print("✅ All items are proper dictionaries - FIX SUCCESSFUL!")
                return True
            else:
                print("❌ Some items are still not dictionaries")
                return False
        else:
            print("❌ Food fetch returned None")
            return False
            
    except Exception as e:
        print(f"❌ Error during food fetch: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_songpa_food_fetch()
    if success:
        print("\n🎉 Seoul Songpa-gu food fetch test PASSED")
    else:
        print("\n💥 Seoul Songpa-gu food fetch test FAILED")