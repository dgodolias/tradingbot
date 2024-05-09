import datetime
import math
import os
from binance.um_futures import UMFutures
from dotenv import load_dotenv
import talib
import pandas as pd
from time import sleep
from binance.error import ClientError
from binance.enums import *
import pause
import sys
from colorama import Fore, Style


def get_fee_rate():
    return 0.00017
# getting your futures balance in USDT
def get_balance_usdt():
    try:
        account_info = client.account()
        return float(account_info['availableBalance'])

    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )


def klines(symbol,timeframe):
    try:
        resp = pd.DataFrame(client.klines(symbol, str(timeframe)+'m', limit=100))
        resp = resp.iloc[:,:6]
        resp.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
        resp = resp.set_index('time')
        resp.index = pd.to_datetime(resp.index, unit = 'ms')
        resp.index = resp.index.tz_localize('UTC').tz_convert('EET')  # Convert to Athens time
        resp = resp.astype(float)
        return resp
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )


# Set leverage for the needed symbol. You need this bcz different symbols can have different leverage
def set_leverage(symbol, level):
    try:
        response = client.change_leverage(
            symbol=symbol, leverage=level, recvWindow=6000
        )
        print(response)
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )


# The same for the margin type
def set_mode(symbol, type):
    try:
        print("Setting margin type to", type)
        response = client.change_margin_type(
            symbol=symbol, marginType=type, recvWindow=6000
        )
        print(response)
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )


# Price precision. BTC has 1, XRP has 4
def get_price_precision():
    return price_precision


# Amount precision. BTC has 3, XRP has 1
def get_qty_precision():
    return qty_precision

