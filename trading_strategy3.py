import math
import time
from binance.client import Client
import pandas as pd
import talib
import plotly.graph_objects as go

class TradingBot:
    def __init__(self):
        self.balance = 1000
        self.client = client
        self.btc_balance = 0
        self.total_money_spent = 0
        self.fee = 0.00017  # Trading fee
        self.long_order = False
        self.short_order = False
        self.long_trades = 0
        self.successful_long_trades = 0
        self.sum_pnl = 0
        self.short_trades = 0
        self.successful_short_trades = 0
        self.sum_pnl_short = 0
        self.max_realized_loss = 0

    def calculate_indicators(self, df):
        df['macd'], df['macdsignal'], df['macdhist'] = talib.MACD(df['close'])
        df['stochrsi'], df['stochrsi_signal'] = talib.STOCHRSI(df['close'])
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'])
        df['ema'] = talib.EMA(df['close'])
        df['cci'] = talib.CCI(df['high'], df['low'], df['close'])
        df['vwap'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
        df['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'])
        df['williams_r'] = talib.WILLR(df['high'], df['low'], df['close'])
        df['adx'] = talib.ADX(df['high'], df['low'], df['close'])  # New
        df['psar'] = talib.SAR(df['high'], df['low'])  # New

        # Ichimoku Clouds
        high_9 = df['high'].rolling(window=9).max()
        low_9 = df['low'].rolling(window=9).min()
        df['tenkan_sen'] = (high_9 + low_9) / 2

        high_26 = df['high'].rolling(window=26).max()
        low_26 = df['low'].rolling(window=26).min()
        df['kijun_sen'] = (high_26 + low_26) / 2

        df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(26)
        df['senkou_span_b'] = ((df['high'].rolling(window=52).max() + df['low'].rolling(window=52).min()) / 2).shift(26)

        df['chikou_span'] = df['close'].shift(-26)

        # Volume Profile
        df['volume_profile'] = df['volume'] * (df['high'] + df['low'] + df['close']) / 3
        df['volume_profile_shifted'] = df['volume_profile'].shift(1)

    
        return df

    def long_signal(self, row):
        signals = [
        row['macd'] > row['macdsignal'] + 0.16,  
        row['stochrsi'] < 3,  
        row['macdhist'] > 0.0285,  
        row['cci'] < -565,  
        row['close'] < row['vwap'] - 0.026,  
        row['mfi'] < 3.5 , 
        row['williams_r'] < -98 , 
        row['adx'] > 35,  # CHECKED
        row['close'] > row['psar'] , 
        (row['close'] > row['senkou_span_a'] and row['close'] > row['senkou_span_b'] and 
                              row['tenkan_sen'] > row['kijun_sen'] and  
                              row['chikou_span'] > row['close'] and  
                              row['senkou_span_a'] > row['senkou_span_b']) ,
        row['volume_profile'] > row['volume_profile_shifted'] * 1.35  # CHECKED
        ]
        return sum(signals) >= 6

    def short_signal(self, row):
        signals = [
            row['macd'] < row['macdsignal'] - 0.16,  
            row['stochrsi'] > 97,  
            row['macdhist'] < -0.0285,  
            row['cci'] > 565, 
            row['close'] > row['vwap'] + 0.026,  
            row['mfi'] > 96.5,  
            row['williams_r'] > -2, 
            row['adx'] < 25,  
            row['close'] < row['psar'],  
            (row['close'] < row['senkou_span_a'] and row['close'] < row['senkou_span_b'] and
             row['tenkan_sen'] < row['kijun_sen'] and
             row['chikou_span'] < row['close'] and  
             row['senkou_span_a'] < row['senkou_span_b']),  
            row['volume_profile'] < row['volume_profile_shifted'] * 0.65  
        ]
        return sum(signals) >= 6

    def long(self, price):
        if self.balance > 0:
            self.long_order = True
            self.short_order = False
            amount = self.balance
            btc_bought = math.floor((amount / (price*(1 + self.fee))) * 1000) / 1000  

            self.balance -= btc_bought * price * (1 + self.fee)
            
            self.btc_balance += btc_bought
            self.total_money_spent = btc_bought * price * (1 + self.fee)

            print(f"Longed at {price}, balance: {self.balance}, BTC: {self.btc_balance}")
            self.long_trades += 1

    def short(self, price):
        if self.balance > 0:
            self.long_order = False
            self.short_order = True
            amount = self.balance
            btc_sold = math.floor((amount / (price*(1 + self.fee))) * 1000) / 1000  # Deduct the fee from the sold amount

            self.balance -= btc_sold * price * (1 + self.fee)  # Add the fee to the sold amount

            self.btc_balance -= btc_sold
            self.total_money_spent = btc_sold * price * (1 + self.fee)

            print(f"Shorted at {price}, balance: {self.balance}, BTC: {self.btc_balance}")
            self.short_trades += 1

    def close_position(self, price):
        if self.btc_balance > 0:
            # Close long positions
            total_sell = self.btc_balance * price * (1 - self.fee)  # Deduct the fee from the sold amount
            self.balance += total_sell
            self.btc_balance = 0
            self.highest_balance = 0
            self.long_order = False
            print(f"Closed long position at {price}, balance: {self.balance}, BTC: {self.btc_balance}")

            pnl = (self.balance - self.total_money_spent) / self.total_money_spent
            self.sum_pnl += pnl
            if pnl > 0:
                self.successful_long_trades += 1
            self.max_realized_loss = min(self.max_realized_loss, pnl)

            self.total_money_spent = 0
        elif self.btc_balance < 0:
            # Close short positions
            total_buy = -self.btc_balance * price  * (1 + self.fee)  # Deduct the fee from the sold amount
            percentage_change = (self.total_money_spent - total_buy) / self.total_money_spent
            self.balance += self.total_money_spent * (1 + percentage_change) 
            self.btc_balance = 0
            self.highest_balance = 0
            self.short_order = False
            print(f"Closed short position at {price}, balance: {self.balance}, BTC: {self.btc_balance}")

            pnl = (self.balance - self.total_money_spent) / self.total_money_spent
            self.sum_pnl_short += pnl
            if pnl > 0:
                self.successful_short_trades += 1
            self.max_realized_loss = min(self.max_realized_loss, pnl)
        
            self.total_money_spent = 0
    
    def backtest(self, df):
            df = self.calculate_indicators(df)
            for _, row in df.iterrows():
                if self.long_signal(row):
                    if self.short_order:
                        self.close_position(row['close'])
                    if not self.long_order:
                        self.long(row['close'])
                elif self.short_signal(row):
                    if self.long_order:
                        self.close_position(row['close'])
                    if not self.short_order:
                        self.short(row['close'])
                
            self.close_position(row['close'])
            return self.balance

    
