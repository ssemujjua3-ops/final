import numpy as np
import pickle
import os
from typing import Dict, List, Optional, Tuple
from loguru import logger
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

class TradingAgent:
    def __init__(self, model_path: str = "models"):
        self.model_path = model_path
        os.makedirs(model_path, exist_ok=True) 
        
        self.direction_model = GradientBoostingClassifier(
            n_estimators=50, max_depth=5, random_state=42
        )
        self.scaler = StandardScaler()
        
        self.is_trained = False
        self.experience_buffer: List[Dict] = []
        self.min_training_samples = 50 
        
        self._load_models()
    
    def _load_models(self):
        # In a real app, this would also load the scaler and check model version
        try:
            direction_path = os.path.join(self.model_path, "direction_model.pkl")
            if os.path.exists(direction_path):
                with open(direction_path, 'rb') as f:
                    self.direction_model = pickle.load(f)
                self.is_trained = True
                logger.info("Direction model loaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to load models: {e}. Starting untranied.")
            self.is_trained = False

    def _save_models(self):
        try:
            with open(os.path.join(self.model_path, "direction_model.pkl"), 'wb') as f:
                pickle.dump(self.direction_model, f)
            logger.info("Models saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save models: {e}")

    # --- Training & Data Management ---
    def add_experience(self, experience: Dict):
        """Adds a completed trade experience (features + outcome) to the buffer."""
        self.experience_buffer.append(experience)
    
    def retrain_if_needed(self):
        """Triggers a re-training session if enough new experience is gathered."""
        if len(self.experience_buffer) < self.min_training_samples:
            return

        logger.info(f"Retraining ML model with {len(self.experience_buffer)} samples...")
        
        try:
            # 1. Prepare Data: Features (X) and Labels (Y)
            X_raw = [exp["features"] for exp in self.experience_buffer if exp.get("features")]
            
            # Map outcome (WIN/LOSS) to numerical labels (1=WIN, 0=LOSS)
            Y = np.array([1 if exp["outcome"] == "WIN" else 0 for exp in self.experience_buffer if exp.get("features")])
            
            if not X_raw or len(X_raw) != len(Y):
                logger.warning("Inconsistent or missing feature data for retraining.")
                return

            X = np.array(X_raw)
            
            # 2. Scale Features
            X_scaled = self.scaler.fit_transform(X)
            
            # 3. Train Model
            self.direction_model.fit(X_scaled, Y)
            self.is_trained = True
            
            # 4. Save and Clear Buffer (Optional: partial clearing to retain old knowledge)
            self._save_models()
            self.experience_buffer = [] # Clear buffer after successful training
            logger.success("ML Model retrained successfully.")

        except Exception as e:
            logger.error(f"ML Retraining failed: {e}")

    # --- Trade Decision Logic ---
    def _extract_features(self, context: Dict) -> Optional[List[float]]:
        """Transforms market data into numerical features for the ML model."""
        indicators = context.get("indicators", {})
        patterns = context.get("patterns", [])
        candles = context.get("candles", [])
        
        if not indicators or not candles:
            return None
        
        # 1. RSI value
        rsi_val = indicators.get("rsi", {}).get("value", 50.0)
        
        # 2. MACD histogram (momentum)
        macd_hist = indicators.get("macd", {}).get("histogram", 0.0)
        
        # 3. Normalized ATR (Volatility)
        atr_val = indicators.get("atr", 0.001)
        
        # 4. Candlestick size (relative to ATR)
        if candles:
            body_size = abs(candles[0]['close'] - candles[0]['open'])
            body_to_atr = body_size / atr_val
        else:
            body_to_atr = 0

        # 5. Pattern Sums
        bullish_pattern_strength = sum(p.get("strength", 0) for p in patterns if p.get("signal") == "CALL")
        bearish_pattern_strength = sum(p.get("strength", 0) for p in patterns if p.get("signal") == "PUT")
        
        features = [
            rsi_val, 
            macd_hist, 
            atr_val,
            body_to_atr,
            bullish_pattern_strength, 
            bearish_pattern_strength
        ]
        
        return features

    def _heuristic_score(self, context: Dict) -> Tuple[float, float]:
        """Calculates a pattern/indicator-based confidence score (pre-ML)."""
        call_score = 0.0
        put_score = 0.0
        patterns = context.get("patterns", [])
        indicators = context.get("indicators", {})
        
        # 1. Pattern signals
        for pattern in patterns[:3]: 
            strength = pattern.get("strength", 0.5)
            if pattern.get("signal") == "CALL": call_score += strength * 1.5
            elif pattern.get("signal") == "PUT": put_score += strength * 1.5
        
        # 2. Indicator signals
        rsi = indicators.get("rsi", {})
        if rsi.get("signal") == "oversold": call_score += 0.5
        elif rsi.get("signal") == "overbought": put_score += 0.5
            
        return call_score, put_score
        
    def get_trade_decision(self, context: Dict) -> Dict:
        """Determines the final trade direction and confidence."""
        
        features = self._extract_features(context)
        call_score, put_score = self._heuristic_score(context)

        final_confidence = 0.5
        final_direction = "HOLD"
        
        if self.is_trained and features:
            try:
                # Scale features using the fitted scaler
                X = self.scaler.transform([features])
                
                # Predict probability for the classes (0=LOSS, 1=WIN)
                proba = self.direction_model.predict_proba(X)[0] 
                
                # The model predicts the probability of the trade being a WIN
                ml_win_proba = proba[1] 
                
                # Use a simple threshold to determine if ML supports CALL or PUT
                # For this example, we assume we use the pattern/heuristic signal
                # and the ML model simply validates the *WIN probability*
                
                # The ML confidence is the probability of a win given the features
                ml_confidence = ml_win_proba

            except Exception as e:
                logger.warning(f"ML prediction failed: {e}. Using only heuristics.")
                ml_confidence = 0.5
        else:
            ml_confidence = 0.5

        # Combine Heuristic and ML: Use the heuristic direction, but adjust confidence
        # based on ML's calculated probability of a successful trade.
        total = call_score + put_score
        
        if total > 0.5:
            if call_score > put_score:
                final_direction = "CALL"
                heuristic_conf = call_score / total
            else:
                final_direction = "PUT"
                heuristic_conf = put_score / total

            # Final Confidence = weighted average of heuristic signal strength and ML win probability
            # The ML model acts as a powerful filter/validator.
            final_confidence = (heuristic_conf * 0.4) + (ml_confidence * 0.6)
        
        # Apply min/max limits
        return {
            "direction": final_direction,
            "confidence": max(0.5, min(final_confidence, 0.95))
        }

    # --- Money Management ---
    
    def determine_expiration(self, volatility: float, pattern_strength: float) -> int:
        """Determines the optimal trade duration in seconds."""
        
        if volatility > 0.002: base_exp = 60
        elif volatility > 0.001: base_exp = 120
        else: base_exp = 300
        
        if pattern_strength > 0.8: return base_exp 
        else: return base_exp * 2 
    
    def get_trade_amount(self, balance: float, confidence: float, 
                         base_pct: float = 0.02) -> float:
        """Calculates trade amount using a simple Martingale-like confidence multiplier."""
        
        # Risk management: Martingale-like scaling based on confidence
        if confidence < 0.65:
            pct = base_pct * 0.5 # Half stake
        elif confidence < 0.75:
            pct = base_pct # Base stake
        else:
            pct = base_pct * 1.5 # Increased stake
        
        amount = balance * pct
        # Enforce minimum of $1 and maximum of 5% of balance
        return max(1, min(amount, balance * 0.05)) 
    
    def get_stats(self) -> Dict:
        # Calculate win rate from the training buffer
        if not self.experience_buffer:
            return {
                "total_experiences": 0,
                "is_trained": self.is_trained,
                "win_rate": 0
            }
        
        wins = sum(1 for exp in self.experience_buffer if exp.get("outcome") == "WIN")
        total = len(self.experience_buffer)
        
        return {
            "total_experiences": total,
            "is_trained": self.is_trained,
            "win_rate": (wins / total) if total > 0 else 0
        }
