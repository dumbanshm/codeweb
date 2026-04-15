# Inventory Summary API Endpoint

## Overview

The `/inventory_summary` endpoint provides a real-time snapshot of your entire inventory, categorized by status (alive, at-risk, expired) with all costs calculated as `quantity × cost_price`.

## Endpoint Details

### GET /inventory_summary

Returns comprehensive inventory metrics with costs based on cost price (not MRP).

**URL**: `/inventory_summary`

**Method**: `GET`

**Query Parameters**:
- `include_category_breakdown` (optional, boolean): Include category-wise breakdown
  - Default: false

### Response Format

```json
{
  "alive_products_count": 142,
  "alive_inventory_cost": 325480.50,
  "alive_inventory_qty": 15234,
  "at_risk_products_count": 23,
  "at_risk_inventory_cost": 45670.25,
  "at_risk_inventory_qty": 2150,
  "expired_products_count": 8,
  "expired_inventory_cost": 12340.00,
  "expired_inventory_qty": 450,
  "total_products_count": 173,
  "total_inventory_cost": 383490.75,
  "total_inventory_qty": 17834,
  "expiring_within_week_count": 18,
  "expiring_within_week_cost": 35420.50,
  "at_risk_cost_percentage": 11.91,
  "expired_cost_percentage": 3.22,
  "by_category": null
}
```

### With Category Breakdown

When `include_category_breakdown=true`:

```json
{
  // ... all above fields plus:
  "by_category": [
    {
      "category": "Dairy",
      "alive_products_count": 15,
      "alive_inventory_cost": 45230.50,
      "at_risk_products_count": 5,
      "at_risk_inventory_cost": 8920.00,
      "expired_products_count": 2,
      "expired_inventory_cost": 3450.00,
      "total_inventory_cost": 57600.50
    },
    // ... more categories
  ]
}
```

## Status Definitions

1. **Alive Products**: 
   - Not expired (`days_until_expiry >= 0`)
   - Not flagged as dead stock risk
   - Available for sale

2. **At-Risk Products**:
   - Not expired but flagged as dead stock risk
   - Criteria: Low sales velocity, expiring soon, or high inventory with no sales

3. **Expired Products**:
   - Past expiry date (`days_until_expiry < 0`)
   - Should be removed from inventory

## Cost Calculation

All costs are calculated as:
```
cost = inventory_quantity × cost_price
```

Where `cost_price` is the purchase/procurement price, not the MRP (selling price).

## Usage Examples

### Basic Summary
```bash
curl "http://localhost:8000/inventory_summary"
```

### With Category Breakdown
```bash
curl "http://localhost:8000/inventory_summary?include_category_breakdown=true"
```

### Python Example
```python
import requests

# Get inventory summary
response = requests.get("http://localhost:8000/inventory_summary")
data = response.json()

# Calculate key metrics
total_value = data['total_inventory_cost']
at_risk_value = data['at_risk_inventory_cost']
expired_value = data['expired_inventory_cost']
healthy_value = data['alive_inventory_cost']

print(f"Total Inventory Value: ₹{total_value:,.2f}")
print(f"Healthy Inventory: ₹{healthy_value:,.2f} ({healthy_value/total_value*100:.1f}%)")
print(f"At Risk: ₹{at_risk_value:,.2f} ({data['at_risk_cost_percentage']}%)")
print(f"Expired: ₹{expired_value:,.2f} ({data['expired_cost_percentage']}%)")

# Alert if too much value at risk
if data['at_risk_cost_percentage'] > 15:
    print("⚠️ WARNING: Over 15% of inventory value is at risk!")
```

## Dashboard Integration

This endpoint is perfect for:

1. **Executive Dashboards**: Show total inventory health at a glance
2. **Alerts**: Trigger when at-risk percentage exceeds thresholds
3. **Financial Reports**: Track inventory value by status
4. **Category Analysis**: Identify problematic categories

## Performance

- Uses pre-computed database view `inventory_summary`
- Response time: ~20-50ms
- Real-time data (view updates automatically)
- No looping or aggregation in application layer

## Database Views Created

1. **inventory_summary**: Main summary view with all metrics
2. **inventory_summary_by_category**: Category-wise breakdown

To create these views, run:
```sql
-- Execute the SQL in scripts/create_inventory_summary_view.sql
``` 