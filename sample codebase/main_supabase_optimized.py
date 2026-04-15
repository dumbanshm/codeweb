import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import pandas as pd
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client
import numpy as np
from unified_waste_reduction_system import UnifiedRecommendationSystem

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bwysarrweyooqtjkowzp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ3eXNhcnJ3ZXlvb3F0amtvd3pwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIzNTIzODEsImV4cCI6MjA2NzkyODM4MX0.cfOrT6MXZ9XHAjYC0K1rri1C4-jGmBbE9q0RQLpR3d8")

# Load all data from Supabase at startup
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Connected to Supabase successfully")
    
    # Fetch all users
    users_response = supabase.table('users').select("*").execute()
    users_df = pd.DataFrame(users_response.data)
    logger.info(f"Loaded {len(users_df)} users from Supabase")
    
    # Fetch all products - NOW USING THE ENRICHED VIEW
    try:
        # Try to use enriched view first
        products_response = supabase.table('products_enriched').select("*").execute()
        products_df = pd.DataFrame(products_response.data)
        logger.info("Using products_enriched view")
    except:
        # Fallback to regular products table if view doesn't exist
        logger.warning("products_enriched view not found, falling back to products table")
        products_response = supabase.table('products').select("*").execute()
        products_df = pd.DataFrame(products_response.data)
    
    # Convert date strings to datetime objects
    if not products_df.empty:
        products_df['packaging_date'] = pd.to_datetime(products_df['packaging_date'])
        products_df['expiry_date'] = pd.to_datetime(products_df['expiry_date'])
    
    logger.info(f"Loaded {len(products_df)} products from enriched view")
    
    # Fetch all transactions
    transactions_response = supabase.table('transactions').select("*").execute()
    transactions_df = pd.DataFrame(transactions_response.data)
    
    # Convert date strings to datetime objects
    if not transactions_df.empty:
        transactions_df['purchase_date'] = pd.to_datetime(transactions_df['purchase_date'])
    
    logger.info(f"Loaded {len(transactions_df)} transactions from Supabase")
    
    # Initialize the UnifiedRecommendationSystem with the loaded data
    system = UnifiedRecommendationSystem(users_df, products_df, transactions_df)
    logger.info("UnifiedRecommendationSystem initialized successfully")
    
except Exception as e:
    logger.error(f"Failed to initialize system: {e}")
    system = None

app = FastAPI(
    title="Unified Waste Reduction API (Optimized with Views)",
    description="API for waste reduction recommendations using Supabase views for optimal performance",
    version="4.0.0"
)

# Enhanced CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Pydantic models remain the same as before
class Product(BaseModel):
    product_id: str
    name: str
    category: str
    brand: str
    diet_type: str
    allergens: List[str]
    shelf_life_days: int
    packaging_date: str
    expiry_date: str
    days_until_expiry: int
    weight_grams: int
    price_mrp: float
    cost_price: Optional[float] = None
    current_discount_percent: float
    inventory_quantity: int
    initial_inventory_quantity: Optional[int] = None
    total_cost: Optional[float] = None
    revenue_generated: Optional[float] = 0.0
    store_location_lat: float
    store_location_lon: float
    is_dead_stock_risk: Optional[int] = None

class PaginatedProductsResponse(BaseModel):
    products: List[Product]
    total_items: int
    total_pages: int
    current_page: int
    page_size: int
    has_next: bool
    has_previous: bool

class Recommendation(BaseModel):
    product_id: str
    product_name: str
    name: str
    category: str
    days_until_expiry: int
    price: float
    price_mrp: float
    discount: float
    current_discount_percent: float
    expiry_date: Optional[str] = None
    score: Optional[float] = None
    is_dead_stock_risk: Optional[int] = None

class RecommendationsResponse(BaseModel):
    user_id: str
    recommendations: List[Recommendation]

# Enhanced models with dynamic pricing
class DynamicPricingInfo(BaseModel):
    urgency_score: float
    current_discount: float
    recommended_discount: float
    discount_increase: float
    reasoning: str
    current_price: float
    recommended_price: float
    potential_savings: float

class RecommendationWithDynamicPricing(Recommendation):
    dynamic_pricing: Optional[DynamicPricingInfo] = None

class RecommendationsResponseWithDynamicPricing(BaseModel):
    user_id: str
    recommendations: List[RecommendationWithDynamicPricing]

class DeadStockRiskItem(BaseModel):
    product_id: str
    name: str
    category: str
    days_until_expiry: int
    current_discount_percent: float
    price_mrp: float
    inventory_quantity: int
    expiry_date: str
    risk_score: Optional[float] = None
    threshold: Optional[float] = None
    risk_level: Optional[str] = None
    recommended_discount_percent: Optional[float] = None
    potential_loss: Optional[float] = None

class DeadStockRiskItemWithDynamicPricing(DeadStockRiskItem):
    dynamic_pricing: Optional[DynamicPricingInfo] = None

class ProductWithDynamicPricing(Product):
    dynamic_pricing: Optional[DynamicPricingInfo] = None

