import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class DynamicThresholdCalculator:
    """
    Calculates dynamic thresholds for dead stock prediction based on multiple factors
    """
    
    def __init__(self, products_df, transactions_df):
        self.products_df = products_df
        self.transactions_df = transactions_df
        self.category_thresholds = {}
        self.product_thresholds = {}
        
    def calculate_category_baseline_thresholds(self):
        """
        Calculate baseline thresholds for each product category based on 
        typical shelf life and sales patterns
        """
        # Group by category and calculate metrics
        category_metrics = self.products_df.groupby('category').agg({
            'shelf_life_days': 'mean',
            'product_id': 'count'
        }).rename(columns={'product_id': 'product_count'})
        
        # Calculate sales velocity by category
        sales_by_category = self.transactions_df.merge(
            self.products_df[['product_id', 'category']], 
            on='product_id'
        )
        
        category_velocity = sales_by_category.groupby('category').agg({
            'quantity': 'sum',
            'purchase_date': lambda x: (x.max() - x.min()).days + 1
        }).rename(columns={'purchase_date': 'days_active'})
        
        category_velocity['avg_daily_sales'] = (
            category_velocity['quantity'] / category_velocity['days_active']
        )
        
        # Merge metrics
        category_analysis = category_metrics.merge(
            category_velocity[['avg_daily_sales']], 
            left_index=True, 
            right_index=True,
            how='left'
        )
        
        # Calculate dynamic thresholds
        for category in category_analysis.index:
            avg_shelf_life = category_analysis.loc[category, 'shelf_life_days']
            avg_velocity = category_analysis.loc[category, 'avg_daily_sales']
            
            # Base threshold is 20% of average shelf life
            base_threshold = avg_shelf_life * 0.2
            
            # Adjust based on velocity (high velocity = shorter threshold)
            if avg_velocity > 10:  # High velocity
                velocity_factor = 0.7
            elif avg_velocity > 5:  # Medium velocity
                velocity_factor = 1.0
            else:  # Low velocity
                velocity_factor = 1.3
                
            self.category_thresholds[category] = int(base_threshold * velocity_factor)
            
        return self.category_thresholds
    
    def calculate_product_specific_threshold(self, product_id):
        """
        Calculate threshold for a specific product based on its individual characteristics
        """
        product = self.products_df[self.products_df['product_id'] == product_id].iloc[0]
        
        # Start with category baseline
        category = product['category']
        base_threshold = self.category_thresholds.get(category, 30)
        
        # Get product's sales history
        product_sales = self.transactions_df[
            self.transactions_df['product_id'] == product_id
        ]
        
        # Factor 1: Sales velocity
        if len(product_sales) > 0:
            days_on_market = (product_sales['purchase_date'].max() - 
                            product_sales['purchase_date'].min()).days + 1
            sales_velocity = len(product_sales) / days_on_market
            
            # Adjust threshold based on velocity
            if sales_velocity > 2:  # Very fast moving
                velocity_multiplier = 0.5
            elif sales_velocity > 1:  # Fast moving
                velocity_multiplier = 0.7
            elif sales_velocity > 0.5:  # Normal
                velocity_multiplier = 1.0
            else:  # Slow moving
                velocity_multiplier = 1.5
        else:
            # No sales history - be more conservative
            velocity_multiplier = 2.0
        
        # Factor 2: Price and margin (estimated)
        price = product['price_mrp']
        if price > 300:  # High-value items
            price_multiplier = 1.2  # Give more time to sell
        elif price < 100:  # Low-value items
            price_multiplier = 0.8  # Quicker turnover needed
        else:
            price_multiplier = 1.0
            
        # Factor 3: Current discount
        current_discount = product.get('current_discount_percent', 0)
        if current_discount > 30:  # Already heavily discounted
            discount_multiplier = 0.7  # More urgent
        elif current_discount > 0:
            discount_multiplier = 0.9
        else:
            discount_multiplier = 1.0
            
        # Factor 4: Seasonality (simplified - could be enhanced)
        current_month = datetime.now().month
        if category in ['Beverages'] and current_month in [6, 7, 8]:  # Summer
            seasonal_multiplier = 0.8  # Beverages sell faster in summer
        elif category in ['Snacks'] and current_month in [12, 1]:  # Holiday season
            seasonal_multiplier = 0.9
        else:
            seasonal_multiplier = 1.0
            
        # Calculate final threshold
        dynamic_threshold = (base_threshold * 
                           velocity_multiplier * 
                           price_multiplier * 
                           discount_multiplier * 
                           seasonal_multiplier)
        
        # Ensure threshold is within reasonable bounds
        min_threshold = max(3, product['shelf_life_days'] * 0.05)  # At least 5% of shelf life
        max_threshold = min(60, product['shelf_life_days'] * 0.4)  # At most 40% of shelf life
        
        final_threshold = int(np.clip(dynamic_threshold, min_threshold, max_threshold))
        
        return {
            'product_id': product_id,
            'category': category,
            'base_threshold': base_threshold,
            'dynamic_threshold': final_threshold,
            'factors': {
                'velocity_multiplier': velocity_multiplier,
                'price_multiplier': price_multiplier,
                'discount_multiplier': discount_multiplier,
                'seasonal_multiplier': seasonal_multiplier
            }
        }
    
    def calculate_all_thresholds(self):
        """
        Calculate dynamic thresholds for all products
        """
        # First calculate category baselines
        self.calculate_category_baseline_thresholds()
        
        # Then calculate product-specific thresholds
        thresholds = []
        for product_id in self.products_df['product_id'].unique():
            threshold_info = self.calculate_product_specific_threshold(product_id)
            thresholds.append(threshold_info)
            self.product_thresholds[product_id] = threshold_info['dynamic_threshold']
            
        return pd.DataFrame(thresholds)
    
    def get_threshold(self, product_id):
        """
        Get the dynamic threshold for a specific product
        """
        if product_id in self.product_thresholds:
            return self.product_thresholds[product_id]
        else:
            # Calculate on demand if not cached
            threshold_info = self.calculate_product_specific_threshold(product_id)
            self.product_thresholds[product_id] = threshold_info['dynamic_threshold']
            return threshold_info['dynamic_threshold']


