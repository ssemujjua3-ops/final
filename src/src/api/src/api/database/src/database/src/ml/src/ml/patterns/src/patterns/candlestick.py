import numpy as np
from typing import List, Dict, Optional, Tuple
from loguru import logger

class CandlestickAnalyzer:
    def __init__(self):
        # ... list of patterns
        pass
        
    def analyze_candles(self, candles: List[Dict]) -> List[Dict]:
        """Analyzes a list of candles for known patterns."""
        if len(candles) < 3: return []
        
        patterns_found = []
        
        # Only check the latest 5 candles
        for i in range(min(5, len(candles) - 2)):
            current = candles[i]
            prev = candles[i + 1]
            
            detected = self._detect_patterns(current, prev)
            
            for pattern in detected:
                patterns_found.append({
                    "pattern": pattern["name"],
                    "type": pattern["type"],
                    "signal": pattern["signal"],
                    "strength": pattern["strength"],
                    "timestamp": current.get("timestamp")
                })
        return patterns_found
    
    def _detect_patterns(self, c1: Dict, c2: Dict) -> List[Dict]:
        """Core two-candle pattern detection logic (Engulfing)."""
        detected = []
        
        body1 = abs(c1['close'] - c1['open'])
        body2 = abs(c2['close'] - c2['open'])
        
        # Define if candle is bullish or bearish
        is_bull1 = c1['close'] > c1['open']
        is_bear1 = c1['close'] < c1['open']
        is_bull2 = c2['close'] > c2['open']
        is_bear2 = c2['close'] < c2['open']

        # BULLISH ENGULFING: Bearish candle followed by a larger bullish candle that fully engulfs it
        if is_bear2 and is_bull1 and body1 > 1.2 * body2 and c1['open'] < c2['close'] and c1['close'] > c2['open']:
            detected.append({"name": "bullish_engulfing", "type": "reversal", "signal": "CALL", "strength": 0.85})

        # BEARISH ENGULFING: Bullish candle followed by a larger bearish candle that fully engulfs it
        elif is_bull2 and is_bear1 and body1 > 1.2 * body2 and c1['open'] > c2['close'] and c1['close'] < c2['open']:
            detected.append({"name": "bearish_engulfing", "type": "reversal", "signal": "PUT", "strength": 0.85})

        # DOJI: Tiny body (less than 10% of range)
        range1 = c1['high'] - c1['low']
        if body1 < 0.1 * range1 and range1 > 0.0001:
            detected.append({"name": "doji", "type": "continuation", "signal": "neutral", "strength": 0.5})

        return detected
        
    def get_trend(self, candles: List[Dict], period: int = 20) -> str:
        """Determines the short-term trend based on SMA comparison."""
        if len(candles) < period:
            return "neutral"
            
        closes = [c["close"] for c in candles[:period]]
        
        # Compare the average of the first half (old) vs the second half (new)
        avg_first_half = np.mean(closes[period//2:])
        avg_second_half = np.mean(closes[:period//2])
        
        # 0.1% difference threshold
        if avg_second_half > avg_first_half * 1.001:
            return "uptrend"
        elif avg_second_half < avg_first_half * 0.999:
            return "downtrend"
        return "neutral"
        
    def get_pattern_strength(self, patterns: List[Dict]) -> float:
        """Calculates a cumulative strength score from detected patterns."""
        if not patterns: return 0.5
            
        call_score = sum(p.get("strength", 0) for p in patterns if p.get("signal") == "CALL")
        put_score = sum(p.get("strength", 0) for p in patterns if p.get("signal") == "PUT")
                
        total = call_score + put_score
        return max(call_score, put_score) / total if total > 0 else 0.5
