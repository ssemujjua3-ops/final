import asyncio
import os
import random
import time
from typing import Optional, Dict, List, Callable
from datetime import datetime
from loguru import logger

try:
    # Requires PocketOptionAPI-async installation
    from pocketoptionapi_async import AsyncPocketOptionClient, OrderDirection 
    POCKET_API_AVAILABLE = True
except ImportError:
    POCKET_API_AVAILABLE = False
    logger.warning("PocketOptionAPI not available, running in forced simulation mode")

class PocketOptionClient:
    def __init__(self, ssid: str = "", demo: bool = True):
        self.ssid = ssid or os.getenv("POCKET_OPTION_SSID", "")
        self.demo = demo
        self.connected = False
        self.api: Optional[AsyncPocketOptionClient] = None
        self.balance: float = 0
        # Key: "asset_timeframe", Value: List of callback functions
        self.candle_callbacks: Dict[str, List[Callable]] = {} 
        self.assets = [
            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc",
            "EURJPY_otc", "GBPJPY_otc", "EURGBP_otc", "USDCAD_otc"
        ]
        self.simulation_mode = not POCKET_API_AVAILABLE or not self.ssid or self.demo
        self._candle_simulator_task: Optional[asyncio.Task] = None
        
    async def connect(self) -> bool:
        if self.simulation_mode:
            logger.info("Running in simulation mode.")
            self.connected = True
            self.balance = 10000.0 if self.demo else 100.0 # Start balance
            return True
            
        try:
            self.api = AsyncPocketOptionClient(self.ssid)
            await self.api.connect()
            self.balance = await self.api.get_balance()
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Pocket Option API: {e}")
            return False

    async def disconnect(self):
        if self._candle_simulator_task:
            self._candle_simulator_task.cancel()
            self._candle_simulator_task = None
        
        if self.api and self.connected:
            await self.api.disconnect()
        self.connected = False
        self.balance = 0
        logger.info("Disconnected from Pocket Option.")

    async def subscribe_candles(self, asset: str, timeframe: int, callback: Callable):
        key = f"{asset}_{timeframe}"
        if key not in self.candle_callbacks:
            self.candle_callbacks[key] = []
        self.candle_callbacks[key].append(callback)

        # Start the simulator only if needed
        if self.simulation_mode and self._candle_simulator_task is None:
            self._candle_simulator_task = asyncio.create_task(self._candle_simulator())

    async def unsubscribe_candles(self, asset: str, timeframe: int):
        key = f"{asset}_{timeframe}"
        if key in self.candle_callbacks:
            del self.candle_callbacks[key]
        
    async def place_trade(self, asset: str, direction: str, amount: float, duration: int) -> Dict:
        if self.simulation_mode:
            self.balance -= amount
            logger.info(f"[SIMULATION] Trade placed: {direction} {asset} for ${amount} at {duration}s. New Balance: ${self.balance:.2f}")
            
            # Simulate trade result instantly for simplicity (in a real app, this is async)
            await asyncio.sleep(duration / 10) # Small delay for realism
            is_win = random.random() < 0.65  # 65% base win rate for simulation
            payout = 0.85 
            
            if is_win:
                profit = amount * payout
                self.balance += amount + profit
                outcome = "WIN"
            else:
                outcome = "LOSS"
                
            logger.info(f"[SIMULATION] Trade resulted in {outcome}. Balance: ${self.balance:.2f}")
            return {"id": random.randint(1000, 9999), "outcome": outcome}

        # Real API would go here
        order_direction = OrderDirection.CALL if direction == "CALL" else OrderDirection.PUT
        try:
            trade_id = await self.api.place_order(
                asset=asset, 
                direction=order_direction, 
                amount=amount, 
                duration=duration
            )
            return {"id": trade_id, "outcome": "PENDING"}
        except Exception as e:
            logger.error(f"Real API failed to place trade: {e}")
            return {"id": None, "outcome": "FAILED"}


    # --- Simulation Functions ---
    async def _candle_simulator(self):
        """Simulates real-time candle data for subscribed assets/timeframes."""
        base_prices = {asset: 1.0 + random.uniform(-0.01, 0.01) for asset in self.assets}
        
        while True:
            now = int(time.time())
            
            for key, callbacks in list(self.candle_callbacks.items()):
                if not callbacks: continue
                
                asset, timeframe_str = key.split('_')
                timeframe = int(timeframe_str)

                # Generate candle at the start of a new interval
                if now % timeframe == 0:
                    
                    if asset not in base_prices:
                        base_prices[asset] = 1.0
                        
                    base_price = base_prices[asset]
                    
                    # Generate random OHLC data 
                    change = random.uniform(-0.0005, 0.0005)
                    close_price = base_price * (1 + change)
                    
                    open_price = base_price * (1 + random.uniform(-0.0001, 0.0001))
                    high_price = max(open_price, close_price) * (1 + random.uniform(0.0001, 0.0003))
                    low_price = min(open_price, close_price) * (1 - random.uniform(0.0001, 0.0003))
                    
                    candle = {
                        "timestamp": now - timeframe, 
                        "open": round(open_price, 5),
                        "high": round(high_price, 5),
                        "low": round(low_price, 5),
                        "close": round(close_price, 5),
                        "volume": random.randint(100, 1000),
                        "asset": asset,
                        "timeframe": timeframe
                    }
                    base_prices[asset] = close_price 
                    
                    for callback in callbacks:
                        asyncio.create_task(callback(candle)) 
            
            await asyncio.sleep(1) # Check every second

    def is_connected(self) -> bool:
        return self.connected
        
    def is_simulation(self) -> bool:
        return self.simulation_mode
