import asyncio
from typing import Dict, List, Optional
from loguru import logger
from datetime import datetime, timedelta

class TournamentManager:
    """Handles interaction with Pocket Option tournaments."""
    def __init__(self, client, agent, db):
        self.client = client
        self.agent = agent
        self.db = db
        self.joined_tournaments: List[str] = []
        
    async def get_all_active_free_tournaments(self) -> List[Dict]:
        """Fetches all active tournaments with a $0 entry fee."""
        tournaments = await self.client.get_tournaments() 
        return [t for t in tournaments if t.get("entry_fee", 0) == 0 and t.get("status") == "active"]

    async def join_tournament_by_id(self, tournament_id: str) -> bool:
        """Attempts to join a specific tournament."""
        if tournament_id in self.joined_tournaments:
            logger.info(f"Already joined tournament ID: {tournament_id}")
            return True
        
        success = await self.client.join_tournament(tournament_id)
        if success:
            self.joined_tournaments.append(tournament_id)
            logger.success(f"Successfully joined tournament: {tournament_id}")
        else:
            logger.error(f"Failed to join tournament: {tournament_id}")
            
        return success

class TournamentScheduler:
    """A background task to automatically find and join free tournaments."""
    def __init__(self, manager: TournamentManager):
        self.manager = manager
        self.is_running = False
        self.last_check: Optional[datetime] = None
        
    def start_scheduler(self):
        """Starts the background task to check for and join tournaments."""
        if self.is_running: return
        
        self.is_running = True
        # Use asyncio.create_task to run the coroutine in the main bot loop
        asyncio.create_task(self._run_scheduler()) 
        logger.info("Tournament scheduler started.")

    async def _run_scheduler(self):
        while self.is_running:
            # Only check once per hour
            if self.last_check is None or (datetime.now() - self.last_check) > timedelta(hours=1):
                logger.info("Checking for new free tournaments...")
                try:
                    free_tournaments = await self.manager.get_all_active_free_tournaments()
                    for t in free_tournaments:
                        await self.manager.join_tournament_by_id(t["id"])
                        
                    self.last_check = datetime.now()
                except Exception as e:
                    logger.error(f"Tournament scheduler failed to check: {e}")
            
            await asyncio.sleep(600) # Sleep for 10 minutes
