# Metric Types API Feature

## Overview
Both `/weekly_inventory` and `/weekly_expired` endpoints now support a `metric_type` query parameter that allows you to switch between quantity-based and cost-based metrics. This provides flexibility for different analytical needs - operational vs financial analysis.

## Query Parameter

### metric_type
- **Type**: string
- **Values**: `"qty"` or `"cost"`
- **Default**: `"qty"`
- **Description**: Determines whether metrics are calculated based on quantity (units) or monetary value (cost)

## Updated Endpoints

### GET /weekly_inventory
```
/weekly_inventory?weeks_back=6&metric_type=cost
```

### GET /weekly_expired
```
/weekly_expired?weeks_back=6&metric_type=cost
```

## Response Changes

### When metric_type="qty" (Default)
- `total_inventory`: Sum of inventory quantities
- `sold_inventory`: Sum of sold quantities
- `expired_by_category`: Count of expired products per category
- `unit_label`: "units"

### When metric_type="cost"
- `total_inventory`: Sum of (inventory_quantity × cost_price)
- `sold_inventory`: Sum of (sold_quantity × cost_price)
- `expired_by_category`: Sum of cost values per category
- `unit_label`: "₹"

## Cost Price Calculation
- Uses `cost_price` field if available
- Falls back to 45% of `price_mrp` if cost_price is null
- This ensures consistent cost calculations across all products

## Example Responses

### Quantity Metrics (metric_type="qty")
```json
{
  "weeks": [
    {
      "week_start": "2025-01-06",
      "week_end": "2025-01-12",
      "week_number": 1,
      "total_inventory": 51318.0,
      "sold_inventory": 446.0,
      "alive_products_count": 208,
      "metric_type": "qty"
    }
  ],
  "summary": {
    "total_sold_past_n_weeks": 1535.0,
    "average_weekly_sales": 255.83,
    "current_total_inventory": 48812.0,
    "weeks_analyzed": 6,
    "metric_type": "qty",
    "unit_label": "units"
  },
  "metric_type": "qty"
}
```

### Cost Metrics (metric_type="cost")
```json
{
  "weeks": [
    {
      "week_start": "2025-01-06",
      "week_end": "2025-01-12",
      "week_number": 1,
      "total_inventory": 2315670.45,
      "sold_inventory": 20145.30,
      "alive_products_count": 208,
      "metric_type": "cost"
    }
  ],
  "summary": {
    "total_sold_past_n_weeks": 69234.75,
    "average_weekly_sales": 11539.13,
    "current_total_inventory": 2201456.80,
    "weeks_analyzed": 6,
    "metric_type": "cost",
    "unit_label": "₹"
  },
  "metric_type": "cost"
}
```

## Use Cases

### 1. Financial Analysis
Use `metric_type=cost` to:
- Calculate inventory holding costs
- Analyze financial impact of waste
- Determine inventory turnover rates
- Budget planning and forecasting

### 2. Operational Analysis
Use `metric_type=qty` to:
- Track unit movement
- Plan storage capacity
- Optimize ordering quantities
- Monitor product velocity

### 3. Comparative Analysis
Compare both metrics to identify:
- High-value vs high-volume waste
- Cost efficiency of inventory management
- Product profitability patterns

## Code Examples

### JavaScript/React
```javascript
// Fetch cost-based inventory data
const fetchInventoryCost = async () => {
  const response = await fetch('/api/weekly_inventory?metric_type=cost');
  const data = await response.json();
  
  // Calculate inventory turnover
  const annualSales = data.summary.average_weekly_sales * 52;
  const turnoverRate = annualSales / data.summary.current_total_inventory;
  
  return { ...data, turnoverRate };
};

// Compare metrics
const compareMetrics = async () => {
  const [qtyData, costData] = await Promise.all([
    fetch('/api/weekly_inventory?metric_type=qty').then(r => r.json()),
    fetch('/api/weekly_inventory?metric_type=cost').then(r => r.json())
  ]);
  
  const avgUnitCost = costData.summary.current_total_inventory / 
                      qtyData.summary.current_total_inventory;
  
  return { qtyData, costData, avgUnitCost };
};
```

### Python Analysis
```python
import requests
import pandas as pd

# Fetch both metric types
qty_response = requests.get("http://localhost:8000/weekly_inventory?metric_type=qty")
cost_response = requests.get("http://localhost:8000/weekly_inventory?metric_type=cost")

qty_data = qty_response.json()
cost_data = cost_response.json()

# Create comparison DataFrame
weeks_comparison = []
for i, (q_week, c_week) in enumerate(zip(qty_data['weeks'], cost_data['weeks'])):
    weeks_comparison.append({
        'week': q_week['week_number'],
        'inventory_units': q_week['total_inventory'],
        'inventory_cost': c_week['total_inventory'],
        'avg_unit_cost': c_week['total_inventory'] / q_week['total_inventory'] if q_week['total_inventory'] > 0 else 0,
        'sold_units': q_week['sold_inventory'],
        'sold_cost': c_week['sold_inventory']
    })

df = pd.DataFrame(weeks_comparison)
print(df)
```

## Dashboard Integration

### KPI Cards
```jsx
function InventoryKPIs({ metricType }) {
  const [data, setData] = useState(null);
  
  useEffect(() => {
    fetch(`/api/weekly_inventory?weeks_back=1&metric_type=${metricType}`)
      .then(res => res.json())
      .then(setData);
  }, [metricType]);
  
  if (!data) return <Loading />;
  
  return (
    <div className="kpi-grid">
      <KPICard
        title="Current Inventory"
        value={data.summary.current_total_inventory}
        unit={data.summary.unit_label}
        format={metricType === 'cost' ? 'currency' : 'number'}
      />
      <KPICard
        title="Weekly Average"
        value={data.summary.average_weekly_sales}
        unit={data.summary.unit_label}
        format={metricType === 'cost' ? 'currency' : 'number'}
      />
    </div>
  );
}
```

### Metric Toggle
```jsx
function MetricToggle({ value, onChange }) {
  return (
    <div className="metric-toggle">
      <button
        className={value === 'qty' ? 'active' : ''}
        onClick={() => onChange('qty')}
      >
        Quantity
      </button>
      <button
        className={value === 'cost' ? 'active' : ''}
        onClick={() => onChange('cost')}
      >
        Cost
      </button>
    </div>
  );
}
```

## Best Practices

1. **Default to Quantity**: For operational dashboards, quantity metrics are usually more intuitive
2. **Financial Reports**: Switch to cost metrics for financial reporting and ROI calculations
3. **Cache Results**: Cost calculations are more intensive, consider caching results
4. **Consistent Comparison**: When comparing periods, use the same metric_type
5. **User Preference**: Store user's preferred metric_type in their profile

## Performance Considerations

- **Cost metrics** require additional calculations (multiplication with cost_price)
- Consider adding database indexes on `cost_price` and `price_mrp` columns
- For large datasets, cost calculations may be slower than quantity
- Implement caching for frequently accessed metric combinations 