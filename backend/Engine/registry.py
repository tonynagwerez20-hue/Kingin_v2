import importlib
import logging
import sys
from typing import Any, Type, Dict

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ComponentRegistry")

class ComponentRegistry:
    """
    Utility class for dynamically loading and instantiating Python classes.
    """
    
    @staticmethod
    def load_component(class_path: str, config: Dict[str, Any] = None) -> Any:
        """
        Dynamically loads a class from a string path and instantiates it.
        
        Args:
            class_path: The full module path to the class (e.g., 'Engine.igof.layers.SessionFilterLayer')
            config: Optional configuration dictionary to pass to the constructor.
            
        Returns:
            An instance of the requested class.
            
        Raises:
            ImportError: if the module cannot be found.
            AttributeError: if the class does not exist in the module.
            TypeError: if instantiation fails.
        """
        try:
            logger.info(f"Loading component: {class_path}")
            
            # Split path into module and class name
            parts = class_path.split(".")
            module_name = ".".join(parts[:-1])
            class_name = parts[-1]
            
            # Import the module
            module = importlib.import_module(module_name)
            
            # Get the class from the module
            cls = getattr(module, class_name)
            
            # Instantiate the class
            if config is not None:
                instance = cls(config=config)
            else:
                # If no config provided, try instantiating without arguments
                # Some components like DataProvider might not need a config in constructor
                instance = cls()
                
            logger.info(f"Successfully loaded {class_name}")
            return instance
            
        except ImportError as e:
            logger.error(f"Failed to import module for component {class_path}: {e}")
            sys.exit(1) # Shutdown safely as per requirements
        except AttributeError as e:
            logger.error(f"Class {class_name} not found in module {module_name}: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error loading component {class_path}: {e}")
            sys.exit(1)

if __name__ == "__main__":
    # Example usage/test
    # reg = ComponentRegistry()
    # obj = reg.load_component("Engine.base_interfaces.BaseFiltrationLayer", config={})
    pass
