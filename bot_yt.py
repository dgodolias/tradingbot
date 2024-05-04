import math
from binance.um_futures import UMFutures
import talib as ta
import pandas as pd
from time import sleep
from binance.error import ClientError
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET

client = UMFutures(key = 'b1058af01fe2fe687de39cee6c253157a905cfa8d12b257cae5875eb93ffc6a0', secret='2f91937eae08fb22a25d3372e70180690a5c8da185077e66d759b4d440e68d80')
client.base_url = 'https://testnet.binancefuture.com'

# 0.012 means +1.2%, 0.009 is -0.9%
tp = 10
sl = 0.4
leverage = 1
type = 'ISOLATED'  # type is 'ISOLATED' or 'CROSS'
qty = 1  # Amount of concurrent opened positions
orders = 0
symbol = 'BTCUSDT'
direction = ''

# getting your futures balance in USDT
def get_balance_usdt():
    try:
        account_info = client.account(recvWindow=6000)
        return float(account_info['availableBalance'])

    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )


volume = get_balance_usdt()

# Getting all available symbols on the Futures ('BTCUSDT', 'ETHUSDT', ....)
def get_tickers_usdt():
    tickers = []
    resp = client.ticker_price()
    for elem in resp:
        if 'USDT' in elem['symbol']:
            tickers.append(elem['symbol'])
    return tickers


# Getting candles for the needed symbol, its a dataframe with 'Time', 'Open', 'High', 'Low', 'Close', 'Volume'
def klines(symbol):
    try:
        resp = pd.DataFrame(client.klines(symbol, '1m'))
        resp = resp.iloc[:,:6]
        resp.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        resp = resp.set_index('Time')
        resp.index = pd.to_datetime(resp.index, unit = 'ms')
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


# Open new order with the last price, and set TP and SL:
def open_order(symbol, side):
    price = float(client.ticker_price(symbol)['price'])
    qty_precision = get_qty_precision(symbol)
    price_precision = get_price_precision(symbol)
    print("normal quantity:", volume/(price*1.0007))
    qty = math.floor(volume/(price*1.0007) * 10**qty_precision) / 10**qty_precision
    print("rounded down quantity:", qty)
    order_id = None
    filled_qty = 0
    if side == 'buy':
        try:
            required_margin = (price*1.0007) * qty
            print("Required margin for the trade: ", required_margin)
            resp1 = client.new_order(symbol=symbol, side='BUY', type='MARKET', quantity=qty)
            print(symbol, side, "placing order")
            print(resp1)
            order_id = resp1['orderId']
            filled_qty = float(resp1['executedQty'])
            sleep(2)
            sl_price = round(price - price*sl, price_precision)
            resp2 = client.new_order(symbol=symbol, side='SELL', type='STOP_MARKET', quantity=filled_qty, timeInForce='GTC', stopPrice=sl_price)
            print(resp2)
            sleep(2)
            tp_price = round(price + price * tp, price_precision)
            resp3 = client.new_order(symbol=symbol, side='SELL', type='TAKE_PROFIT_MARKET', quantity=filled_qty, timeInForce='GTC',
                                     stopPrice=tp_price)
            print(resp3)
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
                    # Print the margin
        account_info = client.account()
        print("Available margin: ", account_info['availableBalance'])

    if side == 'sell':
        try:
            resp1 = client.new_order(symbol=symbol, side='SELL', type='MARKET', quantity=qty)
            print(symbol, side, "placing order")
            print(resp1)
            order_id = resp1['orderId']
            filled_qty = float(resp1['executedQty'])
            print("Filled qty: ", filled_qty)
            sleep(2)
            sl_price = round(price + price*sl, price_precision)
            resp2 = client.new_order(symbol=symbol, side='BUY', type='STOP_MARKET', quantity=filled_qty, timeInForce='GTC', stopPrice=sl_price)
            print(resp2)
            sleep(2)
            tp_price = round(price - price * tp, price_precision)
            resp3 = client.new_order(symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', quantity=filled_qty, timeInForce='GTC',
                                     stopPrice=tp_price)
            print(resp3)
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
    return (order_id,filled_qty==qty)

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

    if direction in ["", "up"]:
        return 'up'
    else:
        return 'down'

def handle_signal(symbol, signal, type, leverage):
    print(f'Found {signal.upper()} signal for {symbol}')
    close_position(symbol)
    close_open_orders(symbol)
    set_mode(symbol, type)
    set_leverage(symbol, leverage)
    print(f'Placing order for {symbol}')
    order = open_order(symbol, signal)
    #order_id = order[0]
    #order_filled = order[1]

    return order


while True:
    # we need to get balance to check if the connection is good, or you have all the needed permissions
    balance = get_balance_usdt()
    sleep(1)
    if balance == None:
        print('Cant connect to API. Check IP, restrictions or wait some time')
    if balance != None:
        print("My balance is: ", balance, " USDT")

        signal = str_signal(symbol)

        if signal == 'up' and (direction == 'down' or direction == ''):
            order = handle_signal(symbol, 'buy', type, leverage)
            direction = 'up'
        elif signal == 'down' and (direction == 'up' or direction == ''):
            order = handle_signal(symbol, 'sell', type, leverage)
            direction = 'down'
                    # break
    print('Waiting 3 min')
    sleep(10)