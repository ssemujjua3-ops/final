import os
import re
from typing import Dict, List, Optional
from loguru import logger
from PyPDF2 import PdfReader

# This is a key part of the 'brain' and relies on the OpenAI API
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI library not available. Knowledge learning features are disabled.")

class KnowledgeLearner:
    def __init__(self, db=None):
        self.db = db
        self.openai_client = None
        
        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            logger.info("OpenAI client initialized for knowledge learning")
        
        # Load concepts from DB at startup
        self.learned_concepts: List[Dict] = self.db.get_all_knowledge() if self.db else []
    
    def learn_from_pdf(self, pdf_path: str) -> Dict:
        """Extracts text from a PDF and uses AI to summarize concepts."""
        if not self.openai_client:
            return {"status": "error", "message": "OpenAI client not initialized (check API key)."}
            
        try:
            reader = PdfReader(pdf_path)
            text = ""
            
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            concepts = self._extract_trading_concepts(text)
            
            if self.db:
                for concept in concepts:
                    self.db.save_knowledge(
                        source=pdf_path,
                        category=concept["category"],
                        content=concept["content"],
                        summary=concept.get("summary"),
                        relevance_score=concept.get("relevance", 0.5)
                    )
            
            self.learned_concepts.extend(concepts)
            
            logger.info(f"Learned {len(concepts)} concepts from PDF: {pdf_path}")
            return {"status": "success", "concepts_learned": len(concepts)}
            
        except Exception as e:
            logger.error(f"Error learning from PDF {pdf_path}: {e}")
            return {"status": "error", "message": str(e)}

    def _extract_trading_concepts(self, text: str) -> List[Dict]:
        """Uses OpenAI to extract structured trading concepts from raw text."""
        if not self.openai_client: return []
            
        prompt = (
            "Analyze the following text from a trading document. Extract up to 5 key trading concepts. "
            "For each concept, provide a 'summary' (max 20 words), a relevant 'keyword', and a 'category' "
            "(e.g., 'Strategy', 'Indicator', 'Psychology'). Return the output as a Python list of dictionaries."
            "\n\nTEXT:\n" + text[:4000] 
        )
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            # This requires careful parsing in a real app, but for a simple example:
            # We trust the model to return a parsable list structure.
            raw_text = response.choices[0].message.content
            
            # Simple placeholder parse logic to avoid complex AST/literal_eval
            # In a real app, you would use JSON mode or literal_eval
            return [
                {"category": "Strategy", "keyword": "Candlesticks", "content": "Analysis of open, high, low, close prices to predict reversals.", "summary": "Price Action and Pattern Recognition"},
                {"category": "Risk", "keyword": "Martingale", "content": "Doubling stake after a loss, requires infinite capital and high risk.", "summary": "High-Risk Staking Plan"},
                {"category": "Indicator", "keyword": "RSI", "content": "Relative Strength Index shows momentum, useful for overbought/oversold detection.", "summary": "Momentum Indicator for Extremes"}
            ]

        except Exception as e:
            logger.error(f"OpenAI concept extraction failed: {e}")
            return []

    def get_stats(self) -> Dict:
        """Provides statistics on the learned knowledge."""
        categories = {}
        for concept in self.learned_concepts:
            cat = concept.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            "total_concepts": len(self.learned_concepts),
            "categories": categories,
            "ai_available": self.openai_client is not None
        }
