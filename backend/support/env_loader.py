"""
Performance Configuration Loader
Loads and provides access to performance settings for resource optimization.
"""
import configparser
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class PerformanceConfig:
    """Singleton class for performance configuration."""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Load configuration from performance.ini"""
        config_path = Path(__file__).parent / "performance.ini"
        self._config = configparser.ConfigParser()
        
        if config_path.exists():
            self._config.read(config_path)
            logger.info(f"Loaded performance config from {config_path}")
        else:
            logger.warning(f"Performance config not found at {config_path}, using defaults")
            self._set_defaults()
    
    def _set_defaults(self):
        """Set default values if config file doesn't exist."""
        self._config['PERFORMANCE'] = {
            'max_memory_usage': '400',
            'buffer_max_size': '100',
            'enable_periodic_cleanup': 'true',
            'cleanup_interval_seconds': '300',
            'main_loop_interval_seconds': '10',
            'health_check_interval_seconds': '15',
            'enable_adaptive_polling': 'true',
            'database_batch_writes': 'true',
            'batch_write_interval_seconds': '30',
            'enable_wal_mode': 'true',
            'log_level': 'WARNING',
            'max_log_file_size_mb': '10',
            'dashboard_refresh_interval_seconds': '30',
            'enable_lazy_loading': 'true',
            'max_plot_points': '200',
            'enable_dashboard_auto_refresh': 'false',
            'enable_detailed_logging': 'false',
            'enable_buffer_snapshots': 'false'
        }
    
    def get_int(self, key, default=0):
        """Get integer value."""
        try:
            return self._config.getint('PERFORMANCE', key)
        except (ValueError, configparser.NoOptionError):
            return default
    
    def get_bool(self, key, default=False):
        """Get boolean value."""
        try:
            return self._config.getboolean('PERFORMANCE', key)
        except (ValueError, configparser.NoOptionError):
            return default
    
    def get_str(self, key, default=''):
        """Get string value."""
        try:
            return self._config.get('PERFORMANCE', key)
        except configparser.NoOptionError:
            return default

# Global instance
perf_config = PerformanceConfig()

import os
from dotenv import load_dotenv

load_dotenv()

def get_env(key, default=None):
    return os.environ.get(key, default)

def get_int_env(key, default=0):
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default

def get_float_env(key, default=0.0):
    try:
        return float(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default
