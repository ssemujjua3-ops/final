import asyncio
import time
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

# Corrected Imports 
from src.api.pocket_option import PocketOptionClient
from src.database.db import db
from src.patterns.candlestick import CandlestickAnalyzer
from src.patterns.levels import LevelAnalyzer
from src.patterns.indicators import TechnicalIndicators
from src.ml.agent import TradingAgent
from src.ml.knowledge_learner import KnowledgeLearner
from src.utils.tournament import TournamentManager, TournamentScheduler

class TradingBot:
    def __init__(self, ssid: str = None, demo: bool = True):
        self.client = PocketOptionClient(ssid=ssid, demo=demo)
        self.candlestick_analyzer = CandlestickAnalyzer()
        self.level_analyzer = LevelAnalyzer()
        self.indicators = TechnicalIndicators()
        self.agent = TradingAgent()
        self.knowledge_learner = KnowledgeLearner(db=db)
        self.tournament_manager = TournamentManager(self.client, self.agent, db=db)
        
        self.is_running = False
        self.is_learning = False
        self.is_trading = False
        
        self.current_asset = "EURUSD_otc"
        self.current_timeframe = 60
        self.available_timeframes = [60, 300, 900] # Common timeframes
        
        # market_data stores historical candles for all subscribed assets/timeframes
        self.market_data: Dict[str, Dict] = {}
        
        # Analysis results for the currently active asset/timeframe
        self.patterns_detected: List[Dict] = []
        self.levels_detected: Dict = {}
        self.indicator_values: Dict = {}
        
        self.trade_history: List[Dict] = []
        self.pending_trades: List[Dict] = []
        self.trades_this_hour = 0
        
        self.min_confidence = 0.75 # Default trading threshold
        
    async def handle_candle(self, candle: Dict):
        """Processes a new candle and runs the trading logic."""
        asset = candle["asset"]
        timeframe = candle["timeframe"]
        key = f"{asset}_{timeframe}"
        
        # 1. Store the candle (Most recent candle at index 0)
        if key not in self.market_data:
            self.market_data[key] = {"candles": []}
            
        # Deduplicate before inserting (since simulator/API might send the same candle)
        if self.market_data[key]["candles"] and self.market_data[key]["candles"][0]["timestamp"] == candle["timestamp"]:
            # Update the existing candle (in case of partial candle updates)
            self.market_data[key]["candles"][0] = candle
        else:
            self.market_data[key]["candles"].insert(0, candle)
            
        self.market_data[key]["candles"] = self.market_data[key]["candles"][:200]
        
        # Only analyze the currently active asset/timeframe for trading decisions
        if asset == self.current_asset and timeframe == self.current_timeframe:
            candles_to_analyze = self.market_data[key]["candles"]
            
            # 2. Run analysis modules
            self.patterns_detected = self.candlestick_analyzer.analyze_candles(candles_to_analyze)
            self.levels_detected = self.level_analyzer.find_support_resistance(candles_to_analyze)
            self.indicator_values = self.indicators.calculate_all(candles_to_analyze)
            
            # 3. Generate Trade Decision
            if self.is_trading and self.is_running:
                context = {
                    "asset": asset, "timeframe": timeframe, "patterns": self.patterns_detected,
                    "levels": self.levels_detected, "indicators": self.indicator_values,
                    "balance": self.client.balance, "candles": candles_to_analyze
                }
                trade_suggestion = self.agent.get_trade_decision(context)
                
                direction = trade_suggestion.get("direction")
                confidence = trade_suggestion.get("confidence", 0)
                
                logger.info(f"Agent Suggestion: {direction} with {confidence:.2%} confidence.")
                
                # 4. Execute Trade if confident enough
                if direction in ("CALL", "PUT") and confidence >= self.min_confidence:
                    
                    # Calculate required inputs for the agent's money management
                    volatility_placeholder = self.indicator_values.get("atr", 0.001)
                    pattern_strength_placeholder = self.candlestick_analyzer.get_pattern_strength(self.patterns_detected)

                    expiration = self.agent.determine_expiration(
                        volatility_placeholder, 
                        pattern_strength_placeholder
                    )
                    amount = self.agent.get_trade_amount(self.client.balance, confidence)
                    
                    logger.success(f"PLACING TRADE: {direction} {asset} for ${amount:.2f} @ {confidence:.2%} confidence. Exp: {expiration}s")
                    
                    # Store the trade entry price before placing
                    entry_price = candles_to_analyze[0]["close"] 
                    
                    trade_result = await self.client.place_trade(
                        asset=asset, 
                        direction=direction, 
                        amount=amount, 
                        duration=expiration
                    )
                    
                    # Update internal trade history
                    self.trades_this_hour += 1
                    self.trade_history.append({
                        "id": trade_result.get("id"), "asset": asset, "direction": direction, 
                        "amount": amount, "confidence": confidence, "outcome": trade_result.get("outcome"),
                        "created_at": datetime.now().isoformat()
                    })
                    
                    # Add to ML experience buffer if result is immediate (simulation mode)
                    if trade_result.get("outcome") != "PENDING":
                        self.agent.add_experience({
                            "features": self.agent._extract_features(context),
                            "outcome": trade_result.get("outcome"),
                            "confidence": confidence
                        })
                        self.agent.retrain_if_needed()


    async def start(self):
        """Main asynchronous loop for the bot."""
        if self.is_running: return

        self.is_running = True
        logger.info("Bot is starting...")

        if not await self.client.connect():
            self.is_running = False
            logger.error("Failed to connect to Pocket Option Client. Stopping.")
            return

        logger.info(f"Connected. Running in {'DEMO' if self.client.is_simulation() else 'REAL'} mode. Balance: ${self.client.balance:.2f}")

        # Subscribe to market data for the current asset and all available timeframes
        for tf in self.available_timeframes:
            await self.client.subscribe_candles(
                asset=self.current_asset, 
                timeframe=tf, 
                callback=self.handle_candle
            )
            logger.info(f"Subscribed to {self.current_asset} at {tf}s timeframe.")
            
        # Start a loop to check for trade results (not needed in simulation as results are instant)
        # In a real app, this is where you'd poll/listen for order completion.

        # Keep the async thread alive and processing tasks
        while self.is_running:
            await asyncio.sleep(5) 

        logger.info("Bot main loop exited.")

    async def stop(self):
        """Stops the main bot loop and disconnects."""
        if not self.is_running: return

        self.is_running = False
        logger.info("Bot is stopping...")

        # Unsubscribe from all assets/timeframes
        for tf in self.available_timeframes:
            await self.client.unsubscribe_candles(asset=self.current_asset, timeframe=tf)
        
        await self.client.disconnect() 
        logger.info("Bot stopped and disconnected.")
        
    # --- Utility methods for the web interface ---
    
    def start_trading(self):
        self.is_trading = True
        logger.success("Trading is now ENABLED.")
        
    def stop_trading(self):
        self.is_trading = False
        logger.warning("Trading is now DISABLED.")

    async def set_asset(self, asset: str):
        if self.is_running:
            # Unsubscribe from old asset/timeframes
            for tf in self.available_timeframes:
                await self.client.unsubscribe_candles(asset=self.current_asset, timeframe=tf)
            
            # Update asset
            self.current_asset = asset
            
            # Subscribe to new asset/timeframes
            for tf in self.available_timeframes:
                await self.client.subscribe_candles(
                    asset=self.current_asset, 
                    timeframe=tf, 
                    callback=self.handle_candle
                )
            logger.info(f"Active trading asset changed to: {asset}. Resubscribed.")
        else:
            self.current_asset = asset
            logger.info(f"Active trading asset set to: {asset}. Will subscribe on start.")

    async def set_timeframe(self, timeframe: int):
        if timeframe in self.available_timeframes:
            self.current_timeframe = timeframe
            logger.info(f"Active analysis timeframe changed to: {timeframe}s")
        else:
            logger.error(f"Timeframe {timeframe} is not available in {self.available_timeframes}")
            
    def set_min_confidence(self, confidence: float):
        # Clamp confidence between 50% and 95%
        self.min_confidence = max(0.5, min(0.95, confidence))
        logger.info(f"Minimum confidence set to: {self.min_confidence:.2%}")
    
    def get_status(self) -> Dict:
        key = f"{self.current_asset}_{self.current_timeframe}"
        current_candles = self.market_data.get(key, {}).get("candles", [])

        return {
            "is_running": self.is_running,
            "is_trading": self.is_trading,
            "is_learning": self.is_learning,
            "connected": self.client.is_connected(),
            "simulation_mode": self.client.is_simulation(),
            "balance": self.client.balance,
            "current_asset": self.current_asset,
            "current_timeframe": self.current_timeframe,
            "patterns_detected": len(self.patterns_detected),
            "trades_this_hour": self.trades_this_hour,
            "pending_trades": len(self.pending_trades),
            "total_trades": len(self.trade_history),
            "agent_stats": self.agent.get_stats(),
            "knowledge_stats": self.knowledge_learner.get_stats(),
            "candle_count": len(current_candles)
        }
    
    def get_market_analysis(self) -> Dict:
        key = f"{self.current_asset}_{self.current_timeframe}"
        current_candles = self.market_data.get(key, {}).get("candles", [])
        
        return {
            "candles": current_candles, 
            "patterns": self.patterns_detected[:10],
            "levels": self.levels_detected,
            "indicators": self.indicator_values,
            "trend": self.candlestick_analyzer.get_trend(current_candles)
        }
    
    def get_trade_stats(self) -> Dict:
        # Simple statistics calculation
        total_trades = len(self.trade_history)
        wins = sum(1 for t in self.trade_history if t.get("outcome") == "WIN")
        losses = sum(1 for t in self.trade_history if t.get("outcome") == "LOSS")
        
        return {
            "history": self.trade_history[-50:][::-1], # Last 50 trades, newest first
            "total": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total_trades) if total_trades > 0 else 0
        }
