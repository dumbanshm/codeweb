import requests
import json
from datetime import datetime, timedelta

# Base URL for the API
BASE_URL = "http://localhost:8000"

def test_weekly_expired():
    """Test the weekly expired products endpoint"""
    
    print("=" * 60)
    print("Testing Weekly Expired Products Endpoint")
    print("=" * 60)
    
    # Test with default 6 weeks
    print("\n1. Testing with default 6 weeks:")
    response = requests.get(f"{BASE_URL}/weekly_expired")
    
    if response.status_code == 200:
        data = response.json()
        
        print("\nWeekly Expired Products Data:")
        print("-" * 60)
        
        # Display each week's data
        for week in data['weeks']:
            print(f"\nWeek {week['week_number']} ({week['week_start']} to {week['week_end']}):")
            print(f"  - Expired products: {week['expired_count']}")
            print(f"  - Total value lost: ₹{week['expired_value']:,.2f}")
            
            if week['expired_by_category']:
                print("  - By category:")
                for category, count in week['expired_by_category'].items():
                    print(f"    - {category}: {count} products")
            
            # Calculate waste percentage if we have inventory data
            if week['expired_count'] > 0:
                print(f"  - Average value per expired product: ₹{week['expired_value']/week['expired_count']:,.2f}")
        
        # Display summary
        print("\n" + "=" * 60)
        print("Summary Statistics:")
        print("-" * 60)
        print(f"Total expired in past {data['summary']['weeks_analyzed']} weeks: {data['summary']['total_expired_past_n_weeks']} products")
        print(f"Total value lost: ₹{data['summary']['total_expired_value']:,.2f}")
        print(f"Average weekly expired: {data['summary']['average_weekly_expired']} products")
        print(f"Average weekly value lost: ₹{data['summary']['average_weekly_expired_value']:,.2f}")
        
        # Show category breakdown
        if data['summary']['category_totals']:
            print("\nTotal expired by category:")
            sorted_categories = sorted(data['summary']['category_totals'].items(), 
                                     key=lambda x: x[1], reverse=True)
            for category, count in sorted_categories:
                percentage = (count / data['summary']['total_expired_past_n_weeks'] * 100) if data['summary']['total_expired_past_n_weeks'] > 0 else 0
                print(f"  - {category}: {count} products ({percentage:.1f}%)")
            
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
    
    # Test with different number of weeks
    print("\n" + "=" * 60)
    print("\n2. Testing with 4 weeks:")
    response = requests.get(f"{BASE_URL}/weekly_expired?weeks_back=4")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Successfully retrieved data for {len(data['weeks'])} weeks")
        print(f"Total expired: {data['summary']['total_expired_past_n_weeks']} products")
        print(f"Total value lost: ₹{data['summary']['total_expired_value']:,.2f}")
    else:
        print(f"Error: {response.status_code}")
    
    # Test with 12 weeks for trend analysis
    print("\n" + "=" * 60)
    print("\n3. Testing with 12 weeks (for trend analysis):")
    response = requests.get(f"{BASE_URL}/weekly_expired?weeks_back=12")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Retrieved {len(data['weeks'])} weeks of data")
        
        # Simple trend analysis
        if len(data['weeks']) >= 2:
            recent_4_weeks = sum(w['expired_count'] for w in data['weeks'][:4])
            older_4_weeks = sum(w['expired_count'] for w in data['weeks'][4:8]) if len(data['weeks']) >= 8 else 0
            
            if older_4_weeks > 0:
                trend = ((recent_4_weeks - older_4_weeks) / older_4_weeks) * 100
                print(f"\nTrend Analysis:")
                print(f"  - Recent 4 weeks: {recent_4_weeks} expired products")
                print(f"  - Previous 4 weeks: {older_4_weeks} expired products")
                print(f"  - Change: {trend:+.1f}%")
                
                if trend < -10:
                    print("  - ✅ Waste is decreasing!")
                elif trend > 10:
                    print("  - ⚠️  Waste is increasing!")
                else:
                    print("  - → Waste is stable")

    # Test with cost metrics
    print("\n" + "=" * 60)
    print("\n4. Testing with cost metrics:")
    response = requests.get(f"{BASE_URL}/weekly_expired?weeks_back=2&metric_type=cost")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Successfully retrieved cost data for {len(data['weeks'])} weeks")
        print(f"Metric Type: {data['metric_type']}")
        
        if data['summary']['category_totals']:
            print("\nCategory costs:")
            for category, value in sorted(data['summary']['category_totals'].items(), key=lambda x: x[1], reverse=True):
                print(f"  - {category}: ₹{value:,.2f}")
    else:
        print(f"Error: {response.status_code}")
    
    # Test API documentation
    print("\n" + "=" * 60)
    print("\n5. API Endpoint Information:")
    print(f"Endpoint: GET /weekly_expired")
    print(f"Parameters:")
    print(f"  - weeks_back (optional): Number of weeks to analyze (default: 6, min: 1, max: 52)")
    print(f"  - metric_type (optional): 'qty' or 'cost' (default: 'qty')")
    print(f"\nExample usage:")
    print(f"  curl '{BASE_URL}/weekly_expired?weeks_back=8'")
    print(f"  curl '{BASE_URL}/weekly_expired?metric_type=cost'")
    
    # Insights and recommendations
    print("\n" + "=" * 60)
    print("\n5. Actionable Insights:")
    print("Use this data to:")
    print("  - Identify categories with highest waste")
    print("  - Track waste reduction progress over time")
    print("  - Calculate financial impact of expired products")
    print("  - Plan inventory adjustments based on expiration patterns")

if __name__ == "__main__":
    test_weekly_expired() 