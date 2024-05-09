import datetime
import math
import time
import winsound
from binance.client import Client
import pandas as pd
import talib

class TradingBot:
    def __init__(self):
        self.precision = 2
        self.balance = 1000
        self.client = client
        self.eth_balance = 0
        self.total_money_spent = 0
        self.fee = 0.00017  # Trading fee
        self.long_order = False
        self.short_order = False
        self.long_trades = 0
        self.successful_long_trades = 0
        self.sum_pnl_long = 0
        self.short_trades = 0
        self.successful_short_trades = 0
        self.sum_pnl_short = 0
        self.max_realized_loss = 0
        self.top_losses = []
        self.unrealized_losses = []

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
        row['macd'] > row['macdsignal'] + 0.16,  #CHECKED
        row['stochrsi'] < 3,  # CHECKED
        row['macdhist'] > 0.024,  # CHECKED
        row['cci'] < -228,  # CHECKED
        row['close'] < row['vwap'] - 0.026,  
        row['mfi'] < 3.5 , # CHECKED
        row['williams_r'] < -98 , # CHECKED
        row['adx'] > 35,  # CHECKED
        row['close'] > row['psar'] , 
        (row['close'] > row['senkou_span_a'] and row['close'] > row['senkou_span_b'] and 
                              row['tenkan_sen'] > row['kijun_sen'] and  
                              row['chikou_span'] > row['close'] and  
                              row['senkou_span_a'] > row['senkou_span_b']) , # CHECKED
        row['volume_profile'] > row['volume_profile_shifted'] * 1.35  # CHECKED
        ]
        return sum(signals) >= 5

    def short_signal(self, row):
        signals = [
            row['macd'] < row['macdsignal'] - 0.16,  
            row['stochrsi'] > 97,  
            row['macdhist'] < -0.024,  
            row['cci'] >  228, 
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
        print(sum(signals))
        return sum(signals) >= 5

    def long(self, price):
        if self.balance > 0:
            self.long_order = True
            self.short_order = False
            amount = self.balance
            eth_bought = math.floor((amount / (price*(1 + self.fee))) * (10**self.precision)) / (10**self.precision)  

            self.balance -= eth_bought * price * (1 + self.fee)
            
            self.eth_balance += eth_bought
            self.total_money_spent = eth_bought * price * (1 + self.fee)

            print(f"Longed at {price}, balance: {self.balance}, ETH: {self.eth_balance}")
            self.long_trades += 1

    def short(self, price):
        if self.balance > 0:
            self.long_order = False
            self.short_order = True
            amount = self.balance
            eth_sold = math.floor((amount / (price*(1 + self.fee))) * (10**self.precision)) / (10**self.precision)  # Deduct the fee from the sold amount

            self.balance -= eth_sold * price * (1 + self.fee)  # Add the fee to the sold amount

            self.eth_balance -= eth_sold
            self.total_money_spent = eth_sold * price * (1 + self.fee)

            print(f"Shorted at {price}, balance: {self.balance}, ETH: {self.eth_balance}")
            self.short_trades += 1

    def close_position(self, price):
        if self.eth_balance > 0:
            # Close long positions
            total_sell = self.eth_balance * price * (1 - self.fee)  # Deduct the fee from the sold amount
            percentage_change = (total_sell - self.total_money_spent) / self.total_money_spent
            self.balance += total_sell
            self.eth_balance = 0
            self.highest_balance = 0
            self.long_order = False
            print(f"Closed long position at {price}, balance: {self.balance}, ETH: {self.eth_balance}")
            print()

            self.sum_pnl_long += percentage_change
            if percentage_change > 0:
                self.successful_long_trades += 1
            else:
                if len(self.top_losses) < 10:  # If the list has less than 10 items, we simply add the new loss
                    self.top_losses.append(percentage_change)
                else:  # If the list already has 10 items
                    min_loss = min(self.top_losses, key=abs)  # We find the smallest loss (in absolute terms)
                    if abs(percentage_change) > abs(min_loss):  # If the new loss is larger
                        self.top_losses.remove(min_loss)  # We remove the smallest loss from the list
                        self.top_losses.append(percentage_change)  # And add the new one

            self.max_realized_loss = min(self.max_realized_loss, percentage_change)

            self.total_money_spent = 0
        elif self.eth_balance < 0:
            # Close short positions
            total_buy = -self.eth_balance * price  * (1 + self.fee)  # Deduct the fee from the sold amount
            percentage_change = (self.total_money_spent - total_buy) / self.total_money_spent
            self.balance += self.total_money_spent * (1 + percentage_change) 
            self.eth_balance = 0
            self.highest_balance = 0
            self.short_order = False
            print(f"Closed short position at {price}, balance: {self.balance}, ETH: {self.eth_balance}")
            print()
            self.sum_pnl_short += percentage_change
            if percentage_change > 0:
                self.successful_short_trades += 1
            else:
                if len(self.top_losses) < 10:  # If the list has less than 10 items, we simply add the new loss
                    self.top_losses.append(percentage_change)
                else:  # If the list already has 10 items
                    min_loss = min(self.top_losses, key=abs)  # We find the smallest loss (in absolute terms)
                    if abs(percentage_change) > abs(min_loss):  # If the new loss is larger
                        self.top_losses.remove(min_loss)  # We remove the smallest loss from the list
                        self.top_losses.append(percentage_change)  # And add the new one

            self.max_realized_loss = min(self.max_realized_loss, percentage_change)
        
            self.total_money_spent = 0
    
    def backtest(self, df):
            df = self.calculate_indicators(df)
            for _, row in df.iterrows():
                #finding the 10 biggest unrealised losses
                if self.long_order:
                    self.unrealized_losses.append(((row['close']  - self.total_money_spent) / self.total_money_spent))
                    if len(self.unrealized_losses) > 10:
                        self.unrealized_losses.remove(min(self.unrealized_losses, key=abs))

                    if row['close'] * self.eth_balance <= self.total_money_spent * 0.70:
                        self.close_position(row['close'])
                elif self.short_order:
                    self.unrealized_losses.append(((self.total_money_spent - row['close']) / self.total_money_spent))
                    if len(self.unrealized_losses) > 10:
                        self.unrealized_losses.remove(min(self.unrealized_losses, key=abs))

                    if row['close'] * (-self.eth_balance) >= self.total_money_spent * 1.30:
                        self.close_position(row['close'])                

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
klines = client.get_historical_klines("ETHUSDC", Client.KLINE_INTERVAL_15MINUTE, "1 days ago UTC")
print(klines)

"""start_date = "18 Aug, 2017"
end_date = "09 May, 2024"

start_date = datetime.datetime.strptime(start_date, "%d %b, %Y")
end_date = datetime.datetime.strptime(end_date, "%d %b, %Y")

klines = client.get_historical_klines("ETHUSDT", Client.KLINE_INTERVAL_15MINUTE, start_date.strftime("%d %b, %Y %H:%M:%S"), end_date.strftime("%d %b, %Y %H:%M:%S"))
"""

df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
df['close'] = pd.to_numeric(df['close'])
df['open'] = pd.to_numeric(df['open']) 
df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
df['high'] = pd.to_numeric(df['high'], errors='coerce')
df['low'] = pd.to_numeric(df['low'], errors='coerce')

bot = TradingBot()

# Run the trading bot
df = df.iloc[::-1]
balance = bot.backtest(df)
print("----------------------------------------------------")
print("First candle date: ", df['timestamp'].iloc[0])
print(f"Final balance: {balance}")
print()
print(f"Successful long trades: {bot.successful_long_trades}/ {bot.long_trades}")
print(f"Average pnl per long trade: {100*(bot.sum_pnl_long/(bot.long_trades))}"+"%")
print()
print(f"Successful short trades: {bot.successful_short_trades}/ {bot.short_trades}")
print(f"Average pnl per short trade: {100 * (bot.sum_pnl_short/(bot.short_trades))}"+"%")
print()
print("Average pnl per trade: ", 100 * ((bot.sum_pnl_long + bot.sum_pnl_short) / (bot.long_trades + bot.short_trades)),"%")

print(f"Top 10 realized losses: {sorted(bot.top_losses)}")

# Play sound
for _ in range(2):
    winsound.Beep(1000, 500)  # Beep at 1000 Hz for 500 ms
client.close_connection()
