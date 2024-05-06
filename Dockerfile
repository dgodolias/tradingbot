# Use an official Python runtime as a parent image
FROM python:3.8-slim-buster

# Set the working directory in the container to /app
WORKDIR /app

# Add the current directory contents into the container at /app
ADD . /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    wget

# Install TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xvzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib/ \
    && ./configure --prefix=/usr \
    && make \
    && make install

# Install the necessary Python packages
RUN pip install --no-cache-dir -v binance
RUN pip install --no-cache-dir -v pandas
RUN pip install --no-cache-dir -v TA-Lib
RUN pip install --no-cache-dir -v pause
RUN pip install --no-cache-dir -v python-binance
RUN pip install --no-cache-dir -v binance-futures-connector

# Make port 80 available to the world outside this container
EXPOSE 80

# Run trading_bot.py when the container launches
CMD ["python", "trading_bot.py"]