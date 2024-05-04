import time
from binance.client import Client
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
import matplotlib.pyplot as plt


# Create a temporary client to get server time
temp_client = Client()
server_time = temp_client.get_server_time()
offset = server_time['serverTime'] - int(time.time() * 1000)

# Create a client with the correct offset
client = Client('pBXctBYN1vkZBUIOkhBhob5tfK0md1oC3KAo10rJBKMlJgZMwMaQJMaNWLQRsVox', '0kCWDrAB10jKjTPKSWuUaJDmCD23mQApy43cZS8jIHCgNajGpI0k8y43ZYR7p43p')

# Get the historical hourly data
klines = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_15MINUTE, "20 days ago UTC")
df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
df['close'] = pd.to_numeric(df['close'])
df['open'] = pd.to_numeric(df['open'])  # Convert 'open' column to numeric

# Use 'close' price for prediction
data = df['close']

# Fit the ARIMA model
model = ARIMA(data, order=(5,1,0))
model_fit = model.fit()

# Make prediction
start_index = len(data)
end_index = start_index + 9  # Predict the next 10 prices
yhat = model_fit.predict(start=start_index, end=end_index)
print(yhat)

# Plot the data
plt.figure(figsize=(12,6))
plt.plot(data, color='blue', label='Historical data')
plt.plot(yhat, color='red', label='Predicted data')
plt.legend()
plt.show()