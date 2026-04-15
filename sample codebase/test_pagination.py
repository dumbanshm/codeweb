import requests
import json

# Base URL for the API
BASE_URL = "http://localhost:8000"

def test_products_pagination():
    """Test the paginated products endpoint"""
    
    print("=" * 60)
    print("Testing Products Pagination")
    print("=" * 60)
    
    # Test 1: Default pagination (page 1, 20 items per page)
    print("\n1. Testing default pagination:")
    response = requests.get(f"{BASE_URL}/products")
    
    if response.status_code == 200:
        data = response.json()
        print(f"  Total products: {data['total_items']}")
        print(f"  Total pages: {data['total_pages']}")
        print(f"  Current page: {data['current_page']}")
        print(f"  Page size: {data['page_size']}")
        print(f"  Products on this page: {len(data['products'])}")
        print(f"  Has next page: {data['has_next']}")
        print(f"  Has previous page: {data['has_previous']}")
        
        if data['products']:
            print(f"  First product ID: {data['products'][0]['product_id']}")
            print(f"  Last product ID: {data['products'][-1]['product_id']}")
    else:
        print(f"  Error: {response.status_code}")
    
    # Test 2: Custom page size
    print("\n2. Testing custom page size (10 items per page):")
    response = requests.get(f"{BASE_URL}/products", params={"page_size": 10})
    
    if response.status_code == 200:
        data = response.json()
        print(f"  Total pages with page_size=10: {data['total_pages']}")
        print(f"  Products on this page: {len(data['products'])}")
    
    # Test 3: Navigate to page 2
    print("\n3. Testing page navigation (page 2):")
    response = requests.get(f"{BASE_URL}/products", params={"page": 2, "page_size": 10})
    
    if response.status_code == 200:
        data = response.json()
        print(f"  Current page: {data['current_page']}")
        print(f"  Products on this page: {len(data['products'])}")
        print(f"  Has previous: {data['has_previous']}")
        print(f"  Has next: {data['has_next']}")
        
        if data['products']:
            print(f"  First product ID on page 2: {data['products'][0]['product_id']}")
    
    # Test 4: Pagination with filters
    print("\n4. Testing pagination with filters (category=Dairy):")
    response = requests.get(f"{BASE_URL}/products", params={"category": "Dairy", "page_size": 5})
    
    if response.status_code == 200:
        data = response.json()
        print(f"  Total Dairy products: {data['total_items']}")
        print(f"  Total pages: {data['total_pages']}")
        print(f"  Products on this page: {len(data['products'])}")
        
        if data['products']:
            print(f"  Product categories: {[p['category'] for p in data['products']]}")
    
    # Test 5: Edge case - page beyond total pages
    print("\n5. Testing edge case (requesting page beyond total):")
    response = requests.get(f"{BASE_URL}/products", params={"page": 1000})
    
    if response.status_code == 200:
        data = response.json()
        print(f"  Current page: {data['current_page']}")
        print(f"  Products returned: {len(data['products'])}")
        print(f"  Has previous: {data['has_previous']}")
        print(f"  Has next: {data['has_next']}")
    
    # Test 6: Performance test with different page sizes
    print("\n6. Performance comparison:")
    for size in [10, 50, 100]:
        import time
        start = time.time()
        response = requests.get(f"{BASE_URL}/products", params={"page_size": size})
        end = time.time()
        
        if response.status_code == 200:
            print(f"  Page size {size}: {(end - start)*1000:.2f}ms")

def print_curl_examples():
    """Print example cURL commands"""
    print("\n" + "=" * 60)
    print("Example cURL Commands:")
    print("=" * 60)
    
    print("\n# Get first page with default size (20)")
    print('curl "http://localhost:8000/products"')
    
    print("\n# Get page 2 with 10 items per page")
    print('curl "http://localhost:8000/products?page=2&page_size=10"')
    
    print("\n# Get filtered products with pagination")
    print('curl "http://localhost:8000/products?category=Snacks&min_discount=20&page_size=5"')
    
    print("\n# Get all products in one page (max 100)")
    print('curl "http://localhost:8000/products?page_size=100"')

if __name__ == "__main__":
    test_products_pagination()
    print_curl_examples() 