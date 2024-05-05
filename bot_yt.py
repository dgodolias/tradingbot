import math
from binance.um_futures import UMFutures
import talib as ta
import pandas as pd
from time import sleep
import datetime
from binance.error import ClientError
from binance.enums import *

client = UMFutures(key = 'b1058af01fe2fe687de39cee6c253157a905cfa8d12b257cae5875eb93ffc6a0', secret='2f91937eae08fb22a25d3372e70180690a5c8da185077e66d759b4d440e68d80')
client.base_url = 'https://testnet.binancefuture.com'

# 0.012 means +1.2%, 0.009 is -0.9%

sl = 0.4
leverage = 1
type = 'CROSSED'  # type is 'ISOLATED' or 'CROSS'
qty = 1  # Amount of concurrent opened positions
orders = 0
symbol = 'BTCUSDT'
direction = ''
fee_rate = 0.0007  # Adjust this to your actual fee rate

def get_fee_rate():
    return fee_rate
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


volume = get_balance_usdt()


# Getting candles for the needed symbol, its a dataframe with 'Time', 'Open', 'High', 'Low', 'Close', 'Volume'
def klines(symbol):
    try:
        resp = pd.DataFrame(client.klines(symbol, '1m'))
        resp = resp.iloc[:,:6]
        resp.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        resp = resp.set_index('Time')
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

#Check if the position is open
def is_position_open(symbol):
    try:
        position_info = client.get_position_risk(symbol=symbol)
        print("Position info:",position_info)
        if position_info:
            return True
        else:
            return False
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )


# Open new order with the last price, and set TP and SL:
def open_order(symbol, side):
    fee_rate = get_fee_rate()
    volume = get_balance_usdt()
    price = float(client.ticker_price(symbol)['price'])
    qty_precision = get_qty_precision(symbol)
    price_precision = get_price_precision(symbol)
    direction = ''
    print('Price:', price)
    print('Volume:',volume)
    print("normal quantity:", volume/(price))
    if side == 'buy':
        price = price * (1 + fee_rate)
        qty = math.floor((volume/(price) * 10**qty_precision)) / 10**qty_precision
    elif side == 'sell':  # shorting
        price = price * (1 - fee_rate)
        qty = math.floor((volume/(price) * 10**qty_precision)) / 10**qty_precision
    print("rounded down quantity:", qty)
    trade_happend = False
    if side == 'buy':
        while not trade_happend:
            try:
                required_margin = (price) * qty
                print("Required margin for the trade: ", required_margin)
                resp1 = client.new_order(symbol=symbol, side=SIDE_BUY, type=FUTURE_ORDER_TYPE_MARKET,quantity=qty)
                print(symbol, side, "placing order")
                trade_happend = True

                print(resp1)
                direction = 'up'

                sl_price = round(price - price*sl, price_precision)
                resp2 = client.new_order(symbol=symbol, side=SIDE_SELL, type=FUTURE_ORDER_TYPE_STOP_MARKET, quantity=qty, timeInForce='GTC', stopPrice=sl_price)
                print(resp2)

            except ClientError as error:
                print(
                    "Found error. status: {}, error code: {}, error message: {}".format(
                        error.status_code, error.error_code, error.error_message
                    )
                )
                qty=previous_qty(symbol, qty)
                        
        account_info = client.account()
        print("Available margin: ", account_info['availableBalance'])

    if side == 'sell':
        while not trade_happend:
            try:
                required_margin = (price) * qty
                print("Required margin for the trade: ", required_margin)
                resp1 = client.new_order(symbol=symbol, side=SIDE_SELL, type=FUTURE_ORDER_TYPE_MARKET,quantity=qty)

                print(symbol, side, "placing order")
                trade_happend = True

                print(resp1)
                direction = 'down'

                sl_price = round(price + price*sl, price_precision)
                resp2 = client.new_order(symbol=symbol, side=SIDE_BUY,type=FUTURE_ORDER_TYPE_STOP_MARKET, quantity=qty, timeInForce='GTC', stopPrice=sl_price)
                print(resp2)

            except ClientError as error:
                print(
                    "Found error. status: {}, error code: {}, error message: {}".format(
                        error.status_code, error.error_code, error.error_message
                    )
                )
                qty=previous_qty(symbol, qty)
        # Print the margin
        account_info = client.account()
        print("Available margin: ", account_info['availableBalance'])
    
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

# Strategy. Can use any other:

def str_signal(symbol):
    # Get the latest kline data
    klines_data = klines(symbol)
    previous_close_time_str = klines_data.index[-1].strftime("%Y-%m-%d %H:%M:%S")  # The closing time is at index -2
    previous_close_time = datetime.datetime.strptime(previous_close_time_str, "%Y-%m-%d %H:%M:%S")
    print(previous_close_time)
    current_time = client.time()['serverTime']
    current_time = datetime.datetime.fromtimestamp(current_time / 1000)
    print(current_time)
    difference = current_time - previous_close_time
    difference = difference.total_seconds()
    # Check if the previous candle has closed and we're within a 10-second window
    print(difference <= 30)
    if (difference) <= 30:
        print(klines_data['Close'].iloc[-1])
        print(float(client.ticker_price(symbol)['price']))
        if direction == 'down':
            print("up")
            return 'up'
        else:
            print("down")
            return 'down'
    else:
        return 'none'


def handle_signal(symbol, signal, type, leverage):
    print(f'Found {signal.upper()} signal for {symbol}')
    close_open_orders(symbol)
    close_position(symbol)

    set_leverage(symbol, leverage)
    print(f'Placing order for {symbol}')
    direction = open_order(symbol, signal)

    return direction

close_open_orders(symbol)
close_position(symbol)
set_mode(symbol, type)


while True:
    # we need to get balance to check if the connection is good, or you have all the needed permissions
    balance = get_balance_usdt()
    if balance == None:
        print('Cant connect to API. Check IP, restrictions or wait some time')
    if balance != None:
        print("My balance is: ", balance, " USDT")

        signal = str_signal(symbol)

        if signal == 'up' and (direction == 'down' or direction == ''):
            direction = handle_signal(symbol, 'buy', type, leverage)
            sleep(30)
        elif signal == 'down' and (direction == 'up' or direction == ''):
            direction = handle_signal(symbol, 'sell', type, leverage)
            sleep(30)