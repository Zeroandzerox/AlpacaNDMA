import argparse
import logging
import os
from pathlib import Path
from typing import Optional
from ndma_strategy import NDMA, Settings, get_universe

def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(
        prog='NDMA',
        description='Executes the N-day moving average breakout strategy.',
    )
    parser.add_argument('-d', '--days', type=int, default=int(os.getenv('NDMA_DAYS', '50')))
    parser.add_argument('-u', '--universe', default=os.getenv('NDMA_UNIVERSE', 'universe'))
    args = parser.parse_args(argv)
    if args.days < 2:
        parser.error('--days must be greater than 1')

    logging.basicConfig(
        level=os.getenv('LOG_LEVEL', 'INFO').upper(),
        format='%(asctime)s %(levelname)s %(message)s',
        force=True,
    )
    base_dir = Path(__file__).resolve().parent
    universe_path = Path(args.universe)
    if not universe_path.is_absolute():
        universe_path = base_dir / universe_path
    settings = Settings.from_environment(base_dir / 'config.txt')
    NDMA(args.days, get_universe(universe_path), settings).run()


if __name__ == '__main__':
    main()