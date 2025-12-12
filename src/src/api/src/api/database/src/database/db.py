import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger

class Database:
    def __init__(self, db_path: str = "trading_bot.db"):
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def get_connection(self):
        if self.conn is None:
            # check_same_thread=False is crucial for Flask/asyncio compatibility
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. Trades Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER UNIQUE,
                asset TEXT NOT NULL,
                direction TEXT NOT NULL,
                amount REAL NOT NULL,
                confidence REAL,
                outcome TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. Learned Knowledge (from PDF/Web)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learned_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                relevance_score REAL DEFAULT 0.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 3. Model State (for ML persistence)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL UNIQUE,
                model_data BLOB,
                metrics TEXT,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    # --- Trade Methods ---
    # Simplified, the bot now manages the trade history in-memory for speed
    
    # --- Knowledge/Model Methods ---
    def save_knowledge(self, source: str, category: str, content: str, 
                       summary: str = None, relevance_score: float = 0):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO learned_knowledge (source, category, content, summary, relevance_score)
            VALUES (?, ?, ?, ?, ?)
        ''', (source, category, content, summary, relevance_score))
        conn.commit()
        return cursor.lastrowid
    
    def get_all_knowledge(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM learned_knowledge')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

# Instantiate the database class once
db = Database()
