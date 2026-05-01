import logging
from typing import List, Dict, Type, Any
from .smc import (
    MechanicalStructureLayer,
    LiquiditySweepLayer,
    FVGDiscountLayer,
    DisplacementLayer,
    MicroMSSLayer,
    KillzoneFilterLayer,
    NewsEventLayer
)

logger = logging.getLogger("SMCLayers")

class LayerFactory:
    """
    Registry for instantiating SMC layers from strings.
    Maintains compatibility by importing from the modular smc/ package.
    """
    _LAYERS = {
        "MechanicalStructure": MechanicalStructureLayer,
        "LiquiditySweep": LiquiditySweepLayer,
        "FVGDiscount": FVGDiscountLayer,
        "Displacement": DisplacementLayer,
        "MicroMSS": MicroMSSLayer,
        "KillzoneFilter": KillzoneFilterLayer,
        "NewsEventLayer": NewsEventLayer,
        "MLFilter": "Engine.igof.layers.ml_layer.MLFilterLayer" # Use string for late binding or import directly
    }


    @staticmethod
    def create_layers(layer_names: List[str], thresholds: Dict[str, float] = None) -> List[Any]:
        """
        Takes a list of strings and returns initialized class instances.
        """
        instances = []
        thresholds = thresholds or {}
        
        for name in layer_names:
            cls = LayerFactory._LAYERS.get(name)
            if cls:
                # Default threshold handling for Displacement specifically as per prompt
                default_th = 1.5 if name == "Displacement" else 0.5
                threshold = thresholds.get(name, default_th)
                instances.append(cls(name=name, threshold=threshold))
                logger.info(f"Initialized SMC Layer: {name}")
            else:
                logger.warning(f"SMC Layer '{name}' not found in factory.")
                
        return instances
