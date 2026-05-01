from typing import Dict
import logging
from ...base_interfaces import BaseFiltrationLayer

import ml_filter

logger = logging.getLogger("MLFilterLayer")

class MLFilterLayer(BaseFiltrationLayer):
    """
    IGOF Filtration Layer that uses the ML model to score signals.
    """
    def process(self, data: Dict) -> Dict:
        """
        Processes the market snapshot and applies ML confidence filtering.
        Expects 'signal' or features to be present in data.
        """
        # In a real pipeline, the strategy would have already populated 
        # features or a candidate signal in the data dict.
        candidate_signal = data.get("candidate_signal", {})
        
        # If no candidate signal, we might be in an enrichment phase 
        # or the previous layer didn't pass one. 
        # For a compulsory filter, if no signal is present to filter, 
        # we might just pass or fail based on policy.
        if not candidate_signal:
            # If we don't have a signal to score, we can't filter it.
            # Usually, ML sits after structural filters.
            return {"status": True, "reason": "No candidate signal to score", "score": 1.0}

        features = ml_filter.engineer_features(candidate_signal)
        should_trade, confidence, debug = ml_filter.should_trade(features)
        
        if should_trade:
            return {
                "status": True,
                "reason": f"ML Confidence OK ({confidence:.2f})",
                "score": confidence
            }
        else:
            return {
                "status": False,
                "reason": f"ML Confidence too low ({confidence:.2f} < {debug['threshold']})",
                "score": confidence
            }