class PaginatedProductsResponseWithDynamicPricing(BaseModel):
    products: List[ProductWithDynamicPricing]
    total_items: int
    total_pages: int
    current_page: int
    page_size: int
    has_next: bool
    has_previous: bool

class ExpiredProductsResponse(BaseModel):
    total_expired_count: int
    total_expired_value: float
    category_split: Dict[str, float]
    category_details: List[Dict[str, Any]]

class WeeklyInventoryData(BaseModel):
    week_start: str
    week_end: str
    week_number: int
    total_inventory: float
    sold_inventory: float
    alive_products_count: int
    metric_type: str
    inventory_utilization_rate_pct: Optional[float] = None
    cost_utilization_rate_pct: Optional[float] = None

class WeeklyInventoryResponse(BaseModel):
    weeks: List[WeeklyInventoryData]
    summary: dict
    metric_type: str

class WeeklyExpiredData(BaseModel):
    week_start: str
    week_end: str
    week_number: int
    expired_count: int
    expired_value: float
    expired_by_category: dict
    metric_type: str
    waste_rate_pct: Optional[float] = None

class WeeklyExpiredResponse(BaseModel):
    weeks: List[WeeklyExpiredData]
    summary: dict
    metric_type: str

# Pydantic models for additional endpoints
class ApiResponse(BaseModel):
    message: str
    endpoints: List[str]

class TransactionCreate(BaseModel):
    user_id: str
    product_id: str  
    quantity: int = Field(..., ge=1)

class TransactionResponse(BaseModel):
    transaction_id: int
    message: str
    inventory_remaining: int
    total_price: float
    discount_applied: float

class InventoryAnalyticsResponse(BaseModel):
    total_products: int
    total_inventory_value: float
    total_revenue: float
    profit_margin: float
    inventory_turnover_rate: float
    categories_performance: List[Dict[str, Any]]
    top_profitable_products: List[Dict[str, Any]]
    underperforming_products: List[Dict[str, Any]]

class InventorySummaryResponse(BaseModel):
    alive_products_count: int
    alive_inventory_cost: float
    alive_inventory_qty: int
    at_risk_products_count: int
    at_risk_inventory_cost: float
    at_risk_inventory_qty: int
    expired_products_count: int
    expired_inventory_cost: float
    expired_inventory_qty: int
    total_products_count: int
    total_inventory_cost: float
    total_inventory_qty: int
    expiring_within_week_count: int
    expiring_within_week_cost: float
    at_risk_cost_percentage: float
    expired_cost_percentage: float
    by_category: Optional[List[Dict[str, Any]]] = None

# Root endpoint
@app.get("/", response_model=ApiResponse)
def root():
    """Root endpoint showing available endpoints"""
    return ApiResponse(
        message="Waste Reduction API with ML (Optimized Version)",
        endpoints=[
            "/health",
            "/recommendations/{user_id}",
            "/dead_stock_risk", 
            "/products",
            "/categories",
            "/users",
            "/expired_products",
            "/inventory_analytics",
            "/inventory_summary",
            "/weekly_inventory",
            "/weekly_expired",
            "/dynamic_pricing/{product_id}",
            "/transactions",
            "/refresh_data"
        ]
    )

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "4.0.0",
        "description": "Optimized Waste Reduction API with Database Views",
        "database": "connected" if supabase else "disconnected",
        "ml_system": "loaded" if system else "not loaded"
    }

