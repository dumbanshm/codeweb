# Dynamic Pricing API Feature

## Overview

The API now supports dynamic pricing calculations for products based on urgency scores, dead stock risk, and sales velocity. When you add `?dynamic=true` to supported endpoints, the response includes intelligent pricing recommendations to minimize waste and maximize revenue.

## Supported Endpoints

### 1. Recommendations (`/recommendations/{user_id}`)

Get personalized product recommendations with dynamic pricing:

```bash
GET /recommendations/U0000?dynamic=true
```

Response includes a `dynamic_pricing` object for each recommendation:

```json
{
  "product_id": "P0022",
  "product_name": "Nestle Classic Yogurt",
  "days_until_expiry": 1,
  "price": 407.17,
  "current_discount_percent": 40,
  "dynamic_pricing": {
    "urgency_score": 1.0,
    "current_discount": 40,
    "recommended_discount": 40,
    "discount_increase": 0,
    "reasoning": "Critical expiry window, High dead stock risk, High urgency score",
    "current_price": 244.30,
    "recommended_price": 244.30,
    "potential_savings": 0
  }
}
```

### 2. Dead Stock Risk (`/dead_stock_risk`)

Get at-risk products with pricing recommendations:

```bash
GET /dead_stock_risk?dynamic=true&min_risk_level=HIGH
```

### 3. Products (`/products`)

Browse products with dynamic pricing suggestions:

```bash
GET /products?dynamic=true&max_days_until_expiry=7&page_size=10
```

## Dynamic Pricing Fields

When `dynamic=true`, each product includes these additional fields:

| Field | Type | Description |
|-------|------|-------------|
| `urgency_score` | float | 0.0-1.0 score indicating pricing urgency |
| `current_discount` | float | Current discount percentage |
| `recommended_discount` | float | ML-recommended discount percentage |
| `discount_increase` | float | Additional discount needed |
| `reasoning` | string | Human-readable explanation for the recommendation |
| `current_price` | float | Current selling price after discount |
| `recommended_price` | float | Recommended selling price |
| `potential_savings` | float | Customer savings with recommended pricing |

## Pricing Logic

The dynamic pricing engine considers multiple factors:

1. **Days Until Expiry**: Products closer to expiry get higher urgency scores
2. **Sales Velocity**: Slow-moving products get higher discounts
3. **Dead Stock Risk**: At-risk products get aggressive pricing
4. **Inventory Levels**: High inventory with low sales triggers discounts
5. **Category Thresholds**: Different categories have different risk thresholds

## Urgency Score Calculation

- **1.0** (Maximum): Expires in ≤3 days, high dead stock risk
- **0.75-0.99**: Expires in 4-7 days, medium-high risk
- **0.50-0.74**: Expires in 8-14 days, medium risk
- **0.25-0.49**: Expires in 15-30 days, low-medium risk
- **0.0-0.24**: Expires in >30 days or healthy sales velocity

## Discount Recommendations

Based on urgency score:
- **Urgency ≥ 0.9**: Up to 60% discount
- **Urgency ≥ 0.7**: Up to 50% discount
- **Urgency ≥ 0.5**: Up to 40% discount
- **Urgency ≥ 0.3**: Up to 30% discount
- **Urgency < 0.3**: Standard pricing (0-20%)

## Example Usage

### Get expiring products with dynamic pricing:
```python
import requests

# Get products expiring in 7 days with pricing recommendations
response = requests.get(
    "http://localhost:8000/products",
    params={
        "dynamic": True,
        "max_days_until_expiry": 7,
        "page_size": 20
    }
)

products = response.json()["products"]
for product in products:
    if product.get("dynamic_pricing"):
        dp = product["dynamic_pricing"]
        print(f"{product['name']}:")
        print(f"  Current: ₹{dp['current_price']:.2f} ({dp['current_discount']}% off)")
        print(f"  Recommended: ₹{dp['recommended_price']:.2f} ({dp['recommended_discount']}% off)")
        print(f"  Reason: {dp['reasoning']}")
```

### Get personalized recommendations with pricing:
```python
# Get recommendations for user U0000
response = requests.get(
    "http://localhost:8000/recommendations/U0000",
    params={"dynamic": True, "n": 10}
)

recommendations = response.json()["recommendations"]
total_savings = sum(r["dynamic_pricing"]["potential_savings"] for r in recommendations)
print(f"Total potential savings: ₹{total_savings:.2f}")
```

## Benefits

1. **Reduce Waste**: Aggressive pricing for products about to expire
2. **Maximize Revenue**: Sell products before they become dead stock
3. **Customer Value**: Offer better deals on products that need to move
4. **Intelligent Pricing**: ML-based recommendations, not just rules
5. **Real-time Adaptation**: Prices adjust based on current inventory and sales

## Performance

Dynamic pricing adds minimal overhead:
- ~50-100ms additional processing time
- Calculations use pre-computed metrics from database views
- ML models are loaded once at startup
- Pricing engine uses efficient vectorized operations 