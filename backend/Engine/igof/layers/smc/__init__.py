# Engine/igof/layers/smc_layers/__init__.py
# ─────────────────────────────────────────────────────────────────────
# Exports every SMC filtration layer so ComponentRegistry.load_component()
# can resolve class names via:
#   import Engine.igof.layers.smc_layers
#   getattr(module, "KillzoneFilterLayer")   → works
#
# When you add a new layer file, add its import here.
# ─────────────────────────────────────────────────────────────────────

from .killzone    import KillzoneFilterLayer
from .structure   import MechanicalStructureLayer
from .liquidity   import LiquiditySweepLayer
from .displacement import DisplacementLayer
from .fvg         import FVGDiscountLayer
from .mss         import MicroMSSLayer
from .news_layer  import NewsEventLayer

__all__ = [
    "KillzoneFilterLayer",
    "MechanicalStructureLayer",
    "LiquiditySweepLayer",
    "DisplacementLayer",
    "FVGDiscountLayer",
    "MicroMSSLayer",
    "NewsEventLayer",
]
