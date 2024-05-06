import time
from binance.client import Client
import pandas as pd
import talib

class TradingBot:
    def __init__(self):
        self.balance = 1000
        self.client = client
        self.btc_balance = 0
        self.total_money_spent = 0
        self.highest_balance = 0
        self.fee = 0.00075  # Trading fee of 0.075%
        self.long_order = False
        self.short_order = False

    def calculate_indicators(self, df):
        df['mom'] = talib.MOM(df['close'], timeperiod=10)
        df['roc'] = talib.ROC(df['close'], timeperiod=10)
        df['willr'] = talib.WILLR(df['high'], df['low'], df['close'], timeperiod=14)
        df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
        df['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)
        df['ppo'] = talib.PPO(df['close'], fastperiod=12, slowperiod=26)  # Percentage Price Oscillator
        df['macd'], df['macdsignal'], df['macdhist'] = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)  # Moving Average Convergence Divergence
        df['upperband'], df['middleband'], df['lowerband'] = talib.BBANDS(df['close'], timeperiod=20)
        df['ht_trendline'] = talib.HT_TRENDLINE(df['close'])  # Hilbert Transform - Instantaneous Trendline
        df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=14)  # Commodity Channel Index
        return df

    def long_signal(self, row):
        signals = [
            row['mom'] > 0.001,
            row['roc'] > 1.7,
            row['willr'] < -90,
            row['adx'] < 17.5,
            row['mfi'] < 10,
            row['ppo'] > 0.92,  # PPO is positive
            row['macd'] > 0.00025,  # MACD is positive
            row['close'] < row['lowerband'],  # Close price is below the lower Bollinger Band
            row['ht_trendline'] > row['close'],  # HT_TRENDLINE is above the close price
            row['cci'] > 170,  # CCI is above 100
        ]
        return sum(signals) >= 4

    def short_signal(self, row):
        signals = [
            row['mom'] < -0.001,  # mirrored from long signal
            row['roc'] < -1.7,  # mirrored from long signal
            row['willr'] > -10,  # mirrored from long signal
            row['adx'] > 42.5,  # mirrored from long signal
            row['mfi'] > 90,  # mirrored from long signal
            row['ppo'] < -0.92,  # PPO is negative, mirrored from long signal
            row['macd'] < -0.00025,  # MACD is negative
            row['close'] > row['upperband'],  # Close price is above the upper Bollinger Band
            row['ht_trendline'] < row['close'],  # HT_TRENDLINE is below the close price
            row['cci'] < -170,  # CCI is below -100
        ]
        return sum(signals) >= 4

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
            self.total_money_spent += amount
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
            total_buy = -self.btc_balance * price * (1 + self.fee)  # Add the fee to the bought amount
            percentage_change = (total_buy - self.total_money_spent) / self.total_money_spent
            self.balance += self.total_money_spent * (1 - percentage_change)
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
klines = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_1MINUTE, "1 days ago UTC")
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
