# NDMA

NDMA is a Python-based algorithmic trading strategy for [Alpaca](https://alpaca.markets/) that trades stocks when the current market price breaks through an N-day simple moving average (SMA).

The strategy is designed to run once per scheduled invocation during market hours. It can be deployed as an AWS Lambda function triggered by EventBridge Scheduler. Example chron expression(for AWS):
> */2 9-15 ? * MON-FRI * 
AWS does not allow expressions which execute >=1/minute

Warning: This software *can* place real stock orders through the Alpaca API. It is designed to be used as a validation test for more complex strategies when run parallel. It is highly recommended you use [paper trading](https://docs.alpaca.markets/us/docs/paper-trading) in an account not running any other strategies or manual trades.

## How It Works

For each symbol in the configured universe, NDMA:

1. Retrieves approximately 4 × N days of daily historical bars. (current safety buffer to ensure at least N bars are returned)
2. Calculates the N-day simple moving average.
3. Retrieves the latest bid/ask quote.
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

Each Lambda invocation checks the Alpaca market clock once. If the market is closed or within five minutes of closing, the invocation exits without trading. When the market is open, it performs one strategy evaluation and exits.

## Requirements
- Python 3.9+
- An Alpaca account
- Alpaca API access and credentials
- Pandas
- Alpaca-py

Install the Python dependencies with:

> pip install alpaca-py pandas

## Configuration

For cloud deployment, configure these environment variables through the platform's secret manager. Environment variables take precedence over the local file:

> ALPACA_API_KEY=YOUR_ALPACA_API_KEY
>
> ALPACA_SECRET_KEY=YOUR_ALPACA_SECRET_KEY
>
> ALPACA_ENDPOINT=https://paper-api.alpaca.markets/v2

`ALPACA_ENDPOINT` defaults to the paper endpoint. Set it to the live endpoint only when live trading is intended. `NDMA_DAYS`, `NDMA_UNIVERSE`, and `LOG_LEVEL` are also supported.

For local development, an example configuration file without credentials (`config_template.txt`) is included. Copy it to `config.txt`; The file should be formatted as shown below:

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

## AWS Lambda deployment

Package `lambda_function.py`, `ndma_strategy.py`, `universe`, and the installed dependencies into a Lambda deployment zip. Configure the handler as:

> lambda_function.lambda_handler

Create an EventBridge Scheduler rule for the desired market-hours cadence, such as once per day before the expected market open. The function checks the market clock itself, so weekend, holiday, and late-close invocations exit without trading.

Store `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in AWS Secrets Manager or encrypted Lambda environment variables. Set `ALPACA_ENDPOINT` to the paper endpoint while validating the deployment.

Set Lambda reserved concurrency to `1` to reduce overlapping invocations. For stronger protection, add a DynamoDB conditional lock before submitting orders.

## Multiple Accounts

Deploy separate Lambda functions or separate scheduled rules for independent Alpaca accounts, each with its own credentials and environment configuration.

**Do not run NDMA in an account alongside other strategies or manual trades, the algorithm does not distinguish between orders it placed and orders placed independently**

## Logging

Lambda writes execution logs to CloudWatch through standard python logging.

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

The strategy will cancel an existing open order and replace it with a new order when not filled by the time the script runs again. It should not be run in an account alongside other strategies or manual trades. No guardrails exist to prevent its interference with orders it did not generate.

### Market Data

This script relies on Alpaca's documented default behavior for lastest quote source (SIP if you have unlimited subscription IEX otherwise). The IEX quote may not represent the complete consolidated U.S. market.

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
