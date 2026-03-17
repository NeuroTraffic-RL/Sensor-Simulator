"""
Entry point for SUMO sensor simulator.
Usage: python -m sumo_sensor --config config.json
"""

import argparse
import sys
from pathlib import Path

from .runner import run_simulation


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='SUMO-RL Traffic Sensor Simulator v1.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m sumo_sensor --config config.json
  python -m sumo_sensor --config myconfig.json --log-level DEBUG

For more information, see README.md
        """
    )

    parser.add_argument(
        '--config',
        '-c',
        type=str,
        required=True,
        help='Path to configuration JSON file'
    )

    parser.add_argument(
        '--log-level',
        '-l',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level (default: INFO)'
    )

    parser.add_argument(
        '--version',
        '-v',
        action='version',
        version='SUMO Sensor Simulator v1.0'
    )

    args = parser.parse_args()

    # Validate config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    # Setup logging level
    import logging
    from .utils.logger import setup_logger

    log_level = getattr(logging, args.log_level.upper())
    setup_logger(level=log_level)

    # Run simulation
    run_simulation(str(config_path))


if __name__ == '__main__':
    main()
