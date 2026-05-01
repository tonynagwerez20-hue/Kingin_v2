import importlib
import logging
from typing import Dict, Any
from .base_provider import BaseDataProvider

logger = logging.getLogger("ProviderFactory")

class DataProviderFactory:
    """
    Factory to dynamically load Data Providers from configuration.
    """
    
    _PROVIDERS = {
        "MT5_PROVIDER": "data_feed.mt5_provider.MT5DataProvider",
        "SIERRA_PROVIDER": "data_feed.sierra_provider.SierraDataProvider"
    }

    @staticmethod
    def get_provider(provider_type: str, config: Dict[str, Any]) -> BaseDataProvider:
        """
        Loads and returns an instance of the requested provider.
        """
        class_path = DataProviderFactory._PROVIDERS.get(provider_type)
        if not class_path:
            raise ValueError(f"Unknown Data Provider Type: {provider_type}")
            
        try:
            module_name, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            provider_class = getattr(module, class_name)
            
            logger.info(f"Dynamically loaded Data Provider: {provider_type}")
            return provider_class(config)
            
        except ImportError as e:
            logger.error(f"Failed to import provider {provider_type}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error instantiating provider {provider_type}: {e}")
            raise
