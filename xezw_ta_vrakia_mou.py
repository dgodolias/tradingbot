import time
import talib
from binance.client import Client
import pandas as pd

class TradingBot:
    def __init__(self):
        self.balance = 1000
        self.btc_balance = 0
        self.short_balance = 0
        self.total_money_spent = 0
        self.total_money_earned = 0
        self.price_last_order = 0
        self.fee = 0.00075  # Trading fee of 0.075%
        self.long_order_ongoing = False
        self.short_order_ongoing = False
        self.long_trades = 0
        self.short_trades = 0
        self.successful_long_trades = 0
        self.successful_short_trades = 0
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
        macd_condition = row['macd'] > row['macdsignal'] + 0.13  # Increased by 50%
        stochrsi_condition = row['stochrsi'] < 3.25  # Decreased by 50%
        macdhist_condition = row['macdhist'] > 0.026  # Increased by 50%
        cci_condition = row['cci'] < -520  # Decreased by 50%
        vwap_condition = row['close'] < row['vwap'] - 0.026  # Increased by 50%
        mfi_condition = row['mfi'] < 3.5  # Decreased by 50%
        williams_r_condition = row['williams_r'] < -96.5  # Decreased by 50%
        adx_condition = row['adx'] > 32.5  # Unchanged as it's a comparison
        psar_condition = row['close'] > row['psar']  # Unchanged as it's a comparison
        ichimoku_condition = (row['close'] > row['senkou_span_a'] and row['close'] > row['senkou_span_b'] and  # Price is above the cloud
                              row['tenkan_sen'] > row['kijun_sen'] and  # Conversion Line is above Base Line
                              row['chikou_span'] > row['close'] and  # Lagging Span is above the price
                              row['senkou_span_a'] > row['senkou_span_b'])  # Senkou Span A is above Senkou Span B
        volume_profile_condition = row['volume_profile'] > row['volume_profile_shifted'] * 1.5  # Volume profile increased by 50%

        indicator_sum = sum([macd_condition, stochrsi_condition, macdhist_condition, cci_condition, vwap_condition, mfi_condition, williams_r_condition, adx_condition, psar_condition, ichimoku_condition, volume_profile_condition]) 

        return indicator_sum >= 6

    def short_signal(self, row):
        macd_condition = row['macd'] < row['macdsignal'] - 0.13  # Increased by 50%     
        stochrsi_condition = row['stochrsi'] > 100 - 3.25  # Decreased by 50%   
        macdhist_condition = row['macdhist'] < -0.026  # Decreased by 50%
        cci_condition = row['cci'] > 520  # Increased by 50%
        vwap_condition = row['close'] > row['vwap'] + 0.026  # Increased by 50%
        mfi_condition = row['mfi'] > 96.5  # Increased by 50%
        williams_r_condition = row['williams_r'] > -3.5  # Increased by 50%
        adx_condition = row['adx'] < 27.5  # Unchanged as it's a comparison
        psar_condition = row['close'] < row['psar']  # Unchanged as it's a comparison
        ichimoku_condition = (row['close'] < row['senkou_span_a'] and row['close'] < row['senkou_span_b'] and  # Price is below the cloud
                              row['tenkan_sen'] < row['kijun_sen'] and  # Conversion Line is below Base Line
                              row['chikou_span'] < row['close'] and  # Lagging Span is below the price
                              row['senkou_span_a'] < row['senkou_span_b'])  # Senkou Span A is below Senkou Span B
        volume_profile_condition =  row['volume_profile'] < row['volume_profile_shifted'] * 0.5  # Volume profile decreased by 50%

        indicator_sum = sum([macd_condition, stochrsi_condition, macdhist_condition, cci_condition, vwap_condition, mfi_condition, williams_r_condition, adx_condition, psar_condition, ichimoku_condition, volume_profile_condition]) 

        return indicator_sum >= 7
    

    def short(self, price):
        self.short_trades += 1
        self.short_order_ongoing = True
        self.price_last_order = price
        amount = self.balance 
        self.balance -= amount
        btc_sold = (amount / price) * (1 - self.fee)  # Deduct the fee from the sold amount
        self.short_balance += btc_sold
        self.total_money_spent += amount
        print(f"Shorted at {price}, balance: {self.balance}, BTC: {self.short_balance}")

    def cover(self, price):
        self.short_order_ongoing = False
        percentage_change = (price - self.price_last_order) / self.price_last_order

        if percentage_change > 0:
            self.successful_short_trades += 1
        else:
            self.max_realized_loss = max(self.max_realized_loss, abs(percentage_change))

        total_cover = self.short_balance * self.price_last_order * ( 1 - percentage_change) * (1 - self.fee)  # Deduct the fee from the covered amount

        self.balance += total_cover
        self.short_balance = 0
        self.total_money_spent = 0
        self.price_last_order = 0
        print(f"Covered at {price}, balance: {self.balance}, BTC: {self.short_balance}")

    def long(self, price):
        self.long_trades += 1
        self.long_order_ongoing = True
        self.price_last_order = price
        amount = self.balance 
        self.balance -= amount
        btc_bought = (amount / price) * (1 - self.fee)  # Deduct the fee from the bought amount
        self.btc_balance += btc_bought
        self.total_money_spent += amount
        print(f"Bought at {price}, balance: {self.balance}, BTC: {self.btc_balance}")

    def sell(self, price):
        self.long_order_ongoing = False
        percentage_change = (price - self.price_last_order) / self.price_last_order

        if percentage_change > 0:
            self.successful_long_trades += 1
        else:
            self.max_realized_loss = max(self.max_realized_loss, abs(percentage_change))

        total_sell = self.btc_balance * price * (1 - self.fee)  # Deduct the fee from the sold amount
        self.balance += total_sell
        self.btc_balance = 0
        self.total_money_spent = 0
        self.price_last_order = 0
        print(f"Sold at {price}, balance: {self.balance}, BTC: {self.btc_balance}")

    def backtest(self, df):
        df = self.calculate_indicators(df)
        for _, row in df.iterrows():
            if self.long_order_ongoing:
                if self.short_signal(row):
                    self.sell(row['close'])
                    self.short(row['close'])
                    self.long_order_ongoing = False
                    self.short_order_ongoing = True
            elif self.short_order_ongoing:
                if self.long_signal(row):
                    self.cover(row['close'])
                    self.long(row['close'])
                    self.short_order_ongoing = False
                    self.long_order_ongoing = True
            else:
                if self.long_signal(row):
                    self.long(row['close'])
                    self.long_order_ongoing = True
                elif self.short_signal(row):
                    self.short(row['close'])
                    self.short_order_ongoing = True

        # Sell remaining BTC at the last close price
        if self.btc_balance > 0:
            self.sell(df.iloc[-1]['close'])

        # Cover remaining short position at the last close price
        if self.short_balance > 0:
            self.cover(df.iloc[-1]['close'])

        return self.balance

