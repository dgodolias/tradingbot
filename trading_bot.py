import datetime
import math
import time
from binance.cm_futures import UMFutures
import talib
import pandas as pd
from time import sleep
from binance.error import ClientError
from binance.enums import *
import pause


def get_fee_rate():
    return 0.0007
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
def get_price_precision(symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['pricePrecision']


# Amount precision. BTC has 3, XRP has 1
def get_qty_precision(symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['quantityPrecision']

# Get the previous quantity to avoid errors with the precision
def previous_qty(symbol, qty):
    precision = get_qty_precision(symbol)
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
    qty_precision = get_qty_precision(symbol)
    price_precision = get_price_precision(symbol)
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

    while True:
        try:
            print("Required margin for the trade: ", price * qty)
            client.new_order(symbol=symbol, side=SIDE_BUY if side == 'buy' else SIDE_SELL, type=FUTURE_ORDER_TYPE_MARKET, quantity=qty)
            print(symbol, side, "placing order")
            client.new_order(symbol=symbol, side=SIDE_SELL if side == 'buy' else SIDE_BUY, type=FUTURE_ORDER_TYPE_STOP_MARKET, quantity=qty, timeInForce='GTC', stopPrice=sl_price)
            if not position_opened(symbol):
                raise ClientError(status_code=400, error_code='PositionError', error_message='Position not opened')            
            break
        except ClientError as error:
            print("Found error. status: {}, error code: {}, error message: {}".format(error.status_code, error.error_code, error.error_message))
            qty = previous_qty(symbol, qty)

    print("Available margin: ", client.account()['availableBalance'])
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

def str_signal(row):

    # Define conditions for 'up' and 'down'
    conditions_up = [
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
    conditions_down = [
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

    # Check for 'up' and 'down' conditions
    if sum(conditions_up) >= 1:
        return 'up'
    elif sum(conditions_down) >= 1:
        return 'down'
    else:
        return 'none'

def handle_signal(symbol, signal, leverage):
    print(f'Found {signal.upper()} signal for {symbol}')
    close_open_orders(symbol)
    close_position(symbol)

    set_leverage(symbol, leverage)
    print(f'Placing order for {symbol}')
    direction = open_order(symbol, signal)

    return direction

def klines_delay():
    # Get the current second
    current_second = datetime.datetime.now().second
    print('Current second:', current_second)
    # If we're in the [1, 10] range, sleep until the 10th second
    if 1 <= current_second <= 15:
        sleep_time = 15 - current_second
        sleep(sleep_time)

def pause_(previous_unix, step):

    print('Waiting for the next candle')
    pause.until(previous_unix + step)
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
        if balance != None:
            print("My balance is: ", balance, " USDT")

            klines_delay()
            klines_ = klines(symbol,timeframe)
            df = calculate_indicators(klines_)
            row = df.iloc[-1]
            print(row.name)
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

client = UMFutures(key = 'b1058af01fe2fe687de39cee6c253157a905cfa8d12b257cae5875eb93ffc6a0', secret='2f91937eae08fb22a25d3372e70180690a5c8da185077e66d759b4d440e68d80')
client.base_url = 'https://testnet.binancefuture.com'

# 0.012 means +1.2%, 0.009 is -0.9%

sl = 0.4
orders = 0
leverage = 1
type = 'CROSSED'  # type is 'ISOLATED' or 'CROSS'
symbol = 'BTCUSDT'
direction = ''
timeframe = 1 #in minutes

trade(leverage, type, symbol, direction, timeframe)

