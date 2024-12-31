from typing import Dict, List
from datetime import datetime
import logging
from ..config import settings
from ..database.db_manager import db_manager

logger = logging.getLogger(__name__)

class PositionManager:
    def __init__(self):
        self.positions = {}
        self.daily_pnl = 0
        self.last_reset = datetime.now().date()

    def reset_daily_metrics(self):
        """Reset daily metrics if it's a new day"""
        current_date = datetime.now().date()
        if current_date > self.last_reset:
            self.daily_pnl = 0
            self.last_reset = current_date

    def can_trade(self, portfolio_value: float) -> bool:
        """Check if trading is allowed based on daily loss limits"""
        self.reset_daily_metrics()
        max_daily_loss = portfolio_value * (settings.MAX_DAILY_LOSS_PERCENT / 100)
        return self.daily_pnl > -max_daily_loss

    def calculate_position_size(self, portfolio_value: float, current_price: float) -> int:
        """Calculate safe position size based on portfolio value"""
        max_position_value = portfolio_value * (settings.MAX_POSITION_SIZE_PERCENT / 100)
        return int(max_position_value / current_price)

    def add_position(self, symbol: str, entry_price: float, quantity: int):
        """Add new trading position"""
        self.positions[symbol] = {
            'entry_price': entry_price,
            'quantity': quantity,
            'entry_time': datetime.now()
        }
        
        # Record in database
        db_manager.record_trade({
            'symbol': symbol,
            'entry_price': entry_price,
            'quantity': quantity,
            'trade_type': 'BUY',
            'entry_time': datetime.now()
        })

    def close_position(self, symbol: str, exit_price: float):
        """Close existing position and calculate P&L"""
        if symbol in self.positions:
            position = self.positions[symbol]
            pnl = (exit_price - position['entry_price']) * position['quantity']
            self.daily_pnl += pnl
            
            # Record in database
            db_manager.record_trade({
                'symbol': symbol,
                'entry_price': position['entry_price'],
                'exit_price': exit_price,
                'quantity': position['quantity'],
                'trade_type': 'SELL',
                'entry_time': position['entry_time'],
                'exit_time': datetime.now(),
                'pnl': pnl
            })
            
            del self.positions[symbol]
            return pnl
        return 0

    def get_active_positions(self) -> Dict:
        """Get all active positions"""
        return self.positions

    def update_position_values(self, current_prices: Dict[str, float]):
        """Update unrealized P&L for all positions"""
        unrealized_pnl = 0
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                current_price = current_prices[symbol]
                position['current_price'] = current_price
                position['unrealized_pnl'] = (
                    current_price - position['entry_price']
                ) * position['quantity']
                unrealized_pnl += position['unrealized_pnl']
        return unrealized_pnl