# Enhanced dead stock detection with dynamic thresholds
def calculate_dead_stock_risk_dynamic(row, threshold_calculator):
    """
    Calculate if a product is at risk using dynamic thresholds
    """
    # Get dynamic threshold for this product
    threshold = threshold_calculator.get_threshold(row['product_id'])
    
    # If already expired
    if row['days_until_expiry'] <= 0:
        return 1
    
    # If within dynamic threshold
    if row['days_until_expiry'] <= threshold:
        # Check if sales velocity suggests it won't sell out
        if row['sales_velocity'] == 0:
            return 1
        
        # Project if current inventory will sell before expiry
        projected_sales = row['sales_velocity'] * row['days_until_expiry']
        
        # Assuming we need to sell at least 80% of typical inventory
        # This could also be made dynamic based on actual inventory levels
        if projected_sales < 80:
            return 1
    
    return 0


# Example usage
if __name__ == "__main__":
    # Assuming we have the dataframes loaded
    print("Dynamic Threshold Calculation Example")
    print("="*50)
    
    # Initialize calculator
    # calculator = DynamicThresholdCalculator(products_df, transactions_df)
    
    # Calculate all thresholds
    # threshold_df = calculator.calculate_all_thresholds()
    
    # Show example thresholds
    # print("\nSample Dynamic Thresholds:")
    # print(threshold_df.head(10))
    
    # Show how thresholds vary by category
    # print("\nThresholds by Category:")
    # print(calculator.category_thresholds)
    
    print("\nKey Benefits of Dynamic Thresholds:")
    print("1. Adapts to product-specific shelf life")
    print("2. Considers sales velocity patterns")
    print("3. Accounts for price and margin factors")
    print("4. Adjusts for seasonal variations")
    print("5. Responds to current discount levels") 