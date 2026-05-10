import json
import os
import logging

logger = logging.getLogger("ConfigLoader")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "trading_params_lite.json")

def load_trading_params():
    """
    Load trading parameters from the JSON config file.
    """
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Config file not found at {CONFIG_PATH}")
        return {}
    
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config file: {e}")
        return {}

def save_trading_params(params):
    """
    Save trading parameters to the JSON config file.
    """
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(params, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving config file: {e}")
        return False

def get_news_participation():
    """
    Helper to specifically get news participation flag.
    """
    params = load_trading_params()
    # Check both potential locations for the flag
    return params.get("news_participate", params.get("filters", {}).get("news_participate", True))
