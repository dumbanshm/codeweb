# Weekly Expired Products API Endpoint

## Overview
The `/weekly_expired` endpoint provides analytics on products that expired during specific weeks. This helps track waste patterns, identify problem categories, and measure the financial impact of expired inventory.

## Endpoint Details

### GET /weekly_expired

Returns weekly data about expired products for the past N weeks.

**URL**: `/weekly_expired`

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
      "expired_count": 23,
      "expired_value": 15234.50,
      "expired_by_category": {
        "Dairy": 12,
        "Vegetables": 8,
        "Fruits": 3
      }
    },
    // ... more weeks
  ],
  "summary": {
    "total_expired_past_n_weeks": 145,
    "total_expired_value": 87532.25,
    "average_weekly_expired": 24.17,
    "average_weekly_expired_value": 14588.71,
    "weeks_analyzed": 6,
    "category_totals": {
      "Dairy": 68,
      "Vegetables": 45,
      "Fruits": 32
    }
  }
}
```

### Field Descriptions

**Week Data:**
- `week_start`: Start date of the week (Monday)
- `week_end`: End date of the week (Sunday)
- `week_number`: Week number (1 = most recent week)
- `expired_count`: Number of products that expired during this week
- `expired_value`: Total value of expired products (inventory_qty × price_mrp)
- `expired_by_category`: Breakdown of expired products by category

**Summary Data:**
- `total_expired_past_n_weeks`: Total products expired across all weeks
- `total_expired_value`: Total financial loss from expired products
- `average_weekly_expired`: Average number of products expiring per week
- `average_weekly_expired_value`: Average weekly financial loss
- `category_totals`: Total expired products by category across all weeks

## Example Usage

### Basic Request (Default 6 weeks)
```bash
curl http://localhost:8000/weekly_expired
```

### Extended Period (12 weeks)
```bash
curl "http://localhost:8000/weekly_expired?weeks_back=12"
```

### Python Example
```python
import requests
import matplotlib.pyplot as plt

# Fetch weekly expired data
response = requests.get("http://localhost:8000/weekly_expired?weeks_back=8")
data = response.json()

# Extract data for visualization
weeks = [f"Week {w['week_number']}" for w in data['weeks']]
expired_counts = [w['expired_count'] for w in data['weeks']]
expired_values = [w['expired_value'] for w in data['weeks']]

# Create visualization
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

# Expired count by week
ax1.bar(weeks, expired_counts, color='red', alpha=0.7)
ax1.set_title('Weekly Expired Products Count')
ax1.set_ylabel('Number of Products')

# Expired value by week
ax2.bar(weeks, expired_values, color='orange', alpha=0.7)
ax2.set_title('Weekly Financial Loss from Expired Products')
ax2.set_ylabel('Value (₹)')

plt.tight_layout()
plt.show()

# Print insights
print(f"Total waste in {data['summary']['weeks_analyzed']} weeks: {data['summary']['total_expired_past_n_weeks']} products")
print(f"Financial impact: ₹{data['summary']['total_expired_value']:,.2f}")
```

## Use Cases

### 1. **Waste Tracking Dashboard**
Create a dashboard showing:
- Weekly waste trends
- Category-wise waste distribution
- Financial impact over time
- Comparison with previous periods

### 2. **Category Analysis**
Identify which product categories have the highest waste:
```javascript
// Find problematic categories
const categoryWaste = data.summary.category_totals;
const sortedCategories = Object.entries(categoryWaste)
  .sort(([,a], [,b]) => b - a)
  .map(([category, count]) => ({
    category,
    count,
    percentage: (count / data.summary.total_expired_past_n_weeks * 100).toFixed(1)
  }));

console.log('Top waste categories:', sortedCategories.slice(0, 3));
```

### 3. **Trend Analysis**
Compare recent weeks with older weeks to identify trends:
```python
# Calculate trend
recent_weeks = sum(w['expired_count'] for w in data['weeks'][:4])
older_weeks = sum(w['expired_count'] for w in data['weeks'][4:8])
trend_percentage = ((recent_weeks - older_weeks) / older_weeks) * 100

if trend_percentage < -10:
    print("✅ Waste is decreasing!")
elif trend_percentage > 10:
    print("⚠️ Waste is increasing!")
else:
    print("→ Waste levels are stable")
```

### 4. **Financial Impact Report**
Generate reports showing:
- Total value lost to expiration
- Average weekly loss
- Cost per expired item
- ROI of waste reduction initiatives

## Integration with Other Endpoints

Combine with other endpoints for comprehensive analytics:

1. **With `/weekly_inventory`**: Calculate waste percentage
   ```python
   waste_rate = (expired_count / total_inventory_qty) * 100
   ```

2. **With `/products`**: Identify products frequently expiring
3. **With `/inventory_analytics`**: Compare waste value to profit margins

## Metrics and KPIs

Key metrics to track:
- **Waste Rate**: (Expired Products / Total Inventory) × 100
- **Financial Loss Rate**: (Expired Value / Total Inventory Value) × 100
- **Category Waste Distribution**: Which categories contribute most to waste
- **Trend Direction**: Is waste increasing or decreasing?
- **Average Days to Expiry**: For products that expired

## Best Practices

1. **Regular Monitoring**: Check weekly to catch trends early
2. **Set Alerts**: Notify when waste exceeds thresholds
3. **Category Focus**: Prioritize categories with highest waste
4. **Seasonal Analysis**: Compare same weeks across different months
5. **Action Plans**: Create specific actions for high-waste categories

## Example Dashboard Components

```jsx
// React component for waste trend
function WasteTrendChart({ weeks }) {
  const chartData = {
    labels: weeks.map(w => `Week ${w.week_number}`).reverse(),
    datasets: [
      {
        label: 'Expired Products',
        data: weeks.map(w => w.expired_count).reverse(),
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.5)',
      }
    ]
  };

  return (
    <div>
      <h3>Weekly Waste Trend</h3>
      <Line data={chartData} />
      <p>Total Loss: ₹{weeks.reduce((sum, w) => sum + w.expired_value, 0).toLocaleString()}</p>
    </div>
  );
}
``` 