# OPTIMIZED: Dead stock risk now uses the view
@app.get("/dead_stock_risk")
def get_dead_stock_risk(
    category: Optional[str] = None,
    min_risk_level: str = Query("HIGH", regex="^(CRITICAL|HIGH|MEDIUM|LOW)$", description="Minimum risk level to include"),
    dynamic: bool = Query(False, description="Include dynamic pricing information")
):
    """
    Get products at risk of becoming dead stock.
    Uses the dead_stock_risk_products view with real-time risk calculation.
    When dynamic=true, includes recommended pricing to prevent dead stock.
    """
    try:
        # Map risk levels to minimum risk scores
        risk_level_thresholds = {
            "CRITICAL": 0.75,  # > 75% risk
            "HIGH": 0.50,      # > 50% risk  
            "MEDIUM": 0.25,    # > 25% risk
            "LOW": 0.0         # All at-risk products
        }
        
        min_risk_score = risk_level_thresholds.get(min_risk_level, 0.5)
        
        # Build query using the view
        query = supabase.table('dead_stock_risk_products').select("*")
        
        # Apply filters
        query = query.gte('risk_score', min_risk_score)
        
        if category:
            query = query.eq('category', category)
        
        # Execute query
        response = query.execute()
        
        # Convert to response model
        items = []
        for product in response.data:
            # Determine risk level based on score
            risk_score = product.get('risk_score', 0)
            if risk_score >= 0.75:
                risk_level = "CRITICAL"
            elif risk_score >= 0.50:
                risk_level = "HIGH"
            elif risk_score >= 0.25:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
            
            item_data = {
                "product_id": product.get('product_id', ''),
                "name": product.get('name', ''),
                "category": product.get('category', ''),
                "days_until_expiry": product.get('days_until_expiry', 0),
                "current_discount_percent": product.get('current_discount_percent', 0),
                "price_mrp": product.get('price_mrp', 0),
                "inventory_quantity": product.get('inventory_quantity', 0),
                "expiry_date": product.get('expiry_date', ''),
                "risk_score": risk_score,
                "threshold": product.get('threshold', 0),
                "risk_level": risk_level,
                "recommended_discount_percent": product.get('recommended_discount_percent', 0),
                "potential_loss": product.get('cost_price', 0) * product.get('inventory_quantity', 0)
            }
            
            if dynamic and system and system.pricing_engine:
                # Get full product data from ML system
                product_data = system.products_df[system.products_df['product_id'] == product['product_id']]
                if not product_data.empty:
                    product_row = product_data.iloc[0]
                    pricing_info = system.pricing_engine.calculate_dynamic_discount(product_row)
                    
                    dynamic_pricing = DynamicPricingInfo(
                        urgency_score=pricing_info['urgency_score'],
                        current_discount=pricing_info['current_discount'],
                        recommended_discount=pricing_info['recommended_discount'],
                        discount_increase=pricing_info['discount_increase'],
                        reasoning=pricing_info['reasoning'],
                        current_price=product.get('price_mrp', 0) * (1 - pricing_info['current_discount'] / 100),
                        recommended_price=product.get('price_mrp', 0) * (1 - pricing_info['recommended_discount'] / 100),
                        potential_savings=product.get('price_mrp', 0) * pricing_info['discount_increase'] / 100
                    )
                    
                    item = DeadStockRiskItemWithDynamicPricing(**item_data, dynamic_pricing=dynamic_pricing)
                else:
                    item = DeadStockRiskItemWithDynamicPricing(**item_data) if dynamic else DeadStockRiskItem(**item_data)
            else:
                item = DeadStockRiskItem(**item_data)
                
            items.append(item)
        
        # Sort by risk score descending
        items.sort(key=lambda x: x.risk_score, reverse=True)
        
        logger.info(f"Found {len(items)} at-risk products (min risk level: {min_risk_level})")
        return items
    
    except Exception as e:
        logger.error(f"Error fetching dead stock risk: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching dead stock risk: {str(e)}")

# OPTIMIZED: Weekly inventory now uses the view
@app.get("/weekly_inventory", response_model=WeeklyInventoryResponse)
def get_weekly_inventory(
    weeks_back: int = Query(6, ge=1, le=52, description="Number of weeks to look back"),
    metric_type: str = Query("qty", regex="^(qty|cost)$", description="Metric type: 'qty' for quantity, 'cost' for monetary value")
):
    """
    Get weekly inventory analytics - OPTIMIZED with database view.
    The view pre-calculates all metrics in parallel at the database level.
    """
    try:
        logger.info(f"Fetching weekly inventory from view: weeks_back={weeks_back}, metric_type={metric_type}")
        
        # Query the weekly_inventory_metrics view
        response = supabase.table('weekly_inventory_metrics').select("*").lte('week_number', weeks_back).execute()
        
        weekly_data = []
        for row in response.data:
            # Select the appropriate metric based on metric_type
            if metric_type == "qty":
                total_inventory = row['total_inventory_qty']
                sold_inventory = row['sold_inventory_qty']
                utilization_rate = row['inventory_utilization_rate_pct']
            else:  # cost
                total_inventory = row['total_inventory_cost']
                sold_inventory = row['sold_inventory_cost']
                utilization_rate = row['cost_utilization_rate_pct']
            
            weekly_data.append(WeeklyInventoryData(
                week_start=row['week_start'],
                week_end=row['week_end'],
                week_number=row['week_number'],
                total_inventory=round(total_inventory, 2),
                sold_inventory=round(sold_inventory, 2),
                alive_products_count=row['alive_products_count'],
                metric_type=metric_type,
                inventory_utilization_rate_pct=round(utilization_rate, 2) if utilization_rate else 0
            ))
        
        # Calculate summary statistics
        total_sold = sum(week.sold_inventory for week in weekly_data)
        avg_weekly_sales = total_sold / len(weekly_data) if weekly_data else 0
        
        # Get current inventory from products_enriched view
        if metric_type == "qty":
            current_inv_response = supabase.rpc('get_current_inventory_qty').execute()
            current_inventory = current_inv_response.data if current_inv_response.data else 0
            unit_label = "units"
        else:
            current_inv_response = supabase.rpc('get_current_inventory_cost').execute()
            current_inventory = current_inv_response.data if current_inv_response.data else 0
            unit_label = "₹"
        
        summary = {
            "total_sold_past_n_weeks": round(total_sold, 2),
            "average_weekly_sales": round(avg_weekly_sales, 2),
            "current_total_inventory": round(current_inventory, 2),
            "weeks_analyzed": len(weekly_data),
            "metric_type": metric_type,
            "unit_label": unit_label
        }
        
        return WeeklyInventoryResponse(
            weeks=weekly_data,
            summary=summary,
            metric_type=metric_type
        )
        
    except Exception as e:
        logger.error(f"Error fetching weekly inventory: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching weekly inventory: {str(e)}")

