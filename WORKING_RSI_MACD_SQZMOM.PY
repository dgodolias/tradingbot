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
        self.fee = 0.00075  # Trading fee of 0.075%
        self.stop_loss_ratio = 0.97  # Stop loss
        self.take_profit_ratio = 1.08  #Take profit

    def calculate_indicators(self, df):
        df['macd'], df['macdsignal'], df['macdhist'] = talib.MACD(df['close'])
        df['stochrsi'], df['stochrsi_signal'] = talib.STOCHRSI(df['close'])
        df['upper_band'], df['middle_band'], df['lower_band'] = talib.BBANDS(df['close'])
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'])
        df['ema'] = talib.EMA(df['close'])
        df['cci'] = talib.CCI(df['high'], df['low'], df['close'])
        multiplier = 2  # adjust this value according to your strategy
        df['keltner_upper'] = df['ema'] + df['atr'] * multiplier
        df['keltner_lower'] = df['ema'] - df['atr'] * multiplier
        df['squeeze_on'] = (df['lower_band'] > df['keltner_lower']) & (df['upper_band'] < df['keltner_upper'])
        df['squeeze_off'] = (df['lower_band'] < df['keltner_lower']) & (df['upper_band'] > df['keltner_upper'])
        df['vwap'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
        df['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'])
        df['williams_r'] = talib.WILLR(df['high'], df['low'], df['close'])

        return df
    
    def long_signal(self, row):
        macd_condition = row['macd'] > row['macdsignal']
        stochrsi_condition = row['stochrsi'] < 10  # More oversold
        squeeze_condition = row['squeeze_off']
        macdhist_condition = row['macdhist'] > 0
        cci_condition = row['cci'] < -150  # More oversold
        vwap_condition = row['close'] < row['vwap']
        mfi_condition = row['mfi'] < 20  # More oversold
        williams_r_condition = row['williams_r'] < -80  # More oversold
    
        indicator_sum = sum([macd_condition, stochrsi_condition, squeeze_condition, macdhist_condition, cci_condition, vwap_condition, mfi_condition, williams_r_condition]) 
    
        return indicator_sum >= 4
     
    def close_long_signal(self, row):
        stop_loss_condition = row['close'] * self.btc_balance <= self.total_money_spent * self.stop_loss_ratio
        take_profit_condition = row['close'] * self.btc_balance >= self.total_money_spent * self.take_profit_ratio
    
        return stop_loss_condition or take_profit_condition


    def long(self, price):
        amount = self.balance 
        self.balance -= amount
        btc_bought = (amount / price) * (1 - self.fee)  # Deduct the fee from the bought amount
        self.btc_balance += btc_bought
        self.total_money_spent += amount
        print(f"Bought at {price}, balance: {self.balance}, BTC: {self.btc_balance}")

    def sell(self, price):
        total_sell = self.btc_balance * price * (1 - self.fee)  # Deduct the fee from the sold amount
        self.balance += total_sell
        self.btc_balance = 0
        self.total_money_spent = 0
        print(f"Sold at {price}, balance: {self.balance}, BTC: {self.btc_balance}")

    def backtest(self, df):
        df = self.calculate_indicators(df)
        for _, row in df.iterrows():
            if self.balance>0:
                if self.long_signal(row):
                    self.long(row['close'])
            elif self.btc_balance>0:
                if self.close_long_signal(row):
                    self.sell(row['close'])
        
        # Sell remaining BTC at the last close price
        if self.btc_balance > 0:
            self.sell(df.iloc[-1]['close'])
        
        return self.balance

# Create a temporary client to get server time
temp_client = Client()
server_time = temp_client.get_server_time()
offset = server_time['serverTime'] - int(time.time() * 1000)

# Create a client with the correct offset
client = Client('pBXctBYN1vkZBUIOkhBhob5tfK0md1oC3KAo10rJBKMlJgZMwMaQJMaNWLQRsVox', '0kCWDrAB10jKjTPKSWuUaJDmCD23mQApy43cZS8jIHCgNajGpI0k8y43ZYR7p43p')

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
print(f"Final balance: {final_balance}")