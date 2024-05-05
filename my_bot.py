import math
import pandas as pd
from time import sleep
import datetime
import coinbasepro.auth_client

client = coinbasepro.AuthenticatedClient(api_key='your_api_key', api_secret='your_api_secret', passphrase='your_passphrase')

# 0.012 means +1.2%, 0.009 is -0.9%
tp = 10
sl = 0.4
qty = 1  # Amount of concurrent opened positions
orders = 0
symbol = 'BTC-USD'
direction = ''

# getting your account balance in USD
def get_balance_usdt():
    accounts = client.get_accounts()
    for account in accounts:
        if account['currency'] == 'USD':
            return float(account['balance'])

volume = get_balance_usdt()

# Getting all available symbols on the Coinbase Pro ('BTC-USD', 'ETH-USD', ....)
def get_tickers_usdt():
    tickers = []
    products = client.get_products()
    for product in products:
        if 'USD' in product['id']:
            tickers.append(product['id'])
    return tickers

# Getting candles for the needed symbol, its a dataframe with 'Time', 'Open', 'High', 'Low', 'Close', 'Volume'
def klines(symbol):
    resp = pd.DataFrame(client.get_product_historic_rates(symbol, granularity=60), columns=['Time', 'Low', 'High', 'Open', 'Close', 'Volume'])
    resp = resp.set_index('Time')
    resp.index = pd.to_datetime(resp.index, unit = 's')
    resp = resp.astype(float)
    return resp

# Open new order with the last price, and set TP and SL:
def open_order(symbol, side):
    fee_rate = 0.0007  # Adjust this to your actual fee rate
    price = float(client.get_product_ticker(product_id=symbol)['price'])
    direction = ''

    print("normal quantity:", volume/(price))
    if side == 'buy':
        price = price * (1 + fee_rate)
        qty = math.floor((volume/(price) * 10**2)/2) / 10**2
    elif side == 'sell':  # shorting
        price = price * (1 - fee_rate)
        qty = math.floor((volume/(price) * 10**2)/2) / 10**2
    print("rounded down quantity:", qty)
    order_id = None
    filled_qty = 0
    if side == 'buy':
        try:
            required_margin = (price) * qty
            print("Required margin for the trade: ", required_margin)
            resp1 = client.place_market_order(product_id=symbol, side='buy', funds=qty)
            print(symbol, side, "placing order")
            print(resp1)
            direction = 'up'
            order_id = resp1['id']
            filled_qty = float(resp1['filled_size'])
        except Exception as error:
            print("Found error: ", error)
        # Print the margin
        account_info = client.get_account('USD')
        print("Available margin: ", account_info['available'])

    if side == 'sell':
        try:
            required_margin = (price) * qty
            print("Required margin for the trade: ", required_margin)
            resp1 = client.place_market_order(product_id=symbol, side='sell', funds=qty)
            print(symbol, side, "placing order")
            print(resp1)
            direction = 'down'
        except Exception as error:
            print("Found error: ", error)
        # Print the margin
        account_info = client.get_account('USD')
        print("Available margin: ", account_info['available'])
    
    return direction

def close_position(symbol):
    try:
        # Get the position details
        position_info = client.get_account(symbol)

        if position_info:
            # Determine the order side based on the position amount
            order_side = 'sell' if float(position_info['balance']) > 0 else 'buy'

            # Place an order to close the position
            client.place_market_order(
                product_id=symbol,
                side=order_side,
                funds=abs(float(position_info['balance'])),
            )

            print(f"Closed position for {symbol}")

    except Exception as error:
        print("Found error: ", error)

# Close open orders for the needed symbol. If one stop order is executed and another one is still there
def close_open_orders(symbol):
    try:
        response = client.cancel_all(product_id=symbol)
        print(response)
    except Exception as error:
        print("Found error: ", error)

# Strategy. Can use any other:

def str_signal(symbol):
    # Get the latest kline data
    klines_data = klines(symbol)
    previous_close_time_str = klines_data.index[-1].strftime("%Y-%m-%d %H:%M:%S")  # The closing time is at index -2
    previous_close_time = datetime.datetime.strptime(previous_close_time_str, "%Y-%m-%d %H:%M:%S")
    print(previous_close_time)
    current_time = datetime.datetime.now()
    print(current_time)
    difference = current_time - previous_close_time
    difference = difference.total_seconds()
    # Check if the previous candle has closed and we're within a 10-second window
    print(difference <= 15)
    if (difference) <= 15:
        print(klines_data['Close'].iloc[-1])
        print(float(client.get_product_ticker(product_id=symbol)['price']))
        if direction == 'down':
            print("up")
            return 'up'
        else:
            print("down")
            return 'down'
    else:
        return 'none'


def handle_signal(symbol, signal):
    print(f'Found {signal.upper()} signal for {symbol}')
    close_open_orders(symbol)
    close_position(symbol)

    print(f'Placing order for {symbol}')
    direction = open_order(symbol, signal)

    return direction

close_open_orders(symbol)
close_position(symbol)

while True:
    # we need to get balance to check if the connection is good, or you have all the needed permissions
    balance = get_balance_usdt()
    if balance == None:
        print('Cant connect to API. Check IP, restrictions or wait some time')
    if balance != None:
        print("My balance is: ", balance, " USD")

        signal = str_signal(symbol)

        if signal == 'up' and (direction == 'down' or direction == ''):
            direction = handle_signal(symbol, 'buy')
        elif signal == 'down' and (direction == 'up' or direction == ''):
            direction = handle_signal(symbol, 'sell')
    print('Waiting 1 second...')
    sleep(1)