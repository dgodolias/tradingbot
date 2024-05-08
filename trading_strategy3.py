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
        self.highest_balance = 0
        self.fee = 0.00017  # Trading fee
        self.long_order = False
        self.short_order = False

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
        row['macd'] > row['macdsignal'] + 0.16,  # Increased by 50%
        row['stochrsi'] < 3.25,  # Decreased by 50%
        row['macdhist'] > 0.027,  # Increased by 50%
        row['cci'] < -520,  # Decreased by 50%
        row['close'] < row['vwap'] - 0.026,  # Increased by 50%
        row['mfi'] < 3.5 , # Decreased by 50%
        row['williams_r'] < -97 , # Decreased by 50%
        row['adx'] > 33.5,  # Unchanged as it's a comparison
        row['close'] > row['psar'] , # Unchanged as it's a comparison
        (row['close'] > row['senkou_span_a'] and row['close'] > row['senkou_span_b'] and  # Price is above the cloud
                              row['tenkan_sen'] > row['kijun_sen'] and  # Conversion Line is above Base Line
                              row['chikou_span'] > row['close'] and  # Lagging Span is above the price
                              row['senkou_span_a'] > row['senkou_span_b']) , # Senkou Span A is above Senkou Span B
        row['volume_profile'] > row['volume_profile_shifted'] * 1.5  # Volume profile increased by 50%
        ]
        return sum(signals) >= 6

    def short_signal(self, row):
        signals = [
            row['macd'] < row['macdsignal'] - 0.16,  # Increased by 50%
            row['stochrsi'] > 100 - 3.25,  # Decreased by 50%
            row['macdhist'] < -0.027,  # Decreased by 50%
            row['cci'] > 520,  # Increased by 50%
            row['close'] > row['vwap'] + 0.026,  # Increased by 50%
            row['mfi'] > 96.5,  # Increased by 50%
            row['williams_r'] > -3,  # Increased by 50%
            row['adx'] < 26.5,  # Unchanged as it's a comparison
            row['close'] < row['psar'],  # Unchanged as it's a comparison
            (row['close'] < row['senkou_span_a'] and row['close'] < row['senkou_span_b'] and  # Price is below the cloud
             row['tenkan_sen'] < row['kijun_sen'] and  # Conversion Line is below Base Line
             row['chikou_span'] < row['close'] and  # Lagging Span is below the price
             row['senkou_span_a'] < row['senkou_span_b']),  # Senkou Span A is below Senkou Span B
            row['volume_profile'] < row['volume_profile_shifted'] * 0.5  # Volume profile decreased by 50%
        ]
        return sum(signals) >= 6

    def long(self, price):
        if self.balance > 0:
            self.long_order = True
            self.short_order = False
            amount = self.balance
            self.balance -= amount
            btc_bought = (amount / price) * (1 - self.fee)  # Deduct the fee from the bought amount

            self.btc_balance += btc_bought
            self.total_money_spent += amount
            self.highest_balance = max(self.highest_balance, self.btc_balance * price)
            print(f"Longed at {price}, balance: {self.balance}, BTC: {self.btc_balance}")

    def short(self, price):
        if self.balance > 0:
            self.long_order = False
            self.short_order = True
            amount = self.balance
            self.balance -= amount
            btc_sold = (amount / price) * (1 - self.fee)  # Deduct the fee from the sold amount

            self.btc_balance -= btc_sold
            self.total_money_spent += amount * (1 - self.fee)  # Add the fee to the bought amount
            self.highest_balance = max(self.highest_balance, self.btc_balance * price)
            print(f"Shorted at {price}, balance: {self.balance}, BTC: {self.btc_balance}")

    def close_position(self, price):
        if self.btc_balance > 0:
            # Close long positions
            total_sell = self.btc_balance * price * (1 - self.fee)  # Deduct the fee from the sold amount
            self.balance += total_sell
            self.btc_balance = 0
            self.total_money_spent = 0
            self.highest_balance = 0
            self.long_order = False
            print(f"Closed long position at {price}, balance: {self.balance}, BTC: {self.btc_balance}")
        elif self.btc_balance < 0:
            # Close short positions
            total_buy = -self.btc_balance * price  # Add the fee to the bought amount
            percentage_change = (self.total_money_spent - total_buy) / self.total_money_spent
            self.balance += self.total_money_spent * (1 + percentage_change) * (1 - self.fee)  # Deduct the fee from the sold amount
            self.btc_balance = 0
            self.total_money_spent = 0
            self.highest_balance = 0
            self.short_order = False
            print(f"Closed short position at {price}, balance: {self.balance}, BTC: {self.btc_balance}")
    
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
print(f"Final balance: {balance}")
client.close_connection()
