# Products Pagination API Documentation

## Overview
The `/products` endpoint now supports pagination to efficiently handle large product catalogs. This allows frontend applications to load products progressively and improves performance.

## Updated Endpoint

### GET /products

Returns paginated product list with optional filters.

**URL**: `/products`

**Method**: `GET`

**Query Parameters**:
- `page` (integer, optional): Page number to retrieve
  - Default: 1
  - Minimum: 1
- `page_size` (integer, optional): Number of items per page
  - Default: 20
  - Minimum: 1
  - Maximum: 100
- `category` (string, optional): Filter by product category
- `diet_type` (string, optional): Filter by diet type
- `min_discount` (float, optional): Minimum discount percentage (0-100)
- `max_days_until_expiry` (integer, optional): Maximum days until product expiry

### Response Format

```json
{
  "products": [
    {
      "product_id": "P0001",
      "name": "Amul Fresh Milk",
      "category": "Dairy",
      "brand": "Amul",
      "diet_type": "vegetarian",
      "allergens": ["dairy"],
      "shelf_life_days": 7,
      "packaging_date": "2025-01-10",
      "expiry_date": "2025-01-17",
      "days_until_expiry": 4,
      "weight_grams": 500,
      "price_mrp": 45.00,
      "cost_price": 20.25,
      "current_discount_percent": 10.0,
      "inventory_quantity": 150,
      "initial_inventory_quantity": 200,
      "total_cost": 4050.00,
      "revenue_generated": 2250.00,
      "store_location_lat": 28.6139,
      "store_location_lon": 77.2090,
      "is_dead_stock_risk": 0
    }
    // ... more products
  ],
  "total_items": 198,
  "total_pages": 10,
  "current_page": 1,
  "page_size": 20,
  "has_next": true,
  "has_previous": false
}
```

## Examples

### Basic Pagination

```bash
# Get first page (default)
curl "http://localhost:8000/products"

# Get second page
curl "http://localhost:8000/products?page=2"

# Get 50 items per page
curl "http://localhost:8000/products?page_size=50"
```

### Pagination with Filters

```bash
# Get Dairy products, 10 per page
curl "http://localhost:8000/products?category=Dairy&page_size=10"

# Get discounted products, page 3
curl "http://localhost:8000/products?min_discount=20&page=3"

# Complex filter with pagination
curl "http://localhost:8000/products?category=Fruits&max_days_until_expiry=7&page_size=5"
```

## Frontend Integration Examples

### React Hook Example

```javascript
import { useState, useEffect } from 'react';

function useProducts(filters = {}) {
  const [products, setProducts] = useState([]);
  const [pagination, setPagination] = useState({
    currentPage: 1,
    totalPages: 0,
    totalItems: 0,
    hasNext: false,
    hasPrevious: false
  });
  const [loading, setLoading] = useState(false);

  const fetchProducts = async (page = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page,
        page_size: 20,
        ...filters
      });
      
      const response = await fetch(`/api/products?${params}`);
      const data = await response.json();
      
      setProducts(data.products);
      setPagination({
        currentPage: data.current_page,
        totalPages: data.total_pages,
        totalItems: data.total_items,
        hasNext: data.has_next,
        hasPrevious: data.has_previous
      });
    } catch (error) {
      console.error('Error fetching products:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, []);

  return {
    products,
    pagination,
    loading,
    goToPage: fetchProducts
  };
}
```

### React Component Example

```jsx
function ProductList() {
  const { products, pagination, loading, goToPage } = useProducts({
    category: 'Snacks'
  });

  return (
    <div>
      <h2>Products (Total: {pagination.totalItems})</h2>
      
      {loading ? (
        <div>Loading...</div>
      ) : (
        <div className="product-grid">
          {products.map(product => (
            <ProductCard key={product.product_id} product={product} />
          ))}
        </div>
      )}
      
      <div className="pagination">
        <button 
          onClick={() => goToPage(pagination.currentPage - 1)}
          disabled={!pagination.hasPrevious}
        >
          Previous
        </button>
        
        <span>
          Page {pagination.currentPage} of {pagination.totalPages}
        </span>
        
        <button 
          onClick={() => goToPage(pagination.currentPage + 1)}
          disabled={!pagination.hasNext}
        >
          Next
        </button>
      </div>
    </div>
  );
}
```

## Performance Considerations

1. **Optimal Page Size**: 
   - Use 20-50 items for standard lists
   - Use 10-20 for mobile devices
   - Use 50-100 for data tables

2. **Caching**: 
   - Cache pages that have been loaded
   - Implement prefetching for next page

3. **Filtering**: 
   - Apply filters server-side for better performance
   - Reset to page 1 when filters change

## Migration Guide

If you're updating from the non-paginated version:

### Before (returns array):
```javascript
const response = await fetch('/api/products');
const products = await response.json(); // Array of products
```

### After (returns object with pagination):
```javascript
const response = await fetch('/api/products');
const data = await response.json();
const products = data.products; // Array is now in 'products' field
```

## Best Practices

1. **Always handle empty results**: Check if `products` array is empty
2. **Show loading states**: Especially important when changing pages
3. **Display total count**: Users like to know how many items exist
4. **Preserve filters**: Keep filter state when navigating pages
5. **URL state**: Consider storing page number in URL for shareable links

## Error Handling

The API validates pagination parameters:
- If `page` exceeds total pages, returns empty products array
- If `page_size` exceeds 100, it's capped at 100
- Invalid parameters return 422 Validation Error 