# OPTIMIZED: Weekly expired now uses the view
@app.get("/weekly_expired", response_model=WeeklyExpiredResponse)
def get_weekly_expired(
    weeks_back: int = Query(6, ge=1, le=52, description="Number of weeks to look back"),
    metric_type: str = Query("qty", regex="^(qty|cost)$", description="Metric type: 'qty' for quantity, 'cost' for monetary value")
):
    """
    Get weekly expired products analytics - OPTIMIZED with database view.
    All calculations are done at the database level in parallel.
    """
    try:
        logger.info(f"Fetching weekly expired from view: weeks_back={weeks_back}, metric_type={metric_type}")
        
        # Query the weekly_expired_metrics view
        response = supabase.table('weekly_expired_metrics').select("*").lte('week_number', weeks_back).execute()
        
        weekly_data = []
        category_totals = {}
        
        for row in response.data:
            # Parse category data based on metric type
            category_breakdown = {}
            if row['expired_by_category']:
                for category, stats in row['expired_by_category'].items():
                    if metric_type == "qty":
                        value = stats['count']
                    else:  # cost
                        value = stats['value_cost']
                    category_breakdown[category] = value
                    
                    # Accumulate category totals
                    if category not in category_totals:
                        category_totals[category] = 0
                    category_totals[category] += value
            
            # Select appropriate value metric
            expired_value = row['expired_value_mrp'] if metric_type == "qty" else row['expired_value_cost']
            
            weekly_data.append(WeeklyExpiredData(
                week_start=row['week_start'],
                week_end=row['week_end'],
                week_number=row['week_number'],
                expired_count=row['expired_count'],
                expired_value=round(expired_value, 2),
                expired_by_category=category_breakdown,
                metric_type=metric_type,
                waste_rate_pct=round(row['waste_rate_pct'], 2) if row['waste_rate_pct'] else 0
            ))
        
        # Calculate summary statistics
        total_expired = sum(week.expired_count for week in weekly_data)
        total_value = sum(week.expired_value for week in weekly_data)
        avg_weekly_expired = total_expired / len(weekly_data) if weekly_data else 0
        avg_weekly_value = total_value / len(weekly_data) if weekly_data else 0
        
        # Round category totals if they're costs
        if metric_type == "cost":
            category_totals = {k: round(v, 2) for k, v in category_totals.items()}
        
        summary = {
            "total_expired_past_n_weeks": total_expired,
            "total_expired_value": round(total_value, 2),
            "average_weekly_expired": round(avg_weekly_expired, 2),
            "average_weekly_expired_value": round(avg_weekly_value, 2),
            "weeks_analyzed": len(weekly_data),
            "category_totals": category_totals,
            "metric_type": metric_type,
            "unit_label": "units" if metric_type == "qty" else "₹"
        }
        
        return WeeklyExpiredResponse(
            weeks=weekly_data,
            summary=summary,
            metric_type=metric_type
        )
        
    except Exception as e:
        logger.error(f"Error fetching weekly expired: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching weekly expired: {str(e)}")

