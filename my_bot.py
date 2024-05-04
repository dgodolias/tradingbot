from binance.client import Client

class TradingBot:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)

    def get_balance(self, asset):
        """Get balance of a specific asset"""
        balance = self.client.get_asset_balance(asset=asset)
        return balance

    def place_margin_order(self, symbol, side, type, quantity, leverage):
        """Place a margin order"""
        # First, borrow the asset
        self.client.create_margin_loan(asset=symbol, amount=quantity)

        # Then, place the order
        order = self.client.create_margin_order(
            symbol=symbol,
            side=side,
            type=type,
            quantity=quantity,
            timeInForce=Client.TIME_IN_FORCE_GTC
        )

        # Finally, adjust the leverage
        self.client.change_margin_leverage(symbol=symbol, leverage=leverage)

        return order

    def place_long_order(self, symbol, quantity, leverage):
        """Place a long order"""
        return self.place_margin_order(symbol, Client.SIDE_BUY, Client.ORDER_TYPE_MARKET, quantity, leverage)

    def place_short_order(self, symbol, quantity, leverage):
        """Place a short order"""
        return self.place_margin_order(symbol, Client.SIDE_SELL, Client.ORDER_TYPE_MARKET, quantity, leverage)

    def get_open_orders(self, symbol):
        """Get open orders of a specific symbol"""
        orders = self.client.get_open_orders(symbol=symbol)
        return orders