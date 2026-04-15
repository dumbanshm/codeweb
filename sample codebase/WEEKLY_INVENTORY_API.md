# Weekly Inventory API Endpoint

## Overview
The `/weekly_inventory` endpoint provides analytics on inventory levels and sales for products that were "alive" (packaged and not expired) during specific weeks.

## Endpoint Details

### GET /weekly_inventory

Returns weekly inventory data for the past N weeks, showing total inventory quantities and sold quantities.

**URL**: `/weekly_inventory`

**Method**: `GET`

**Query Parameters**:
- `weeks_back` (optional, integer): Number of weeks to analyze
  - Default: 6
  - Minimum: 1
  - Maximum: 52

### Response Format

```json
{
  "weeks": [
    {
      "week_start": "2025-01-06",
      "week_end": "2025-01-12",
      "week_number": 1,
      "total_inventory_qty": 15234,
      "sold_inventory_qty": 523,
      "alive_products_count": 142
    },
    // ... more weeks
  ],
  "summary": {
    "total_sold_past_n_weeks": 3142,
    "average_weekly_sales": 523.67,
    "current_total_inventory": 14892,
    "weeks_analyzed": 6
  }
}
```

### Product "Alive" Definition
A product is considered "alive" during a week if:
- It was packaged **before or during** that week (packaging_date ≤ week_end)
- It expires **after or during** that week (expiry_date ≥ week_start)

This ensures we only count inventory that was actually available for sale during each week.

## Example Usage

### Basic Request (Default 6 weeks)
```bash
curl http://localhost:8000/weekly_inventory
```

### Custom Time Period (12 weeks)
```bash
curl "http://localhost:8000/weekly_inventory?weeks_back=12"
```

### Python Example
```python
import requests

response = requests.get("http://localhost:8000/weekly_inventory", params={"weeks_back": 8})
data = response.json()

# Analyze inventory utilization
for week in data['weeks']:
    utilization = (week['sold_inventory_qty'] / week['total_inventory_qty']) * 100
    print(f"Week {week['week_number']}: {utilization:.2f}% inventory utilization")
```

## Use Cases

1. **Inventory Planning**: Understand weekly inventory patterns to optimize ordering
2. **Sales Trends**: Track weekly sales to identify seasonal patterns
3. **Waste Reduction**: Monitor inventory utilization rates to reduce waste
4. **Stock Optimization**: Calculate optimal inventory levels based on average sales

## Key Metrics Provided

- **Total Inventory Quantity**: Sum of all inventory for products alive during the week
- **Sold Inventory Quantity**: Total units sold during the week
- **Alive Products Count**: Number of products that were available for sale
- **Inventory Utilization Rate**: Sold quantity / Total inventory (calculate client-side)
- **Weeks of Inventory Remaining**: Current inventory / Average weekly sales

## Testing the Endpoint

Run the test script:
```bash
python test_weekly_inventory.py
```

This will show:
- Weekly breakdown of inventory and sales
- Inventory utilization percentages
- Summary statistics
- Estimated weeks of remaining inventory 