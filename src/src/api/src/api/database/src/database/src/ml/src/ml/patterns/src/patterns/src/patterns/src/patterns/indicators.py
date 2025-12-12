import numpy as np
from typing import List, Dict
from loguru import logger

try:
    import ta 
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logger.warning("TA library not available. Indicator calculations will be disabled.")

class TechnicalIndicators:
    def __init__(self):
        self.indicators = {}
    
    def calculate_all(self, candles: List[Dict]) -> Dict:
        """Calculates all relevant technical indicators."""
        if len(candles) < 30 or not TA_AVAILABLE: 
            return {}
        
        # Prepare data (reverse to oldest-to-newest for TA library)
        candles_df = reversed(candles)
        closes = np.array([c["close"] for c in candles_df])
        highs = np.array([c["high"] for c in candles_df])
        lows = np.array([c["low"] for c in candles_df])
        
        result = {}
        
        # RSI
        rsi_instance = ta.momentum.RSIIndicator(closes, window=14)
        result["rsi"] = self._analyze_rsi(rsi_instance.rsi().iloc[-1])
        
        # MACD
        macd_instance = ta.trend.MACD(closes)
        result["macd"] = self._analyze_macd(
            macd_instance.macd().iloc[-1], 
            macd_instance.macd_signal().iloc[-1], 
            macd_instance.macd_diff().iloc[-1]
        )
        
        # ATR (Volatility measure)
        atr_instance = ta.volatility.AverageTrueRange(highs, lows, closes, window=14)
        result["atr"] = atr_instance.average_true_range().iloc[-1]
        
        self.indicators = result
        return result

    # --- Analysis Helpers ---
    def _analyze_rsi(self, rsi_value: float) -> Dict:
        signal = "neutral"
        if rsi_value > 70:
            signal = "overbought"
        elif rsi_value < 30:
            signal = "oversold"
            
        return {"value": rsi_value, "signal": signal}

    def _analyze_macd(self, macd_line: float, signal_line: float, hist: float) -> Dict:
        trend = "neutral"
        if hist > 0 and macd_line > signal_line:
            trend = "bullish"
        elif hist < 0 and macd_line < signal_line:
            trend = "bearish"
            
        return {
            "macd_line": macd_line, 
            "signal_line": signal_line, 
            "histogram": hist,
            "trend": trend
        }
