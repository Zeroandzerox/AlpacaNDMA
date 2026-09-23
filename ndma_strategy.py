from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from pandas import Timestamp, Timedelta

import configparser
import errno
import json
import logging
import os
from pathlib import Path
from random import shuffle

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.common.exceptions import APIError

import boto3
from botocore.exceptions import ClientError


class Settings:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    @classmethod
    def from_environment(cls, config_path: Path) -> 'Settings':
        config = configparser.ConfigParser()
        if config_path.exists():
            logging.info('Loading configuration from %s', config_path)
            with config_path.open(encoding='utf-8') as configfile:
                config.read_file(configfile)

        section = config['APIKEYS'] if config.has_section('APIKEYS') else {}
        api_key = os.getenv('ALPACA_API_KEY', section.get('API_Key_ID', '')).strip()
        try:
            secret_key = cls.get_secret('Alpaca_50DMA_Secret_Key', 'us-east-1')
        except ClientError:
            logging.warning('Falling back to environment or config for Alpaca secret')
            secret_key = os.getenv(
                'ALPACA_SECRET_KEY', section.get('Secret_Key', '')
            ).strip()
        
        if not api_key or not secret_key:
            raise ValueError(
                'Set ALPACA_API_KEY and ALPACA_SECRET_KEY, or provide config.txt'
            )
        return cls(api_key, secret_key)

    @staticmethod
    def get_secret(secret_name: str, region_name: str) -> str:
        secret_name = "Alpaca_50DMA_Secret_Key" if not secret_name else secret_name
        region_name = "us-east-1" if not region_name else region_name
        try:
            # Create a Secrets Manager client
            session = boto3.session.Session()
            client = session.client(
                service_name='secretsmanager',
                region_name=region_name
            )       
            get_secret_value_response = client.get_secret_value(
                SecretId=secret_name
            )
        except ClientError as e:
            logging.error(f"Error retrieving secret {secret_name}: {e}")
            raise e

        secret_string = get_secret_value_response['SecretString'].strip()
        try:
            secret_value = json.loads(secret_string)
            if isinstance(secret_value, dict):
                for key in ('Secret_Key', 'ALPACA_SECRET_KEY', 'secret_key'):
                    if key in secret_value and isinstance(secret_value[key], str):
                        return secret_value[key].strip()
        except json.JSONDecodeError:
            return secret_string
        return secret_string

# indicator is a function that takes a dataframe of stock bars and returns a list of values for each symbol
# BreakoutStrategy determines if the last price has changed sides of the line defined by the last and second to last value in the list returned by the strategy function.

class BreakoutStrategy:
    def __init__(self, N: int, symbols: list, settings: Settings, indicator):
        self.client = StockHistoricalDataClient(settings.api_key, settings.secret_key)
        self.tradingClient = TradingClient(
            settings.api_key,
            settings.secret_key,
            paper=True
        )
        self.N = N
        self.symbols = symbols
        self.indicator = indicator

    def run(self):
        shuffle(self.symbols)
        stock_bars_request = StockBarsRequest(
            symbol_or_symbols=self.symbols,
            timeframe=TimeFrame.Day,
            start=Timestamp.today() - Timedelta(self.N * 4, 'D'),
            end=Timestamp.today().normalize()
        )
        bars = self.client.get_stock_bars(stock_bars_request)
        df = bars.df
        stock_quote_request = StockLatestQuoteRequest(
            symbol_or_symbols=self.symbols
        )
        quotes = self.client.get_stock_latest_quote(stock_quote_request)

        for symbol in df.index.get_level_values('symbol').unique():
            logging.debug('Evaluating %s', symbol)
            closes = df.loc[symbol]['close']
            signal = self.indicator(df.loc[symbol])
            previous_close = closes.iloc[-2]
            last_ask = quotes[symbol].ask_price
            last_bid = quotes[symbol].bid_price
            last_mid = (last_bid + last_ask) / 2
            last_signal = signal.iloc[-1]
            previous_signal = signal.iloc[-2]
            if last_mid > last_signal and previous_close < previous_signal:
                logging.info(
                    'Buy signal for %s @ %s, breakout from prior close=%s MA=%s to %s',
                    symbol, last_ask, previous_close, previous_signal, last_signal,
                )
                try:
                    self.tradingClient.get_open_position(symbol)
                    logging.info('%s already held; no order placed', symbol)
                    continue
                except APIError:
                    pass
                orders = self.tradingClient.get_orders(
                    GetOrdersRequest(status='open', symbols=[symbol])
                )
                for order in orders:
                    logging.info(
                        'Open order for %s @ %s still unfilled; canceling to reprice',
                        symbol, order.limit_price,
                    )
                    self.tradingClient.cancel_order_by_id(order.id)
                if float(self.tradingClient.get_account().regt_buying_power) >= 10 * (last_mid + 0.01):
                    order = LimitOrderRequest(
                        symbol=symbol,
                        qty=10,
                        limit_price=round(last_mid + 0.01, 2),
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY
                    )
                    self.tradingClient.submit_order(order)
                    logging.info('Placed buy order for %s @ %s', symbol, round(last_mid + 0.01, 2))
            elif last_mid < last_signal and previous_close > previous_signal:
                logging.info('Sell signal for %s @ %s', symbol, last_mid - 0.01)
                try:
                    position = self.tradingClient.get_open_position(symbol)
                    if position.qty > 0:
                        orders = self.tradingClient.get_orders(
                            GetOrdersRequest(status='open', symbols=[symbol])
                        )
                    for order in orders:
                        self.tradingClient.cancel_order_by_id(order.id)
                    order = LimitOrderRequest(
                        symbol=symbol,
                        qty=position.qty,
                        limit_price=round(last_mid - 0.01, 2),
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY,
                    )
                    self.tradingClient.submit_order(order)
                    logging.info('Placed sell order for %s @ %s', symbol, round(last_mid - 0.01, 2))
                except APIError as api_error:
                    logging.error('Error selling %s: %s', symbol, api_error.message)
                    continue
            else:
                logging.info(
                    'No break for %s @ %s between %s and %s',
                    symbol, last_mid, previous_signal, last_signal,
                )

    #Simple Moving Average
    def SMA(self, bars):
        return bars['close'].rolling(window=self.N).mean()

    #Rolling Day Volume Weighted Average Price for the past N days: the average price over the past N days weighted by volume.
    def RDVWAP(self, bars):
        return (bars['vwap'] * bars['volume']).rolling(window=self.N).sum() / bars['volume'].rolling(window=self.N).sum()

    #Daily Volume Weighted Average Price: the average price of each given day based on the volume of the underlying trades (calculated by alpaca)
    def VWAP(self, bars):
        return bars['vwap']
    
    #Exponentially Weighted Moving Average
    def EWMA(self, bars):
        return bars['close'].ewm(span=self.N, adjust=False).mean()

    #Inverse Variance Adjusted Volume Weighted Average Price
    def IVVWAP(self, bars):
        inverse_variance = bars['vwap'] / ((bars['high']-bars['low']) ** 2)
        weight = inverse_variance * bars['volume']
        return (bars['vwap'] * weight).rolling(window=self.N).sum() / weight.rolling(window=self.N).sum()

    
def get_universe(universe_path: Path) -> list:
    if not universe_path.exists():
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), universe_path)
    with universe_path.open(encoding='utf-8') as universe_file:
        return [line.strip() for line in universe_file if line.strip()]