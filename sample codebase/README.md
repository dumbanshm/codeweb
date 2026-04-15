# Unified Waste Reduction System

A comprehensive system for reducing waste in retail environments through intelligent product recommendations, dynamic dead stock prediction, and automated discount management.

## Features

- **Hybrid Recommendation System**: Combines content-based and collaborative filtering approaches
- **Dynamic Threshold Calculation**: Adapts dead stock thresholds based on product category, sales velocity, pricing, and seasonality
- **Automated Discount Management**: Dynamically updates discounts for at-risk products (up to 50% in 2.5% increments)
- **Dietary & Allergy Filtering**: Ensures recommendations respect user dietary preferences and allergies
- **Urgency-Based Scoring**: Prioritizes products nearing expiry
- **Comprehensive Analytics**: Provides insights into product risk levels and waste reduction strategies
- **Robust Error Handling**: Handles edge cases like missing products and empty recommendations
- **Real-time Risk Assessment**: Continuously monitors and flags products at risk of becoming dead stock
- **Continuous Risk Score Export**: Exports both threshold and a continuous risk score for each product via a dedicated DataFrame for fast API and reporting

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure your datasets are in the `datasets/` folder:
   - `fake_users.csv`
   - `fake_products.csv`
   - `fake_transactions.csv`

### Virtual Environment (Mac/Linux)

To activate your Python virtual environment:
```bash
source venv/bin/activate
```
To deactivate:
```bash
deactivate
```

## Usage

### Quick Start

Run the driver code to see the system in action:

```bash
python run_waste_reduction_system.py
```

This will:
1. Load and analyze the datasets
2. Initialize the recommendation system
3. Build content and collaborative filtering models
4. Perform dead stock risk analysis
5. **Automatically update discounts for at-risk products**
6. Generate sample recommendations for users
7. Display waste reduction strategies with updated discount information
8. **Export a separate DataFrame with product_id, threshold, and risk_score for API and reporting**

### Programmatic Usage

```python
from unified_waste_reduction_system import UnifiedRecommendationSystem
import pandas as pd

# Load your data
users_df = pd.read_csv('datasets/fake_users.csv')
products_df = pd.read_csv('datasets/fake_products.csv')
transactions_df = pd.read_csv('datasets/fake_transactions.csv')

# Initialize the system
system = UnifiedRecommendationSystem(users_df, products_df, transactions_df)

# Build models
system.build_content_similarity_matrix()
system.build_collaborative_filtering_model()

# Update discounts for at-risk products
system.update_discounts_for_at_risk_products()

# Build risk DataFrame (threshold and risk_score)
system.build_product_risk_df()

# Get recommendations for a user (now includes updated discounts)
recommendations = system.get_hybrid_recommendations(
    user_id='U0001',
    n_recommendations=10,
    content_weight=0.4,
    collaborative_weight=0.6
)

# Access risk DataFrame
risk_df = system.product_risk_df
```

## System Components

### 1. Dynamic Threshold Calculator
- Calculates category-based baseline thresholds
- Adjusts thresholds based on:
  - Sales velocity
  - Product pricing
  - Current discount levels
  - Seasonal factors

### 2. Automated Discount Manager
- **Threshold-Based Updates**: Increases discounts for products crossing their dynamic threshold
- **Incremental Discounting**: Updates in 2.5% increments, capped at 50%
- **Risk-Aware Logic**: Only updates discounts for products flagged as at risk
- **Real-time Integration**: Updates are reflected immediately in all recommendation outputs

### 3. Recommendation Engine
- **Content-Based**: Finds similar products based on features
- **Collaborative Filtering**: Uses user purchase patterns
- **Hybrid Approach**: Combines both methods for best results
- **Updated Discount Integration**: All recommendations show current, dynamically-updated discounts

### 4. Dead Stock Risk Analysis
- Identifies products at risk of becoming dead stock
- Provides actionable insights for inventory management
- Suggests discount strategies with real-time discount updates
- **Enhanced Reporting**: Shows both original and updated discount information
- **Exports a separate DataFrame with threshold and risk_score for each product**

## Key Improvements

### Error Handling
- **Robust Product Lookups**: Handles missing products gracefully
- **Empty Recommendation Handling**: Provides fallbacks when no recommendations are available
- **Data Integrity**: Maintains separate filtered and unfiltered product datasets for different use cases

### Discount Management
- **Smart Threshold Logic**: Only applies discounts when products cross their calculated threshold
- **Business Logic Preservation**: Maintains original discount values in dataset while updating in-memory calculations
- **Incremental Updates**: Prevents over-discounting with controlled 2.5% increments

### Performance Optimizations
- **Cached Similarity Matrix**: Rebuilds only when discounts are updated
- **Efficient Data Structures**: Uses optimized DataFrames for fast lookups
- **Memory Management**: Cleans up expired products while preserving historical data

## Output Example

The driver code provides comprehensive output including:

1. **Data Analysis**: Overview of users, products, and transactions
2. **Dead Stock Risk Analysis**: Products at risk with dynamic thresholds and **updated discounts**
3. **Personalized Recommendations**: Tailored suggestions with **current discount information**
4. **Waste Reduction Strategies**: Actionable insights with **automated discount recommendations**
5. **Top 10 At-Risk Products**: Real-time list with **updated discount percentages**
6. **Risk Data Export**: API and reporting now include both threshold and continuous risk score for each product

## Customization

You can customize the system behavior by adjusting:

- Recommendation weights (content vs collaborative)
- Number of recommendations
- Threshold calculation parameters
- Urgency boost factors
- **Discount increment size** (currently 2.5%)
- **Maximum discount cap** (currently 50%)

## Data Requirements

The system expects CSV files with the following structure:

- **users.csv**: user_id, diet_type, allergies
- **products.csv**: product_id, name, category, price_mrp, expiry_date, packaging_date, diet_type, allergens, current_discount_percent, etc.
- **transactions.csv**: user_id, product_id, quantity, purchase_date, discount_percent, user_engaged_with_deal

## API Integration

The system includes a FastAPI server (`main.py`) for production deployment:

```bash
uvicorn main:app --reload
```

Available endpoints:
- `GET /recommendations/{user_id}`: Get personalized recommendations
- `GET /dead_stock_risk`: Get products at risk of becoming dead stock (now includes threshold and risk_score)

## Technical Architecture

- **Modular Design**: Separate components for thresholds, recommendations, and discount management
- **Data Persistence**: Supports both CSV and database backends
- **Scalable**: Designed to handle large product catalogs and user bases
- **Extensible**: Easy to add new recommendation algorithms or discount strategies 