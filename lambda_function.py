import logging
import os
import time
from pathlib import Path

from ndma_strategy import NDMA, Settings, get_universe


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    start_time = time.time()
    logging.info('Beginning NDMA Lambda invocation @ %s', time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_time)))
    settings = Settings.from_environment(Path(__file__).parent / 'config.txt')
    trading_client = NDMA(
        int(os.getenv('NDMA_DAYS', '50')),
        get_universe(Path(__file__).parent / os.getenv('NDMA_UNIVERSE', 'universe')),
        settings,
    )

    clock = trading_client.tradingClient.get_clock()
    trading_client.tradingClient.get_account()
    if not clock.is_open:
        logger.info('Market is closed; skipping scheduled invocation')
        return {'status': 'skipped', 'reason': 'market_closed'}
    if clock.next_close.timestamp() - time.time() < 300:
        logger.info('Market close is within five minutes; skipping scheduled invocation')
        return {'status': 'skipped', 'reason': 'near_market_close'}

    trading_client.run()
    end_time = time.time()
    logging.info('NDMA Lambda invocation completed in %s seconds @ %s', round(end_time - start_time, 2), time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(end_time)))
    return {'status': 'completed'}