from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import pandas as pd
import time

import configparser
import os, errno
import os.path as path

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus

from alpaca.common.exceptions import APIError
import logging

from random import shuffle
import datetime
import argparse





class NDMA():
    def __init__(self, N:int, symbols:list):
        config = configparser.ConfigParser()
        with open('config.txt', 'r') as configfile:
            config.read_file(configfile,'config.txt')
        if config['APIKEYS']['API_Key_ID'] != '':
            public_key = config['APIKEYS']['API_Key_ID']
        if config['APIKEYS']['Secret_Key'] != '':
            secret_key = config['APIKEYS']['Secret_Key']
        endpoint = config['APIKEYS']['Endpoint']
        # keys required for stock historical data client
        self.client = StockHistoricalDataClient(public_key, secret_key)
        self.tradingClient = TradingClient(public_key, secret_key)
        self.N = N
        self.symbols = symbols
        
    def run(self):
        #get last N bars for universe.
        shuffle(self.symbols)
        stockBarsRequestHeaders = StockBarsRequest(
            symbol_or_symbols=self.symbols,
            timeframe=TimeFrame.Day,
            start=pd.Timestamp.today() - pd.Timedelta(self.N*4,'D'),
            end=pd.Timestamp.today() 
            )
        bars = self.client.get_stock_bars(
            stockBarsRequestHeaders
            )
        df = bars.df
        stockQuoteRequestHeaders = StockLatestQuoteRequest(symbol_or_symbols=self.symbols, feed='iex')
        quotes = self.client.get_stock_latest_quote(stockQuoteRequestHeaders)
        
        for symbol in df.index.get_level_values("symbol").unique():
            logging.debug(f'Evaluating {symbol}')
            closes = df.loc[symbol]['close']
            avg = closes.rolling(self.N).mean()
            
            previous_close = closes.iloc[-2]
            last_ask = quotes[symbol].ask_price
            last_bid = quotes[symbol].bid_price
            last_mid = (last_bid + last_ask)/2
            last_NDMA = avg.iloc[-1]
            previous_NDMA = avg.iloc[-2]
            if last_mid > last_NDMA and previous_close < previous_NDMA:
                logging.info(f'Buy signal for {symbol} @ {last_ask}, breakout from prior close={previous_close} MA={previous_NDMA} to {last_NDMA}')
                #if there is a held position of the security, pass
                try:
                    self.tradingClient.get_open_position(symbol)
                    logging.info(f'{symbol} already held no order placed')
                    continue
                except(APIError):
                    pass
                getOrdersRequestHeader = GetOrdersRequest(status='open',symbols=[symbol])
                orders = self.tradingClient.get_orders(getOrdersRequestHeader)
                if len(orders)>0: #if there are one or more open orders for the security, cancel the outstanding orders then place a new order 
                    for order in orders:
                        logging.info(f'open order for {symbol} @ {order.limit_price} still unfilled, canceling to reprice')
                        self.tradingClient.cancel_order_by_id(order.id)
                if float(self.tradingClient.get_account().regt_buying_power)>= 10*(last_mid+.01):
                    limitOrderRequestHeaders = LimitOrderRequest(
                        symbol=symbol,
                        qty=10,
                        limit_price=round(last_mid+0.01,2),
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY
                    )    
                    self.tradingClient.submit_order(limitOrderRequestHeaders)
                    logging.info(f'Placed Buy order for {symbol} @ {round(last_mid+0.01,2)}')
            elif last_mid < last_NDMA and previous_close > previous_NDMA:
                logging.info(f'Sell {symbol} @ {last_mid-0.01} breakout from prior close={previous_close} MA={previous_NDMA} to {last_NDMA}')
                try:
                    position = self.tradingClient.get_open_position(symbol)
                    getOrdersRequestHeader = GetOrdersRequest(status='open',symbols=[symbol])
                    orders = self.tradingClient.get_orders(getOrdersRequestHeader)
                    if len(orders)>0: #if there are one or more open orders for the security, cancel the outstanding orders then place a new order 
                        for order in orders:
                            self.tradingClient.cancel_order_by_id(order.id)
                    limitOrderRequestHeaders = LimitOrderRequest(
                        symbol=symbol,
                        qty=position.qty,
                        limit_price=round(last_mid-0.01,2),
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY
                    )    
                    self.tradingClient.submit_order(limitOrderRequestHeaders)
                    logging.info(f'Placed Sell order for {symbol} @ {round(last_mid-0.01,2)}')
                except(APIError):
                    continue
            else:
                logging.info(f'No break for {symbol} @ {last_mid} between {previous_NDMA} to {last_NDMA}')


        
def get_universe(universe_fname):
        #if the universe file does not exist raise FileNotFoundError
        symbols = list()
        if path.exists(universe_fname):
            with open(universe_fname,'r') as universe_file:
                for line in universe_file:
                    symbols.append(line.strip())
        else:
            logging.error('No Universe File Found!')
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), universe_fname)
        return symbols

parser = argparse.ArgumentParser(prog="NDMA",description="executes a stock trading strategy based on the current price breaking above or N-Day moving average.")
parser.add_argument('-d', '--days', type=int, default=50)
parser.add_argument('-u', '--universe', default='universe')
args = parser.parse_args()

logging.basicConfig(
    filename=f'ndma_{datetime.date.today().isoformat()}.log',
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    force=True
)
logging.info("Logging started.")

if args.days < 2:
    parser.error("--days must be greater than 1")

ndma = NDMA(args.days,get_universe(args.universe))

while True:
    try:
        clock = ndma.tradingClient.get_clock()
        ndma.tradingClient.get_account()
        if clock.is_open:
            if clock.next_close.timestamp() - time.time() < 300:
                logging.info("Market Close in < 5 min. Stopping")
                logging.shutdown()
                break
            ndma.run()
            time.sleep(60)
        else:
            time_to_next_open = clock.next_open.timestamp()-time.time()
            if time_to_next_open > (24*60*20):
                logging.info("More than 24h to next open. Stopping")
                logging.shutdown()
                break
            logging.info(f'Sleeping till open {time_to_next_open} seconds')
            time.sleep(time_to_next_open)
    except Exception as ex:
        logging.exception(f'Exception {ex}')
        time.sleep(60)