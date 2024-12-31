from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncio
import logging
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .automation.groww_automation import GrowwAutomation
from .analysis.market_analyzer import MarketAnalyzer
from .trading.position_manager import PositionManager
from .database.db_manager import db_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app setup
app = FastAPI(title="Automated Trading System")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request validation
class StartTrading(BaseModel):
    symbols: List[str]
    portfolio_value: float = 100000

class AlertRequest(BaseModel):
    symbol: str
    price_target: float
    alert_type: str  # "above" or "below"

class TradingSystem:
    def __init__(self):
        self.automation = GrowwAutomation()
        self.analyzer = MarketAnalyzer()
        self.position_manager = PositionManager()
        self.is_trading = False
        self.watched_symbols = []
        self.portfolio_value = 0
        self.trading_task = None

    async def start(self, symbols: List[str], portfolio_value: float):
        """Start the trading system"""
        if not self.is_trading:
            try:
                # Login to Groww
                await self.automation.login()
                self.watched_symbols = symbols
                self.portfolio_value = portfolio_value
                self.is_trading = True
                
                # Start trading loop
                self.trading_task = asyncio.create_task(self.trading_loop())
                logger.info(f"Trading system started with symbols: {symbols}")
                return {"status": "started", "symbols": symbols}
            except Exception as e:
                logger.error(f"Failed to start trading system: {str(e)}")
                raise

    async def stop(self):
        """Stop the trading system"""
        if self.is_trading:
            self.is_trading = False
            if self.trading_task:
                self.trading_task.cancel()
            await self.close_all_positions()
            logger.info("Trading system stopped")
        return {"status": "stopped"}

    async def close_all_positions(self):
        """Close all open positions"""
        positions = self.position_manager.get_active_positions()
        for symbol in positions:
            try:
                current_price = await self.automation.get_stock_price(symbol)
                position = positions[symbol]
                await self.automation.execute_trade(
                    symbol, position['quantity'], "SELL"
                )
                self.position_manager.close_position(symbol, current_price)
            except Exception as e:
                logger.error(f"Failed to close position for {symbol}: {str(e)}")

    async def trading_loop(self):
        """Main trading loop"""
        while self.is_trading:
            try:
                current_time = datetime.now().time()
                
                # Only trade during market hours
                if (current_time.hour >= settings.MARKET_OPEN_HOUR and 
                    current_time.hour < settings.MARKET_CLOSE_HOUR):
                    
                    for symbol in self.watched_symbols:
                        # Skip if market is highly volatile
                        market_context = await self.analyzer.get_market_context()
                        if market_context.get('india_vix', 0) > 25:  # High volatility threshold
                            logger.warning(f"Market too volatile (VIX: {market_context['india_vix']})")
                            continue
                        
                        # Analyze stock
                        analysis = await self.analyzer.analyze_stock(symbol)
                        
                        # Check if we can trade
                        if self.position_manager.can_trade(self.portfolio_value):
                            await self.process_signals(symbol, analysis)
                        else:
                            logger.warning("Daily loss limit reached")
                        
                        # Update positions with current prices
                        if symbol in self.position_manager.positions:
                            current_prices = {symbol: analysis['current_price']}
                            self.position_manager.update_position_values(current_prices)
                
                # Sleep before next iteration
                await asyncio.sleep(settings.SCAN_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {str(e)}")
                await asyncio.sleep(60)  # Longer sleep on error

    async def process_signals(self, symbol: str, analysis: Dict):
        """Process trading signals and execute trades"""
        try:
            signal = analysis['signal']
            current_price = analysis['current_price']
            
            # Check signal strength
            if signal['strength'] >= settings.MIN_SIGNAL_STRENGTH:
                if signal['direction'] == 1 and symbol not in self.position_manager.positions:
                    # Buy signal
                    quantity = self.position_manager.calculate_position_size(
                        self.portfolio_value, current_price
                    )
                    if quantity > 0:
                        trade = await self.automation.execute_trade(symbol, quantity, "BUY")
                        if trade['status'] == 'success':
                            self.position_manager.add_position(symbol, current_price, quantity)
                            logger.info(f"Opened position for {symbol}: {quantity} shares at ₹{current_price}")
                            
                elif signal['direction'] == -1 and symbol in self.position_manager.positions:
                    # Sell signal
                    position = self.position_manager.positions[symbol]
                    trade = await self.automation.execute_trade(
                        symbol, position['quantity'], "SELL"
                    )
                    if trade['status'] == 'success':
                        pnl = self.position_manager.close_position(symbol, current_price)
                        logger.info(f"Closed position for {symbol} with P&L: ₹{pnl}")
                        
        except Exception as e:
            logger.error(f"Failed to process signals for {symbol}: {str(e)}")

# Initialize trading system
trading_system = TradingSystem()

# API Routes
@app.post("/start")
async def start_trading(request: StartTrading):
    """Start the trading system"""
    try:
        return await trading_system.start(request.symbols, request.portfolio_value)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop")
async def stop_trading():
    """Stop the trading system"""
    try:
        return await trading_system.stop()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/positions")
async def get_positions():
    """Get all active positions"""
    try:
        positions = trading_system.position_manager.get_active_positions()
        return {
            "positions": positions,
            "total_pnl": sum(p.get('unrealized_pnl', 0) for p in positions.values())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analysis/{symbol}")
async def get_analysis(symbol: str):
    """Get current analysis for a symbol"""
    try:
        return await trading_system.analyzer.analyze_stock(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alerts")
async def create_alert(alert: AlertRequest):
    """Create a new price alert"""
    try:
        await db_manager.add_alert({
            "symbol": alert.symbol,
            "price_target": alert.price_target,
            "alert_type": alert.alert_type,
            "triggered": False,
            "created_at": datetime.now()
        })
        return {"status": "success", "message": "Alert created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/performance")
async def get_performance():
    """Get trading performance metrics"""
    try:
        return await db_manager.get_performance_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/market_status")
async def get_market_status():
    """Get current market status"""
    try:
        return await trading_system.analyzer.get_market_context()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)