# Use an official Python runtime as a parent image
FROM python:3.8-slim-buster

# Set the working directory in the container to /app
WORKDIR /app

# Add the current directory contents into the container at /app
ADD . /app

# Install the necessary packages one at a time with verbose output
RUN pip install --no-cache-dir -v binance
RUN pip install --no-cache-dir -v pandas
RUN pip install --no-cache-dir -v talib
RUN pip install --no-cache-dir -v pause

# Make port 80 available to the world outside this container
EXPOSE 80

# Run trading_bot.py when the container launches
CMD ["python", "trading_bot.py"]