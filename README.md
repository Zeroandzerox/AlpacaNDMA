# NDMA

NDMA is a Python-based algorithmic trading strategy for [Alpaca](https://alpaca.markets/) that trades stocks when the current market price breaks through an N-day simple moving average (SMA).

The strategy is designed to run continuously during market hours and can be deployed as multiple independent processes, allowing different strategies and/or Alpaca accounts to run on the same machine.

Warning: This software *can* place real stock orders through the Alpaca API. It is designed to be used as a validation test for more complex strategies when run parallel. Use [paper trading](https://docs.alpaca.markets/us/docs/paper-trading) in an account not running any other strategies or manual trades.

## How It Works

For each symbol in the configured universe, NDMA:

1. Retrieves approximately 4 × N days of daily historical bars. (current safety buffer to ensure at least N bars are returned)
2. Calculates the N-day simple moving average.
3. Retrieves the latest IEX bid/ask quote.
4. Calculates the current midpoint from the bid and ask.
5. Looks for a breakout between the previous day's close and the current price relative to the moving average.

### Buy Signal

A buy signal occurs when:

- The current bid/ask midpoint is above the current N-day moving average,
- **AND**
- The previous day's close was below the previous day's N-day moving average.

When a buy signal occurs, NDMA:

1. Checks whether the symbol is already held.
2. Checks for existing open orders.
3. Cancels existing open orders for that symbol if necessary.
4. Places a 10-share DAY limit buy order at approximately $0.01 above the current midpoint.
5. Only places the order if sufficient buying power is available. (currently designed to use maximum intraday leverage as allowed by regt)

### Sell Signal

A sell signal occurs when:

- The current midpoint is below the current N-day moving average,
- **AND**
- The previous day's close was above the previous day's N-day moving average.

When a sell signal occurs, NDMA:

1. Checks whether the symbol is currently held.
2. Cancels existing open orders for that symbol if necessary.
3. Places a 10-share DAY limit sell order at approximately $0.01 below the current midpoint.

### Market Hours

NDMA continuously checks the Alpaca market clock.

If started when the market is closed, the process waits until the next market open.

During market hours, the strategy runs approximately once per minute.

The strategy intentionally stops when the market is less than five minutes from closing.

## Requirements
- Python 3.9+
- An Alpaca account
- Alpaca API access and credentials
- Pandas
- Alpaca-py

Install the Python dependencies with:

> pip install alpaca-py pandas

## Configuration

NDMA uses a local configuration file so that multiple accounts can be operated independently on the same machine. An example configuration file without credentials (config_template.txt) can be found in this repository. Your configuration file should be formatted as shown bellow and named config.txt

> [APIKEYS]
>
> API_Key_ID: YOUR_ALPACA_API_KEY
>
> Secret_Key: YOUR_ALPACA_SECRET_KEY
>
> Endpoint: YOUR_ALPACA_ENDPOINT

## Stock Universe

The strategy reads symbols from a universe file.

The default filename is:
- universe

One ticker should be placed on each line. The following is an example of a universe file contents:

> AAPL
> 
> MSFT
>
> GOOG
>
> AMZN
>
> META
>
> NVDA

A different universe file name can be supplied as an argument when invoking the script using the --universe argument.

The included universe file is comprised of symbols included in the S&P 500. 

# Running NDMA

By default, NDMA uses a 50-day moving average and standard universe file name 'universe' and can be run from the command line using the following:

> python NDMA.pyw

To use a different moving-average period:

> python NDMA.pyw --days 20

**OR**

> python NDMA.pyw -d 20

To use a different universe:

> python NDMA.pyw --universe my_universe

Both options can be combined:

> python NDMA.pyw --days 20 --universe tech_stocks

The --days argument must be at least 2

## Running with windows task scheduler

I have found it simplest to run this script using windows task scheduler. Starting slightly before market open ensures the script is running at open. I have included a check to ensure starts more than 24 hours from a market open stop immediately to avoid duplicate instances when running daily.

### Triggers 

On a schedule

Daily

Start:  1/1/2026 6:00:00 AM 

### Actions

Start A Program

Program/Script: PATH_TO_PYTHON_INSTALLATION

Arguments: PATH_TO_NDMA -d 200 -u universe

Start in: PATH_TO_DIRECTORY_W_CONFIG

Please note that task scheduler uses your system time. PATHS and argument values should be replaced as needed. PATHS may need to be enclosed in quotations if any of your directory names include a space.

## Multiple Accounts

NDMA is intended to support multiple independent strategy instances on a single machine. Each instance should be run in its own directory with it's own configuration file containing unique API credentials. 

**Do not run NDMA in an account alongside other strategies or manual trades, the algorithm does not distinguish between orders it placed and orders placed independently**

## Logging

NDMA writes execution logs to a file named according to the current date:

> ndma_YYYY-MM-DD.log

For example:

> ndma_2026-08-19.log

## Order Behavior

Orders are submitted as:

Order type: Limit
Quantity: 10 shares
Time in force: DAY

Buy orders are priced approximately $0.01 above the current midpoint.

Sell orders are priced approximately $0.01 below the current midpoint.

If an existing open order is found for a symbol when a new signal occurs, the existing order is cancelled and replaced with a newly priced order.

## Risk Considerations

This strategy is intentionally simple and has several important limitations.

### Fixed Order Quantities

Every buy order uses a fixed quantity of 10 shares. Sell orders use position size.  

A signal does not guarantee that an order will execute. The strategy submits limit orders near the current bid/ask midpoint, but the market can move away before the order fills. for a more complete documentation of potential order failure modes please refer to [alpaca's documentation](https://docs.alpaca.markets/us/docs/paper-trading#rules-and-assumptions).

### Open Orders Are Repriced (Regardless of Source)

The strategy may cancel an existing open order and replace it with a new order when another signal is generated. It should not be run in an account alongside other strategies or manual trades. No guardrails exist to prevent its interference with orders it did not generate.

### Market Data

The strategy uses daily historical bars for the moving average and the IEX feed for the latest quote. The IEX quote may not represent the complete consolidated U.S. market.

Market-data availability and whether quotes are real-time or delayed depends on your Alpaca account. 

# Disclaimers & Disclosures

## Completeness

This script is still a WIP and may contain bugs, omissions or incomplete features.

## AI Assistance

This script and readme have been developed with the assistance of LLMs ("artificial intelligence")

## No Guaranteed Profitability

This strategy can generate losing trades. Past performance is no indication of future results.

This project is not financial advice.

Algorithmic trading involves the risk of loss. Review all source code carefully, test with paper trading, and understand the behavior of the strategy and the Alpaca API before deploying any algorithmic trading with real capital.

I assume no responsibility for financial losses, unintended orders, API failures, software bugs, or other consequences resulting from the use of this software.

# **PLEASE DO NOT RUN THIS ON YOUR ACTUAL PORTFOLIO.** 
