class TradingBot:
    def __init__(self):
        self.balance = 1000
        self.btc_balance = 0
        self.buys = []

    def buy(self, price):
        amount = self.balance * 0.1
        self.balance -= amount
        btc_bought = amount / price
        self.buys.append(btc_bought)
        self.btc_balance += btc_bought
        print(f"Bought at {price}, balance: {self.balance}, BTC: {self.btc_balance}")

    def sell(self, price):
        if self.btc_balance > 0:
            total_sell = sum(self.buys) * price
            if total_sell >= sum(self.buys) * 1.06 or price <= sum(self.buys) / len(self.buys) * 0.985:
                self.balance += total_sell
                self.btc_balance = 0
                self.buys = []
                print(f"Sold at {price}, balance: {self.balance}, BTC: {self.btc_balance}")

    def backtest(self, df):
        trade_count = 0
        for _, row in df.iterrows():
            if row['close'] > row['open'] * 1.03:
                self.buy(row['close'])
                trade_count += 1
            if trade_count >= 5 and len(self.buys) > 0:
                self.sell(row['close'])
                trade_count = 0

        return self.balance
# Existing code
import time
from binance.client import Client
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Create a temporary client to get server time
temp_client = Client()
server_time = temp_client.get_server_time()
offset = server_time['serverTime'] - int(time.time() * 1000)

# Create a client with the correct offset
client = Client('pBXctBYN1vkZBUIOkhBhob5tfK0md1oC3KAo10rJBKMlJgZMwMaQJMaNWLQRsVox', '0kCWDrAB10jKjTPKSWuUaJDmCD23mQApy43cZS8jIHCgNajGpI0k8y43ZYR7p43p')

# Get the historical hourly data
klines = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_1HOUR, "1000 days ago UTC")
df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
df['close'] = pd.to_numeric(df['close'])
df['open'] = pd.to_numeric(df['open'])  # Convert 'open' column to numeric

# Create and run the bot
bot = TradingBot()
final_balance = bot.backtest(df)
print(f"Final balance: {final_balance}")