# Create a temporary client to get server time
temp_client = Client()
server_time = temp_client.get_server_time()
offset = server_time['serverTime'] - int(time.time() * 1000)

# Create a client with the correct offset
client = Client('pBXctBYN1vkZBUIOkhBhob5tfK0md1oC3KAo10rJBKMlJgZMwMaQJMaNWLQRsVox', '0kCWDrAB10jKjTPKSWuUaJDmCD23mQApy43cZS8jIHCgNajGpI0k8y43ZYR7p43p')


# Get the latest price data
klines = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_15MINUTE, "4000 days ago UTC")
df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
df['close'] = pd.to_numeric(df['close'])
df['open'] = pd.to_numeric(df['open']) 
df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
df['high'] = pd.to_numeric(df['high'], errors='coerce')
df['low'] = pd.to_numeric(df['low'], errors='coerce')

bot = TradingBot()

# Run the trading bot
balance = bot.backtest(df)
print("----------------------------------------------------")
print(f"Final balance: {balance}")
print()
print(f"Successful long trades: {bot.successful_long_trades}/ {bot.long_trades}")
print(f"Average pnl per long trade: {bot.sum_pnl * 100 / bot.long_trades}"+"%")
print()
print(f"Successful short trades: {bot.successful_short_trades}/ {bot.short_trades}")
print(f"Average pnl per short trade: {bot.sum_pnl_short * 100 / bot.short_trades}"+"%")
print()
print(f"Max realized loss: {bot.max_realized_loss * 100}%")
client.close_connection()