# OPTIMIZED: Products endpoint can now use enriched view
@app.get("/products")
def get_products(
    category: Optional[str] = Query(None, description="Filter by category"),
    diet_type: Optional[str] = Query(None, description="Filter by diet type"),
    min_discount: Optional[float] = Query(None, ge=0, le=100, description="Minimum discount percentage"),
    max_days_until_expiry: Optional[int] = Query(None, ge=0, description="Maximum days until expiry"),
    include_expired: bool = Query(False, description="Include expired products (default: False)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    dynamic: bool = Query(False, description="Include dynamic pricing information")
):
    """
    Get paginated list of products with smart filtering.
    Uses the products_enriched view for pre-calculated metrics.
    By default, only returns alive (non-expired) products unless include_expired=true.
    When dynamic=true, includes recommended pricing based on urgency.
    """
    try:
        # Use the enriched view for optimized queries
        query = supabase.table('products_enriched').select("*", count='exact')
        
        # Apply filters
        if category:
            query = query.eq('category', category)
        
        if diet_type:
            query = query.eq('diet_type', diet_type)
        
        if min_discount is not None:
            query = query.gte('current_discount_percent', min_discount)
        
        if max_days_until_expiry is not None:
            query = query.lte('days_until_expiry', max_days_until_expiry)
        
        # By default, exclude expired products
        if not include_expired:
            query = query.gt('days_until_expiry', 0)
        
        # Calculate pagination
        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)
        
        # Execute query
        response = query.execute()
        
        # Extract total count from response
        total_items = response.count if hasattr(response, 'count') else len(response.data)
        total_pages = (total_items + page_size - 1) // page_size
        
        # Convert to Product models
        products = []
        for product in response.data:
            product_data = {
                "product_id": product['product_id'],
                "name": product['name'],
                "category": product['category'],
                "brand": product['brand'],
                "diet_type": product['diet_type'],
                "allergens": product['allergens'] if isinstance(product['allergens'], list) else (product['allergens'].split(',') if product['allergens'] else []),
                "shelf_life_days": product['shelf_life_days'],
                "packaging_date": product['packaging_date'],
                "expiry_date": product['expiry_date'],
                "days_until_expiry": product['days_until_expiry'],
                "weight_grams": product['weight_grams'],
                "price_mrp": product['price_mrp'],
                "cost_price": product.get('cost_price'),
                "current_discount_percent": product['current_discount_percent'],
                "inventory_quantity": product['inventory_quantity'],
                "initial_inventory_quantity": product.get('initial_inventory_quantity'),
                "total_cost": product.get('total_cost'),
                "revenue_generated": product.get('revenue_generated', 0.0),
                "store_location_lat": product['store_location_lat'],
                "store_location_lon": product['store_location_lon'],
                "is_dead_stock_risk": product.get('is_dead_stock_risk', 0)
            }
            
            if dynamic and system and system.pricing_engine:
                # Get full product data from ML system
                ml_product_data = system.products_df[system.products_df['product_id'] == product['product_id']]
                if not ml_product_data.empty:
                    product_row = ml_product_data.iloc[0]
                    pricing_info = system.pricing_engine.calculate_dynamic_discount(product_row)
                    
                    dynamic_pricing = DynamicPricingInfo(
                        urgency_score=pricing_info['urgency_score'],
                        current_discount=pricing_info['current_discount'],
                        recommended_discount=pricing_info['recommended_discount'],
                        discount_increase=pricing_info['discount_increase'],
                        reasoning=pricing_info['reasoning'],
                        current_price=product['price_mrp'] * (1 - pricing_info['current_discount'] / 100),
                        recommended_price=product['price_mrp'] * (1 - pricing_info['recommended_discount'] / 100),
                        potential_savings=product['price_mrp'] * pricing_info['discount_increase'] / 100
                    )
                    
                    product_obj = ProductWithDynamicPricing(**product_data, dynamic_pricing=dynamic_pricing)
                else:
                    product_obj = ProductWithDynamicPricing(**product_data) if dynamic else Product(**product_data)
            else:
                product_obj = Product(**product_data)
                
            products.append(product_obj)
        
        if dynamic:
            return PaginatedProductsResponseWithDynamicPricing(
                products=products,
                total_items=total_items,
                total_pages=total_pages,
                current_page=page,
                page_size=page_size,
                has_next=page < total_pages,
                has_previous=page > 1
            )
        
        return PaginatedProductsResponse(
            products=products,
            total_items=total_items,
            total_pages=total_pages,
            current_page=page,
            page_size=page_size,
            has_next=page < total_pages,
            has_previous=page > 1
        )
    
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching products: {str(e)}")

# ML-POWERED ENDPOINTS (using the UnifiedRecommendationSystem)

@app.get("/recommendations/{user_id}")
def get_recommendations(
    user_id: str, 
    n: int = Query(10, ge=1, le=50),
    dynamic: bool = Query(False, description="Include dynamic pricing information")
):
    """
    Get personalized recommendations using ML models.
    Combines collaborative filtering, content-based filtering, and urgency scoring.
    When dynamic=true, includes recommended pricing based on urgency.
    """
    if system is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    
    try:
        logger.info(f"Generating ML recommendations for user: {user_id}, dynamic={dynamic}")
        recs = system.get_hybrid_recommendations(user_id, n_recommendations=n)
        
        if recs.empty:
            logger.warning(f"No recommendations found for user: {user_id}")
            if dynamic:
                return RecommendationsResponseWithDynamicPricing(user_id=user_id, recommendations=[])
            return RecommendationsResponse(user_id=user_id, recommendations=[])
        
        recommendations = []
        for _, row in recs.iterrows():
            base_rec = {
                "product_id": str(row.get("product_id", "")),
                "product_name": str(row.get("product_name", "")),
                "name": str(row.get("product_name", "")),
                "category": str(row.get("category", "")),
                "days_until_expiry": int(row.get("days_until_expiry", 0)),
                "price": float(row.get("price", 0)),
                "price_mrp": float(row.get("price", 0)),
                "discount": float(row.get("discount", 0)),
                "current_discount_percent": float(row.get("discount", 0)),
                "expiry_date": "",
                "score": float(row.get("hybrid_score", row.get("recommendation_score", 0))),
                "is_dead_stock_risk": int(row.get("is_dead_stock_risk", 0)),
            }
            
            if dynamic and system.pricing_engine:
                # Get full product data for dynamic pricing calculation
                product_data = system.products_df[system.products_df['product_id'] == row['product_id']]
                if not product_data.empty:
                    product_row = product_data.iloc[0]
                    pricing_info = system.pricing_engine.calculate_dynamic_discount(product_row)
                    
                    dynamic_pricing = DynamicPricingInfo(
                        urgency_score=pricing_info['urgency_score'],
                        current_discount=pricing_info['current_discount'],
                        recommended_discount=pricing_info['recommended_discount'],
                        discount_increase=pricing_info['discount_increase'],
                        reasoning=pricing_info['reasoning'],
                        current_price=float(row.get("price", 0)) * (1 - pricing_info['current_discount'] / 100),
                        recommended_price=float(row.get("price", 0)) * (1 - pricing_info['recommended_discount'] / 100),
                        potential_savings=float(row.get("price", 0)) * pricing_info['discount_increase'] / 100
                    )
                    
                    recommendation = RecommendationWithDynamicPricing(**base_rec, dynamic_pricing=dynamic_pricing)
                else:
                    recommendation = RecommendationWithDynamicPricing(**base_rec)
            else:
                recommendation = Recommendation(**base_rec)
                
            recommendations.append(recommendation)
        
        logger.info(f"ML generated {len(recommendations)} recommendations for user: {user_id}")
        
        if dynamic:
            return RecommendationsResponseWithDynamicPricing(user_id=user_id, recommendations=recommendations)
        return RecommendationsResponse(user_id=user_id, recommendations=recommendations)
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")

