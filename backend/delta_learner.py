import os
import json
import logging
import numpy as np
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("DeltaLearner")

class DeltaLearner:
    """
    Incremental ML Learner that adapts weights in real-time based on trade outcomes.
    Uses a simple Linear Model with Stochastic Gradient Descent (SGD) updates.
    """
    
    def __init__(self, weights_path="models/live_delta_weights.json", learning_rate=0.05):
        self.weights_path = Path(weights_path)
        self.lr = learning_rate
        self.feature_keys = [
            "ob_strength", "fvg_present", "bos_aligned", "liquidity_swept",
            "adr_pct", "pips_to_liquidity", "session", "htf_bias"
        ]
        
        # Initialize weights (0.0 means neutral, let the static model lead initially)
        self.weights = {k: 0.0 for k in self.feature_keys}
        self.bias = 0.0
        self.total_learned = 0
        
        self._load_weights()

    def _load_weights(self):
        """Load learned weights from persistence layer."""
        if self.weights_path.exists():
            try:
                with open(self.weights_path) as f:
                    data = json.load(f)
                    self.weights = data.get("weights", self.weights)
                    self.bias = data.get("bias", 0.0)
                    self.total_learned = data.get("total_learned", 0)
                logger.info(f"DeltaLearner: Loaded {self.total_learned} learning cycles.")
            except Exception as e:
                logger.error(f"DeltaLearner: Load failed: {e}")

    def _save_weights(self):
        """Save learned weights to persistence layer."""
        os.makedirs(self.weights_path.parent, exist_ok=True)
        try:
            with open(self.weights_path, 'w') as f:
                json.dump({
                    "weights": self.weights,
                    "bias": self.bias,
                    "total_learned": self.total_learned,
                    "updated_at": str(datetime.now())
                }, f, indent=2)
        except Exception as e:
            logger.error(f"DeltaLearner: Save failed: {e}")

    def _sigmoid(self, x):
        return 1 / (1 + np.exp(-x))

    def predict(self, features):
        """
        Predict confidence score (0.0 - 1.0).
        """
        score = self.bias
        for k in self.feature_keys:
            score += self.weights[k] * features.get(k, 0)
        
        return self._sigmoid(score)

    def learn(self, features, outcome):
        """
        Update weights based on trade outcome.
        outcome: 1 for Win, 0 for Loss.
        """
        prediction = self.predict(features)
        error = outcome - prediction
        
        # Update weights using SGD: w = w + lr * error * x
        for k in self.feature_keys:
            val = float(features.get(k, 0))
            self.weights[k] += self.lr * error * val
            
        # Update bias
        self.bias += self.lr * error
        
        self.total_learned += 1
        
        # Log the 'Teaching Moment'
        action = "REINFORCED" if outcome == 1 else "PENALIZED"
        logger.info(f"DeltaLearner: {action} logic after {('WIN' if outcome == 1 else 'LOSS')}. Error: {error:.4f}")
        
        # Save every update to ensure persistence
        self._save_weights()

    def get_status(self):
        return {
            "total_learned": self.total_learned,
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "bias": round(self.bias, 4)
        }
