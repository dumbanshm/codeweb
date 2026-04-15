import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Data paths
DATA_DIR = BASE_DIR / "datasets"
MODELS_DIR = BASE_DIR / "models"
SCRIPTS_DIR = BASE_DIR / "scripts"

# Model parameters
MODEL_CONFIG = {
    'content_weight': 0.4,
    'collaborative_weight': 0.6,
    'max_discount_percent': 50,
    'discount_increment': 2.5,
    'risk_threshold': 0.6
}

# API settings
API_CONFIG = {
    'host': '0.0.0.0',
    'port': 8000,
    'reload': True
}

# Dashboard refresh intervals (in seconds)
REFRESH_INTERVALS = {
    'metrics': 30,
    'recommendations': 60,
    'at_risk_products': 15
}