@app.get("/dynamic_pricing/{product_id}")
def get_dynamic_pricing(product_id: str):
    """
    Get ML-based dynamic pricing recommendation for a specific product.
    Uses urgency scoring, sales velocity, and user engagement patterns.
    """
    if system is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    
    try:
        # Get product from enriched view
        product_response = supabase.table('products_enriched').select("*").eq('product_id', product_id).execute()
        
        if not product_response.data:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
        
        product = product_response.data[0]
        
        # Use ML pricing engine
        urgency_score = system.pricing_engine.calculate_dynamic_urgency_score(product)
        discount_info = system.pricing_engine.calculate_dynamic_discount(product)
        
        return {
            "product_id": product_id,
            "product_name": product['name'],
            "days_until_expiry": product['days_until_expiry'],
            "current_discount": float(product['current_discount_percent']),
            "recommended_discount": discount_info['recommended_discount'],
            "discount_increase": discount_info['discount_increase'],
            "urgency_score": urgency_score,
            "reasoning": discount_info['reasoning'],
            "current_price": float(product['price_mrp']) * (1 - float(product['current_discount_percent'])/100),
            "recommended_price": float(product['price_mrp']) * (1 - discount_info['recommended_discount']/100),
            "savings": float(product['price_mrp']) * discount_info['discount_increase']/100,
            "is_dead_stock_risk": bool(product.get('calculated_dead_stock_risk', 0)),
            "ml_features": {
                "sales_velocity": product.get('sales_velocity', 0),
                "inventory_turnover": product.get('inventory_turnover_rate', 0),
                "risk_score": product.get('risk_score', 0),
                "deal_engagement_rate": product.get('deal_engagement_rate', 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating dynamic pricing: {e}")
        raise HTTPException(status_code=500, detail=f"Error calculating dynamic pricing: {str(e)}")

@app.get("/categories")
def get_categories():
    """Get all unique product categories"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection not available.")
    
    try:
        # Use the product_performance_summary view for category data
        response = supabase.table('product_performance_summary').select("category").execute()
        categories = [row['category'] for row in response.data]
        return {"categories": sorted(set(categories))}
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching categories: {str(e)}")

@app.get("/users")  
def get_users():
    """Get all users with their purchase patterns"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection not available.")
    
    try:
        # Use the user_purchase_patterns view for enriched user data
        response = supabase.table('user_purchase_patterns').select("*").execute()
        return {"users": response.data}
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")

@app.get("/expired_products", response_model=ExpiredProductsResponse)
def get_expired_products():
    """
    Get expired products analytics - OPTIMIZED with enriched view.
    Note: Values are calculated using cost_price (qty × cost_price), not MRP.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection not available.")
    
    try:
        # Query products_enriched view for expired products
        response = supabase.table('products_enriched').select("*").lt('days_until_expiry', 0).execute()
        expired_df = pd.DataFrame(response.data)
        
        if expired_df.empty:
            return ExpiredProductsResponse(
                total_expired_count=0,
                total_expired_value=0.0,
                category_split={},
                category_details=[]
            )
        
        # Calculate total value using cost_price (same as inventory_summary)
        expired_df["total_value"] = expired_df["cost_price"] * expired_df["inventory_quantity"]
        
        # Category statistics
        category_stats = expired_df.groupby("category").agg({
            "product_id": "count",
            "total_value": "sum",
            "inventory_quantity": "sum"
        }).reset_index()
        
        category_stats.columns = ["category", "product_count", "total_value", "total_quantity"]
        
        # Calculate percentage split
        total_expired_value = category_stats["total_value"].sum()
        category_split = {}
        category_details = []
        
        for _, row in category_stats.iterrows():
            percentage = (row["total_value"] / total_expired_value * 100) if total_expired_value > 0 else 0
            category_split[row["category"]] = round(percentage, 2)
            
            category_details.append({
                "category": row["category"],
                "product_count": int(row["product_count"]),
                "total_value": round(row["total_value"], 2),
                "total_quantity": int(row["total_quantity"]),
                "percentage": round(percentage, 2)
            })
        
        # Sort by value descending
        category_details = sorted(category_details, key=lambda x: x["total_value"], reverse=True)
        
        return ExpiredProductsResponse(
            total_expired_count=len(expired_df),
            total_expired_value=round(total_expired_value, 2),
            category_split=category_split,
            category_details=category_details
        )
        
    except Exception as e:
        logger.error(f"Error fetching expired products: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching expired products: {str(e)}")

@app.post("/transactions", response_model=TransactionResponse)
def create_transaction(transaction: TransactionCreate, use_dynamic_pricing: bool = True):
    """
    Create a new transaction with ML-based dynamic pricing.
    Inventory and revenue are updated via database triggers.
    """
    try:
        logger.info(f"Creating transaction for user {transaction.user_id}, product {transaction.product_id}")
        
        # Get product details from enriched view
        product_response = supabase.table('products_enriched').select("*").eq('product_id', transaction.product_id).execute()
        if not product_response.data:
            raise HTTPException(status_code=404, detail=f"Product {transaction.product_id} not found")
        
        product = product_response.data[0]
        
        # Check inventory
        if product['inventory_quantity'] < transaction.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient inventory. Available: {product['inventory_quantity']}")
        
        # Get user details
        user_response = supabase.table('users').select("*").eq('user_id', transaction.user_id).execute()
        if not user_response.data:
            raise HTTPException(status_code=404, detail=f"User {transaction.user_id} not found")
        
        user = user_response.data[0]
        
        # Calculate pricing
        if use_dynamic_pricing and system:
            # Use ML pricing engine
            urgency_score = system.pricing_engine.calculate_dynamic_urgency_score(product)
            discount_info = system.pricing_engine.calculate_dynamic_discount(product)
            discount_percent = float(discount_info['recommended_discount'])
            
            logger.info(f"ML pricing: urgency={urgency_score:.2f}, discount={discount_percent}%")
        else:
            # Use static discount
            discount_percent = float(product['current_discount_percent'])
        
        price_per_unit = float(product['price_mrp']) * (1 - discount_percent / 100)
        total_price = price_per_unit * transaction.quantity
        
        # Create transaction
        transaction_data = {
            'user_id': transaction.user_id,
            'product_id': transaction.product_id,
            'purchase_date': datetime.now().strftime('%Y-%m-%d'),
            'quantity': transaction.quantity,
            'price_paid_per_unit': round(price_per_unit, 2),
            'total_price_paid': round(total_price, 2),
            'discount_percent': discount_percent,
            'product_diet_type': product['diet_type'],
            'user_diet_type': user['diet_type'],
            'days_to_expiry_at_purchase': product['days_until_expiry'],
            'user_engaged_with_deal': 1 if discount_percent > 0 else 0
        }
        
        # Insert transaction (trigger will update inventory and revenue)
        transaction_response = supabase.table('transactions').insert(transaction_data).execute()
        
        if not transaction_response.data:
            raise HTTPException(status_code=500, detail="Failed to create transaction")
        
        created_transaction = transaction_response.data[0]
        
        return TransactionResponse(
            transaction_id=created_transaction['transaction_id'],
            message="Transaction created successfully",
            inventory_remaining=product['inventory_quantity'] - transaction.quantity,
            total_price=round(total_price, 2),
            discount_applied=discount_percent
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating transaction: {str(e)}")

@app.get("/inventory_analytics", response_model=InventoryAnalyticsResponse)
def get_inventory_analytics():
    """Get comprehensive inventory analytics - OPTIMIZED with views"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection not available.")
    
    try:
        # Get summary from product_performance_summary view
        summary_response = supabase.table('product_performance_summary').select("*").execute()
        summary_df = pd.DataFrame(summary_response.data)
        
        # Calculate overall metrics
        total_products = summary_df['product_count'].sum()
        total_inventory_value = summary_df['total_inventory_value'].sum()
        total_revenue = summary_df['total_revenue'].sum()
        
        profit_margin = ((total_revenue - total_inventory_value) / total_revenue * 100) if total_revenue > 0 else 0
        avg_turnover = summary_df['avg_turnover_rate'].mean()
        
        # Category performance
        categories_performance = []
        for _, row in summary_df.iterrows():
            category_profit = row['total_revenue'] - (row['total_inventory_value'] * row['avg_turnover_rate'])
            categories_performance.append({
                "category": row['category'],
                "total_inventory": int(row['total_inventory']),
                "inventory_value": round(row['total_inventory_value'], 2),
                "revenue": round(row['total_revenue'], 2),
                "profit": round(category_profit, 2),
                "turnover_rate": round(row['avg_turnover_rate'], 2),
                "at_risk_products": int(row['at_risk_products']),
                "expired_products": int(row['expired_products'])
            })
        
        # Get top profitable products from enriched view
        products_response = supabase.table('products_enriched').select("*").gt('actual_revenue_generated', 0).execute()
        products_df = pd.DataFrame(products_response.data)
        
        if not products_df.empty:
            products_df['profit'] = products_df['actual_revenue_generated'] - (products_df['cost_price'] * products_df['total_quantity_sold'])
            
            # Top profitable products
            top_profitable = products_df.nlargest(10, 'profit')[['product_id', 'name', 'category', 'profit', 'inventory_turnover_rate']]
            top_profitable_products = top_profitable.to_dict('records')
            
            # Underperforming products (low turnover, high inventory)
            underperforming = products_df[
                (products_df['inventory_turnover_rate'] < 0.1) & 
                (products_df['inventory_quantity'] > 50)
            ].nsmallest(10, 'inventory_turnover_rate')[['product_id', 'name', 'category', 'inventory_quantity', 'inventory_turnover_rate']]
            underperforming_products = underperforming.to_dict('records')
        else:
            top_profitable_products = []
            underperforming_products = []
        
        return InventoryAnalyticsResponse(
            total_products=int(total_products),
            total_inventory_value=round(total_inventory_value, 2),
            total_revenue=round(total_revenue, 2),
            profit_margin=round(profit_margin, 2),
            inventory_turnover_rate=round(avg_turnover, 2),
            categories_performance=categories_performance,
            top_profitable_products=top_profitable_products,
            underperforming_products=underperforming_products
        )
        
    except Exception as e:
        logger.error(f"Error calculating inventory analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Error calculating inventory analytics: {str(e)}")

@app.get("/inventory_summary", response_model=InventorySummaryResponse)
def get_inventory_summary(include_category_breakdown: bool = Query(False, description="Include category-wise breakdown")):
    """
    Get real-time inventory summary with costs calculated as qty * cost_price.
    Uses pre-computed view for optimal performance.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection not available.")
    
    try:
        logger.info("Fetching inventory summary from view")
        
        # Get main summary from view
        summary_response = supabase.table('inventory_summary').select("*").execute()
        
        if not summary_response.data:
            raise HTTPException(status_code=500, detail="Failed to fetch inventory summary")
        
        summary = summary_response.data[0]  # View returns single row
        
        # Build response
        response_data = InventorySummaryResponse(
            alive_products_count=summary['alive_products_count'],
            alive_inventory_cost=round(summary['alive_inventory_cost'], 2),
            alive_inventory_qty=summary['alive_inventory_qty'],
            at_risk_products_count=summary['at_risk_products_count'],
            at_risk_inventory_cost=round(summary['at_risk_inventory_cost'], 2),
            at_risk_inventory_qty=summary['at_risk_inventory_qty'],
            expired_products_count=summary['expired_products_count'],
            expired_inventory_cost=round(summary['expired_inventory_cost'], 2),
            expired_inventory_qty=summary['expired_inventory_qty'],
            total_products_count=summary['total_products_count'],
            total_inventory_cost=round(summary['total_inventory_cost'], 2),
            total_inventory_qty=summary['total_inventory_qty'],
            expiring_within_week_count=summary['expiring_within_week_count'],
            expiring_within_week_cost=round(summary['expiring_within_week_cost'], 2),
            at_risk_cost_percentage=float(summary['at_risk_cost_percentage']),
            expired_cost_percentage=float(summary['expired_cost_percentage'])
        )
        
        # Optionally include category breakdown
        if include_category_breakdown:
            category_response = supabase.table('inventory_summary_by_category').select("*").execute()
            
            if category_response.data:
                response_data.by_category = [
                    {
                        "category": row['category'],
                        "alive_products_count": row['alive_products_count'],
                        "alive_inventory_cost": round(row['alive_inventory_cost'], 2),
                        "at_risk_products_count": row['at_risk_products_count'],
                        "at_risk_inventory_cost": round(row['at_risk_inventory_cost'], 2),
                        "expired_products_count": row['expired_products_count'],
                        "expired_inventory_cost": round(row['expired_inventory_cost'], 2),
                        "total_inventory_cost": round(row['total_inventory_cost'], 2)
                    }
                    for row in category_response.data
                ]
        
        logger.info("Successfully fetched inventory summary")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching inventory summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching inventory summary: {str(e)}")

@app.post("/refresh_data")
def refresh_data():
    """Refresh data from Supabase and retrain ML models"""
    global system
    
    try:
        # Fetch fresh data from views
        users_response = supabase.table('users').select("*").execute()
        users_df = pd.DataFrame(users_response.data)
        
        products_response = supabase.table('products_enriched').select("*").execute()
        products_df = pd.DataFrame(products_response.data)
        products_df['packaging_date'] = pd.to_datetime(products_df['packaging_date'])
        products_df['expiry_date'] = pd.to_datetime(products_df['expiry_date'])
        
        transactions_response = supabase.table('transactions').select("*").execute()
        transactions_df = pd.DataFrame(transactions_response.data)
        transactions_df['purchase_date'] = pd.to_datetime(transactions_df['purchase_date'])
        
        # Reinitialize ML system
        system = UnifiedRecommendationSystem(users_df, products_df, transactions_df)
        
        # Rebuild ML models
        system.build_content_similarity_matrix()
        system.build_collaborative_filtering_model(n_factors=50)
        
        logger.info("Data refreshed and ML models retrained successfully")
        return {
            "message": "Data refreshed and ML models retrained successfully",
            "status": "success",
            "users_count": len(users_df),
            "products_count": len(products_df),
            "transactions_count": len(transactions_df)
        }
        
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        raise HTTPException(status_code=500, detail=f"Error refreshing data: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 