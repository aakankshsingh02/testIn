from typing import Dict, List, Optional
from datetime import datetime
import logging
import asyncio
from ..automation.groww_automation import GrowwAutomation
from ..trading.position_manager import PositionManager
from ..analysis.market_analyzer import MarketAnalyzer
from ..config import settings
from ..utils.logger import logger

class Trader:
    def __init__(self):
        self.automation = GrowwAutomation()
        self.position_manager = PositionManager()
        self.market_analyzer = MarketAnalyzer()
        self.is_active = False
        self.portfolio_value = 0
        self.risk_per_trade = 0.02  # 2% risk per trade
        self.trailing_sl_percent = 0.02  # 2% trailing stop loss
        self.target_profit_percent = 0.03  # 3% target profit
        
    async def initialize(self, portfolio_value: float) -> bool:
        """Initialize the trader with portfolio value and login to Groww"""
        try:
            self.portfolio_value = portfolio_value
            await self.automation.login()
            self.is_active = True
            logger.info(f"Trader initialized with portfolio value: ₹{portfolio_value}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize trader: {str(e)}")
            return False

    async def execute_trade(self, symbol: str, trade_type: str, quantity: int) -> Dict:
        """Execute a trade with risk management"""
        try:
            # Pre-trade checks
            if not self.is_active:
                raise Exception("Trader is not active")
            
            if not self._validate_trade(symbol, trade_type, quantity):
                raise Exception("Trade validation failed")
            
            # Get current market price
            current_price = await self.automation.get_stock_price(symbol)
            
            # Calculate trade value
            trade_value = current_price * quantity
            
            # Check if trade value exceeds risk limits
            if not self._check_risk_limits(trade_value):
                raise Exception("Trade exceeds risk limits")
            
            # Execute the trade
            trade_result = await self.automation.execute_trade(symbol, quantity, trade_type)
            
            if trade_result['status'] == 'success':
                # Update position manager
                if trade_type == "BUY":
                    self.position_manager.add_position(
                        symbol,
                        trade_result['price'],
                        quantity,
                        stop_loss=trade_result['price'] * (1 - self.trailing_sl_percent),
                        target=trade_result['price'] * (1 + self.target_profit_percent)
                    )
                else:
                    self.position_manager.close_position(symbol, trade_result['price'])
                
                logger.info(f"Successfully executed {trade_type} trade for {symbol}")
                return trade_result
            
            raise Exception("Trade execution failed")
            
        except Exception as e:
            logger.error(f"Trade execution failed: {str(e)}")
            raise

    def _validate_trade(self, symbol: str, trade_type: str, quantity: int) -> bool:
        """Validate trade parameters"""
        try:
            # Check trade type
            if trade_type not in ["BUY", "SELL"]:
                logger.error(f"Invalid trade type: {trade_type}")
                return False
            
            # Check quantity
            if quantity <= 0:
                logger.error("Quantity must be positive")
                return False
            
            # Check if selling existing position
            if trade_type == "SELL":
                position = self.position_manager.get_position(symbol)
                if not position:
                    logger.error(f"No position found for {symbol}")
                    return False
                if position['quantity'] < quantity:
                    logger.error(f"Insufficient quantity for {symbol}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Trade validation failed: {str(e)}")
            return False

    def _check_risk_limits(self, trade_value: float) -> bool:
        """Check if trade complies with risk management rules"""
        try:
            # Check maximum trade value
            max_trade_value = self.portfolio_value * self.risk_per_trade
            if trade_value > max_trade_value:
                logger.warning(f"Trade value (₹{trade_value}) exceeds max allowed (₹{max_trade_value})")
                return False
            
            # Check daily loss limit
            if not self.position_manager.can_trade(self.portfolio_value):
                logger.warning("Daily loss limit reached")
                return False
            
            # Check total exposure
            current_exposure = self.position_manager.get_total_exposure()
            max_exposure = self.portfolio_value * settings.MAX_POSITION_SIZE_PERCENT / 100
            if current_exposure + trade_value > max_exposure:
                logger.warning("Maximum exposure limit reached")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Risk check failed: {str(e)}")
            return False

    async def update_trailing_stops(self):
        """Update trailing stop losses for all positions"""
        try:
            positions = self.position_manager.get_active_positions()
            
            for symbol, position in positions.items():
                current_price = await self.automation.get_stock_price(symbol)
                
                # Update trailing stop if price has moved up
                if current_price > position['entry_price']:
                    new_stop = current_price * (1 - self.trailing_sl_percent)
                    if new_stop > position['stop_loss']:
                        self.position_manager.update_stop_loss(symbol, new_stop)
                        logger.info(f"Updated trailing stop for {symbol} to ₹{new_stop}")
                
                # Check if stop loss or target hit
                if current_price <= position['stop_loss'] or current_price >= position['target']:
                    await self.execute_trade(symbol, "SELL", position['quantity'])
                    logger.info(f"Exit triggered for {symbol} at ₹{current_price}")
                    
        except Exception as e:
            logger.error(f"Failed to update trailing stops: {str(e)}")

    async def monitor_positions(self):
        """Monitor and manage open positions"""
        while self.is_active:
            try:
                await self.update_trailing_stops()
                
                # Update position values
                positions = self.position_manager.get_active_positions()
                current_prices = {}
                
                for symbol in positions:
                    current_prices[symbol] = await self.automation.get_stock_price(symbol)
                
                self.position_manager.update_position_values(current_prices)
                
                # Sleep before next update
                await asyncio.sleep(settings.SCAN_INTERVAL)
                
            except Exception as e:
                logger.error(f"Position monitoring error: {str(e)}")
                await asyncio.sleep(60)

    def calculate_position_size(self, current_price: float) -> int:
        """Calculate position size based on risk management rules"""
        try:
            risk_amount = self.portfolio_value * self.risk_per_trade
            max_quantity = int(risk_amount / current_price)
            
            # Ensure minimum quantity
            if max_quantity < 1:
                logger.warning("Calculated quantity too small")
                return 0
            
            return max_quantity
            
        except Exception as e:
            logger.error(f"Position size calculation failed: {str(e)}")
            return 0

    async def close_all_positions(self) -> List[Dict]:
        """Close all open positions"""
        try:
            positions = self.position_manager.get_active_positions()
            results = []
            
            for symbol, position in positions.items():
                trade_result = await self.execute_trade(
                    symbol, "SELL", position['quantity']
                )
                results.append(trade_result)
            
            logger.info("All positions closed")
            return results
            
        except Exception as e:
            logger.error(f"Failed to close all positions: {str(e)}")
            raise

    def stop(self):
        """Stop the trader"""
        self.is_active = False
        self.automation.cleanup()
        logger.info("Trader stopped")