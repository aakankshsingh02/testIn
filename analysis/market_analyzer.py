import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict
from ..utils.logger import logger
from .technical_analyzer import TechnicalAnalyzer

class MarketAnalyzer:
    def __init__(self):
        self.tech_analyzer = TechnicalAnalyzer()
    
    async def analyze_stock(self, symbol: str) -> Dict:
        try:
            # Fetch data
            stock = yf.Ticker(f"{symbol}.NS")
            data = stock.history(period="60d", interval="5m")
            
            if data.empty:
                raise ValueError("No data available for symbol")
            
            # Calculate indicators
            analysis_data = self.tech_analyzer.calculate_all_indicators(data)
            
            # Generate trading signal
            signal = self.tech_analyzer.generate_signal(analysis_data)
            
            # Get market context
            market_context = await self.get_market_context()
            
            last_row = analysis_data.iloc[-1]
            return {
                'symbol': symbol,
                'current_price': last_row['Close'],
                'signal': signal,
                'indicators': {
                    'rsi': last_row['RSI'],
                    'macd': last_row['MACD'],
                    'supertrend': last_row['Supertrend'],
                    'volume': last_row['Volume'],
                    'atr': last_row['ATR']
                },
                'market_context': market_context
            }
        
        except Exception as e:
            logger.error(f"Analysis failed for {symbol}: {str(e)}")
            raise
    
    async def get_market_context(self) -> Dict:
        try:
            # Get Nifty data
            nifty = yf.Ticker("^NSEI")
            nifty_data = nifty.history(period="1d")
            
            # Get India VIX data
            vix = yf.Ticker("^INDIAVIX")
            vix_data = vix.history(period="1d")
            
            return {
                'nifty_change': nifty_data['Close'].pct_change().iloc[-1] * 100,
                'india_vix': vix_data['Close'].iloc[-1],
                'market_status': 'open' if self.is_market_open() else 'closed'
            }
        except Exception as e:
            logger.error(f"Failed to get market context: {str(e)}")
            return {}
    
    @staticmethod
    def is_market_open() -> bool:
        now = datetime.now()
        return (
            now.weekday() < 5 and  # Monday to Friday
            9 <= now.hour < 15 or  # Between 9 AM and 3 PM
            (now.hour == 15 and now.minute == 0)  # At exactly 3 PM
        )