import time
from binance.client import Client
import pandas as pd
import talib

class TradingBot:
    def __init__(self):
        self.balance = 1000
        self.btc_balance = 0
        self.total_money_spent = 0
        self.highest_balance = 0
        self.fee = 0.00075  # Trading fee of 0.075%
        self.long_order = False
        self.short_order = False

    def long_signal(self, row):
        return row['high']>row['close']*1.0002

    def short_signal(self, row):
        return row['low']<row['close']*0.9998

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

# Get the historical hourly data
klines = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_1MINUTE, "30 days ago UTC")
df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
df['close'] = pd.to_numeric(df['close'])
df['open'] = pd.to_numeric(df['open']) 
df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
df['high'] = pd.to_numeric(df['high'], errors='coerce')
df['low'] = pd.to_numeric(df['low'], errors='coerce')

# Create and run the bot
bot = TradingBot()
final_balance = bot.backtest(df)
print(f"Final balance: {final_balance}")