# Get the previous quantity to avoid errors with the precision
def previous_qty(symbol, qty):
    precision = get_qty_precision()
    step = 10 ** -precision
    previous_qty = ((qty // step) * step) - step
    return previous_qty

def position_opened(symbol):
    try:
        position_info = client.get_position_risk(symbol=symbol)
        if position_info:
            position_info = position_info[0]
            return float(position_info['positionAmt']) != 0
        else:
            return False
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

def open_order(symbol, side):
    fee_rate = get_fee_rate()
    volume = get_balance_usdt()
    price = float(client.ticker_price(symbol)['price'])
    qty_precision = get_qty_precision()
    price_precision = get_price_precision()

    direction = 'up' if side == 'buy' else 'down'
    fee_multiplier = 1 + fee_rate if side == 'buy' else 1 - fee_rate
    price *= fee_multiplier
    qty = math.floor((volume / price * 10**qty_precision)) / 10**qty_precision
    sl_multiplier = 1 - sl if side == 'buy' else 1 + sl
    sl_price = round(price * sl_multiplier, price_precision)

    print('Price:', price)
    print('Volume:', volume)
    print("Normal quantity:", volume / price)
    print("Rounded down quantity:", qty)

    max_retries = 5
    retry_delay = 2
    retry = 0
    while True:
        try:
            print("Required margin for the trade: ", price * qty)
            order = client.new_order(symbol=symbol, side=SIDE_BUY if side == 'buy' else SIDE_SELL, type=FUTURE_ORDER_TYPE_MARKET, quantity=qty)
            print("*********************************************************************")
            print(order)
            print("*********************************************************************")
            if side == 'buy':
                print(Fore.GREEN + ">>>", symbol, side, "PLACED ORDER <<<" + Style.RESET_ALL)
            else:
                print(Fore.RED + ">>>", symbol, side, "PLACED ORDER <<<" + Style.RESET_ALL)            
                client.new_order(symbol=symbol, side=SIDE_SELL if side == 'buy' else SIDE_BUY, type=FUTURE_ORDER_TYPE_STOP_MARKET, quantity=qty, timeInForce='GTC', stopPrice=sl_price)
            break
        except ClientError as error:
            print("Found error. status: {}, error code: {}, error message: {}".format(error.status_code, error.error_code, error.error_message))
            retry += 1
            sleep(retry_delay)
            if retry >= max_retries:
                print("Max retries reached, exiting")
                sys.exit(1)
            if position_opened(symbol):
                break
            qty = previous_qty(symbol, qty)
            sleep(2)
            if qty <= 0:
                close_open_orders(symbol)
                close_position(symbol)
                break

    print("Available margin: ", client.account()['availableBalance'])
    print('---------------------------------')
    return direction

def close_position(symbol):
    try:
        # Get the position details
        position_info = client.get_position_risk(symbol=symbol)

        if position_info:
            position_info = position_info[0]  # Access the first item in the list

            # Determine the order side based on the position amount
            order_side = SIDE_SELL if float(position_info['positionAmt']) > 0 else SIDE_BUY

            # Place an order to close the position
            client.new_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=abs(float(position_info['positionAmt'])),
            )

            print(f"Closed position for {symbol}")
            print('---------------------------------')

    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
# Close open orders for the needed symbol. If one stop order is executed and another one is still there
def close_open_orders(symbol):
    try:
        response = client.cancel_open_orders(symbol=symbol, recvWindow=6000)
        print(response)
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

def calculate_indicators(df):
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

def str_signal(row):

    # Define conditions for 'up' and 'down'
    conditions_up = [
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
    conditions_down = [
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

    # Check for 'up' and 'down' conditions
    if sum(conditions_up) >= 5:
        return 'up'
    elif sum(conditions_down) >= 5:
        return 'down'
    else:
        return 'none'

def handle_signal(symbol, signal, leverage):
    print(f'Found {signal.upper()} signal for {symbol}')
    close_open_orders(symbol)
    close_position(symbol)

    set_leverage(symbol, leverage)
    print(f'Placing order for {symbol}')

    print('---------------------------------')
    direction = open_order(symbol, signal)

    return direction

def klines_delay():
    # Get the current second
    current_second = datetime.datetime.now().second
    # If we're in the [1, 10] range, sleep until the 10th second
    if 1 <= current_second <= 15:
        sleep_time = 15 - current_second
        sleep(sleep_time)

def pause_(previous_unix, step):

    print('Waiting for the next candle')
    pause.until(previous_unix + step)
    sleep(2)
    print('Next candle is here!')

def trade(leverage, type, symbol, direction,timeframe):

    close_open_orders(symbol)
    close_position(symbol)
    set_mode(symbol, type)

    pause_(klines(symbol,timeframe).index[-1].timestamp(),timeframe* 60)

    while True:
        if not position_opened(symbol): direction = ''
        # we need to get balance to check if the connection is good, or you have all the needed permissions
        balance = get_balance_usdt()
        if balance == None:
            print('Cant connect to API. Check IP, restrictions or wait some time')
            print('---------------------------------')
        if balance != None:
            print("My balance is: ", balance, " USDT")
            print('---------------------------------')

            klines_delay()
            klines_ = klines(symbol,timeframe)
            df = calculate_indicators(klines_)
            row = df.iloc[-1]
            signal = str_signal(row)         

            if signal == 'up' and (direction == 'down' or direction == ''):
                direction = handle_signal(symbol, 'buy',  leverage)
                pause_(klines_.index[-1].timestamp(), timeframe * 60)
            elif signal == 'down' and (direction == 'up' or direction == ''):
                direction = handle_signal(symbol, 'sell', leverage)
                pause_(klines_.index[-1].timestamp(),timeframe * 60)
            else:
                print('No signal found')
                pause_(klines_.index[-1].timestamp(),timeframe * 60)

# Get the API key and secret from the environment
try:
    key = os.getenv('API_KEY')
    secret = os.getenv('API_SECRET')
    base_url = os.getenv('API_BASE_URL')

    if not key or not secret or not base_url:
        raise ValueError("Missing environment variable")

except ValueError:
    load_dotenv('keys.env')
    key = os.getenv('API_KEY')
    secret = os.getenv('API_SECRET')
    base_url = os.getenv('API_BASE_URL')

client = UMFutures(key=key, secret=secret)
client.base_url = base_url

# 0.012 means +1.2%, 0.009 is -0.9%

sl = 0.30
orders = 0
leverage = 1
type = 'CROSSED'  # type is 'ISOLATED' or 'CROSS'
symbol = 'BTCUSDT'
price_precision = 1
qty_precision = 3
direction = ''
timeframe = 15 #in minutes
print('Starting the bot')
print('---------------------------------')
trade(leverage, type, symbol, direction, timeframe)