# Create a temporary client to get server time
temp_client = Client()
server_time = temp_client.get_server_time()
offset = server_time['serverTime'] - int(time.time() * 1000)

# Create a client with the correct offset
client = Client('pBXctBYN1vkZBUIOkhBhob5tfK0md1oC3KAo10rJBKMlJgZMwMaQJMaNWLQRsVox', '0kCWDrAB10jKjTPKSWuUaJDmCD23mQApy43cZS8jIHCgNajGpI0k8y43ZYR7p43p')
client.response_timeout = 20

# Get the historical hourly data
klines = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_15MINUTE, "3600 days ago UTC")
df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
df['close'] = pd.to_numeric(df['close'])
df['open'] = pd.to_numeric(df['open'])  # Convert 'open' column to numeric
df['volume'] = df['volume'].astype(float)
df['high'] = df['high'].astype(float)
df['low'] = df['low'].astype(float)
df['close'] = df['close'].astype(float)

# Create and run the bot
bot = TradingBot()
final_balance = bot.backtest(df)
print("--------------------")
print(f"Final balance: {final_balance}")
print(f"Successful long trades: {bot.successful_long_trades}/ {bot.long_trades}")
print(f"Successful short trades: {bot.successful_short_trades}/ {bot.short_trades}")
print(f"Max realized loss: -{bot.max_realized_loss * 100}%")