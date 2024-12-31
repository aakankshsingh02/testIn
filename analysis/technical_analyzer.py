import pandas as pd
import numpy as np
import talib
from typing import Dict

class TechnicalAnalyzer:
    @staticmethod
    def calculate_all_indicators(data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        # Trend indicators
        df['SMA_20'] = talib.SMA(df['Close'], timeperiod=20)
        df['SMA_50'] = talib.SMA(df['Close'], timeperiod=50)
        df['EMA_9'] = talib.EMA(df['Close'], timeperiod=9)
        
        # Momentum indicators
        df['RSI'] = talib.RSI(df['Close'], timeperiod=14)
        df['MACD'], df['MACD_Signal'], _ = talib.MACD(df['Close'])
        
        # Volatility indicators
        df['ATR'] = talib.ATR(df['High'], df['Low'], df['Close'], timeperiod=14)
        df['BB_Upper'], df['BB_Middle'], df['BB_Lower'] = talib.BBANDS(df['Close'])
        
        # Volume indicators
        df['OBV'] = talib.OBV(df['Close'], df['Volume'])
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        
        # Indian market specific indicators
        df['Supertrend'] = TechnicalAnalyzer.calculate_supertrend(df)
        
        return df
    
    @staticmethod
    def calculate_supertrend(data: pd.DataFrame, period=7, multiplier=3) -> pd.Series:
        hl2 = (data['High'] + data['Low']) / 2
        atr = talib.ATR(data['High'], data['Low'], data['Close'], timeperiod=period)
        
        basic_upperband = hl2 + (multiplier * atr)
        basic_lowerband = hl2 - (multiplier * atr)
        
        supertrend = pd.Series(index=data.index, dtype=float)
        direction = pd.Series(index=data.index, dtype=int)
        
        for i in range(1, len(data.index)):
            if data['Close'][i] > basic_upperband[i-1]:
                supertrend[i] = basic_lowerband[i]
                direction[i] = 1
            elif data['Close'][i] < basic_lowerband[i-1]:
                supertrend[i] = basic_upperband[i]
                direction[i] = -1
            else:
                supertrend[i] = supertrend[i-1]
                direction[i] = direction[i-1]
                
        return supertrend
    
    @staticmethod
    def generate_signal(data: pd.DataFrame) -> Dict:
        last_row = data.iloc[-1]
        
        # Initialize scoring system
        buy_signals = 0
        sell_signals = 0
        total_signals = 7
        
        # Trend signals
        if last_row['EMA_9'] > last_row['SMA_20']:
            buy_signals += 1
        else:
            sell_signals += 1
        
        if last_row['SMA_20'] > last_row['SMA_50']:
            buy_signals += 1
        else:
            sell_signals += 1
        
        # Momentum signals
        if 30 <= last_row['RSI'] <= 70:
            if last_row['RSI'] > 50:
                buy_signals += 1
            else:
                sell_signals += 1
        elif last_row['RSI'] < 30:
            buy_signals += 1
        else:
            sell_signals += 1
        
        # MACD signals
        if last_row['MACD'] > last_row['MACD_Signal']:
            buy_signals += 1
        else:
            sell_signals += 1
        
        # Volatility signals
        if last_row['Close'] > last_row['BB_Middle']:
            buy_signals += 1
        else:
            sell_signals += 1
        
        # Volume signals
        if last_row['Volume'] > last_row['Volume_SMA']:
            if last_row['Close'] > data['Close'].iloc[-2]:
                buy_signals += 1
            else:
                sell_signals += 1
        
        # Calculate signal strength
        strength = max(buy_signals, sell_signals) / total_signals
        
        return {
            'direction': 1 if buy_signals > sell_signals else -1 if sell_signals > buy_signals else 0,
            'strength': strength,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals
        }