import numpy as np
from typing import List, Dict, Tuple
from loguru import logger
from collections import defaultdict

class LevelAnalyzer:
    def __init__(self, tolerance: float = 0.0005):
        self.tolerance = tolerance # 0.05% tolerance
    
    def find_support_resistance(self, candles: List[Dict], 
                                 sensitivity: int = 3) -> Dict[str, List[Dict]]:
        """
        Identifies S/R levels based on peaks and troughs.
        """
        if len(candles) < sensitivity * 2 + 1:
            return {"support": [], "resistance": []}
        
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        current_price = candles[0].get('close', 1.0)
        
        resistance_levels = []
        support_levels = []
        
        for i in range(sensitivity, len(candles) - sensitivity):
            
            # Check for Resistance (a peak where the high is the highest in the window)
            is_resistance = all(highs[i] >= highs[i-j] and highs[i] >= highs[i+j] 
                               for j in range(1, sensitivity + 1))
            if is_resistance:
                resistance_levels.append({"price": highs[i]})
            
            # Check for Support (a trough where the low is the lowest in the window)
            is_support = all(lows[i] <= lows[i-j] and lows[i] <= lows[i+j] 
                            for j in range(1, sensitivity + 1))
            if is_support:
                support_levels.append({"price": lows[i]})

        # Consolidate and filter
        return self._consolidate_levels(resistance_levels, support_levels, current_price)

    def _consolidate_levels(self, resistance: List[Dict], support: List[Dict], current_price: float) -> Dict:
        """Merges levels and calculates proximity."""
        
        def merge(levels):
            if not levels: return []
            
            levels.sort(key=lambda x: x["price"])
            consolidated = []
            
            # Simple consolidation logic
            for level in levels:
                is_merged = False
                for c_level in consolidated:
                    # Check if within tolerance
                    if abs(level["price"] - c_level["price"]) < self.tolerance * current_price:
                        c_level["touches"] = c_level.get("touches", 1) + 1
                        is_merged = True
                        break
                if not is_merged:
                    consolidated.append({"price": level["price"], "touches": 1, "strength": 0.6})
            return consolidated

        consolidated_resistance = merge(resistance)
        consolidated_support = merge(support)
        
        # Calculate distance and sort
        def calculate_distance(level):
            level["distance"] = abs(level["price"] - current_price)
            return level
        
        consolidated_resistance = [calculate_distance(l) for l in consolidated_resistance]
        consolidated_support = [calculate_distance(l) for l in consolidated_support]
        
        # Return the 3 nearest levels
        return {
            "support": sorted(consolidated_support, key=lambda x: x["distance"])[:3],
            "resistance": sorted(consolidated_resistance, key=lambda x: x["distance"])[:3]
        }
