import asyncio
import os
import threading
from dotenv import load_dotenv

# Load environment variables (like POCKET_OPTION_SSID or OPENAI_API_KEY)
load_dotenv()

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from loguru import logger

# Import the core bot logic
from src.trading_bot import TradingBot

# --- Setup ---
app = Flask(__name__, static_folder=".")
CORS(app) # Enable CORS for development
logger.add("trading_bot.log", rotation="10 MB", level="INFO")

# Instantiate the bot (checks for POCKET_OPTION_SSID in .env)
BOT_SSID = os.getenv("POCKET_OPTION_SSID")
BOT_DEMO = os.getenv("POCKET_OPTION_MODE", "demo").lower() == "demo"
bot = TradingBot(ssid=BOT_SSID, demo=BOT_DEMO)

# --- Flask Routes ---

@app.route('/')
def index():
    """Serves the main web interface file."""
    return send_from_directory('.', 'index.html')

@app.route('/status', methods=['GET'])
def get_status():
    """Returns the current status of the bot."""
    return jsonify(bot.get_status())

@app.route('/market-analysis', methods=['GET'])
def get_market_analysis():
    """Returns the latest candle data, patterns, and indicators for the chart."""
    return jsonify(bot.get_market_analysis())

@app.route('/trade-stats', methods=['GET'])
def get_trade_stats():
    """Returns the trade history and performance statistics."""
    return jsonify(bot.get_trade_stats())

@app.route('/action', methods=['POST'])
def handle_action():
    """Handles commands to start/stop the bot and trading."""
    data = request.json
    action = data.get('action')
    value = data.get('value')
    
    # Run bot actions in the asyncio loop
    async def run_async_action():
        if action == 'start':
            await bot.start()
        elif action == 'stop':
            await bot.stop()
        elif action == 'start_trading':
            bot.start_trading()
        elif action == 'stop_trading':
            bot.stop_trading()
        elif action == 'set_asset':
            await bot.set_asset(value)
        elif action == 'set_timeframe':
            await bot.set_timeframe(int(value))
        elif action == 'set_confidence':
            bot.set_min_confidence(float(value))
        elif action == 'join_tournament':
            manager = bot.tournament_manager
            await manager.join_tournament_by_id(value)
        
    try:
        if action in ['start', 'stop']:
            # For start/stop, we handle the thread/loop state
            if action == 'start' and not bot.is_running:
                # Start the bot in its own thread to run the asyncio loop
                bot_thread = threading.Thread(target=_start_bot_thread, daemon=True)
                bot_thread.start()
                return jsonify({"status": "success", "message": "Bot started in background thread."})
            elif action == 'stop' and bot.is_running:
                # Stopping is done inside the loop
                asyncio.run_coroutine_threadsafe(run_async_action(), bot_loop).result(5)
                return jsonify({"status": "success", "message": "Bot stopped."})
            return jsonify({"status": "info", "message": f"Bot already in {action} state."})
        
        elif bot.is_running:
            # All other actions are sent to the running asyncio loop
            asyncio.run_coroutine_threadsafe(run_async_action(), bot_loop).result(5)
            return jsonify({"status": "success", "message": f"Action '{action}' executed."})
        else:
            return jsonify({"status": "error", "message": "Bot is not running. Start it first."}), 400
            
    except Exception as e:
        logger.error(f"Action failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    """Handles PDF upload for AI knowledge learning."""
    if 'pdf' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
    file = request.files['pdf']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
    
    if file and file.filename.endswith('.pdf'):
        temp_path = os.path.join("/tmp", file.filename)
        file.save(temp_path)
        
        # Run learning in the loop
        async def run_learning():
            return bot.knowledge_learner.learn_from_pdf(temp_path)
        
        try:
            # Since learning is synchronous/blocking inside the K-Learner, 
            # we should run it in a separate thread/executor if it were slow.
            # For simplicity, we just run it in the main loop thread for now.
            result = asyncio.run_coroutine_threadsafe(run_learning(), bot_loop).result(60)
            os.remove(temp_path)
            return jsonify({"status": "success", "message": f"Learning complete. Concepts: {result.get('concepts_learned', 0)}"})
        except Exception as e:
            logger.error(f"PDF Learning failed: {e}")
            os.remove(temp_path)
            return jsonify({"status": "error", "message": f"PDF processing failed: {e}"}), 500

    return jsonify({"status": "error", "message": "Invalid file type."}), 400

# --- Asynchronous Bot Execution ---
bot_loop = asyncio.new_event_loop()

def _start_bot_thread():
    """Runs the asyncio event loop for the bot in a separate thread."""
    asyncio.set_event_loop(bot_loop)
    bot_loop.run_until_complete(bot.start())

if __name__ == '__main__':
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000)
    # The bot's asyncio loop is started via the /action route
