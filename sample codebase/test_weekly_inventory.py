import requests
import json
from datetime import datetime, timedelta

# Base URL for the API
BASE_URL = "http://localhost:8000"

def test_weekly_inventory():
    """Test the weekly inventory endpoint"""
    
    print("=" * 60)
    print("Testing Weekly Inventory Endpoint")
    print("=" * 60)
    
    # Test with default 6 weeks
    print("\n1. Testing with default 6 weeks:")
    response = requests.get(f"{BASE_URL}/weekly_inventory")
    
    if response.status_code == 200:
        data = response.json()
        
        print("\nWeekly Inventory Data:")
        print("-" * 60)
        
        # Display each week's data
        for week in data['weeks']:
            print(f"\nWeek {week['week_number']} ({week['week_start']} to {week['week_end']}):")
            print(f"  - Alive products: {week['alive_products_count']}")
            print(f"  - Total inventory: {week['total_inventory_qty']:,} units")
            print(f"  - Sold quantity: {week['sold_inventory_qty']:,} units")
            
            # Calculate utilization rate
            if week['total_inventory_qty'] > 0:
                utilization = (week['sold_inventory_qty'] / week['total_inventory_qty']) * 100
                print(f"  - Inventory utilization: {utilization:.2f}%")
        
        # Display summary
        print("\n" + "=" * 60)
        print("Summary Statistics:")
        print("-" * 60)
        print(f"Total sold in past {data['summary']['weeks_analyzed']} weeks: {data['summary']['total_sold_past_n_weeks']:,} units")
        print(f"Average weekly sales: {data['summary']['average_weekly_sales']:,} units")
        print(f"Current total inventory: {data['summary']['current_total_inventory']:,} units")
        
        # Calculate weeks of inventory remaining
        if data['summary']['average_weekly_sales'] > 0:
            weeks_remaining = data['summary']['current_total_inventory'] / data['summary']['average_weekly_sales']
            print(f"Estimated weeks of inventory remaining: {weeks_remaining:.1f}")
            
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
    
    # Test with different number of weeks
    print("\n" + "=" * 60)
    print("\n2. Testing with 4 weeks:")
    response = requests.get(f"{BASE_URL}/weekly_inventory?weeks_back=4")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Successfully retrieved data for {len(data['weeks'])} weeks")
        print(f"Total sold: {data['summary']['total_sold_past_n_weeks']:,} units")
    else:
        print(f"Error: {response.status_code}")

    # Test with cost metrics
    print("\n" + "=" * 60)
    print("\n3. Testing with cost metrics:")
    response = requests.get(f"{BASE_URL}/weekly_inventory?weeks_back=2&metric_type=cost")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Successfully retrieved cost data for {len(data['weeks'])} weeks")
        print(f"Metric Type: {data['metric_type']}")
        print(f"Unit Label: {data['summary']['unit_label']}")
        print(f"Total inventory value: ₹{data['summary']['current_total_inventory']:,.2f}")
        print(f"Average weekly sales value: ₹{data['summary']['average_weekly_sales']:,.2f}")
    else:
        print(f"Error: {response.status_code}")
    
    # Test API documentation
    print("\n" + "=" * 60)
    print("\n4. API Endpoint Information:")
    print(f"Endpoint: GET /weekly_inventory")
    print(f"Parameters:")
    print(f"  - weeks_back (optional): Number of weeks to analyze (default: 6, min: 1, max: 52)")
    print(f"  - metric_type (optional): 'qty' or 'cost' (default: 'qty')")
    print(f"\nExample usage:")
    print(f"  curl '{BASE_URL}/weekly_inventory?weeks_back=8'")
    print(f"  curl '{BASE_URL}/weekly_inventory?metric_type=cost'")

if __name__ == "__main__":
    test_weekly_inventory() 