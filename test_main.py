#!/usr/bin/env python3
"""
Test script for functions in main.py.
Run individual flows without executing the full pipeline.

Usage:
  python test_main.py --tps              # Test run_tps_measurement() only
  python test_main.py --calcuration FILE # Test run_calcuration(FILE) only
  python test_main.py --send-result PATH # Test send_result_file(PATH) only
"""
import argparse
import sys

# Import from main so we test the same code
from main import run_tps_measurement, run_calcuration, send_result_file


def test_tps_measurement():
    """Test TPS measurement flow (instrument + script + iterations + .hotb)."""
    print("=== Testing run_tps_measurement() ===\n")
    success, hotb_path = run_tps_measurement()
    print(f"\nResult: success={success}, hotb_path={hotb_path}")
    return 0 if success else 1


def test_calcuration(hotb_filename: str):
    """Test HotDisk calculation flow (open .hotb, run commands, export)."""
    print(f"=== Testing run_calcuration({hotb_filename!r}) ===\n")
    run_calcuration(hotb_filename)
    return 0


def test_send_result_file(hotb_filepath: str):
    """Test copying .hotb to CLIENT_PATH as Result_<timestamp>.hotb."""
    print(f"=== Testing send_result_file({hotb_filepath!r}) ===\n")
    success, result_filename = send_result_file(hotb_filepath)
    print(f"\nResult: success={success}, result_filename={result_filename}")
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(
        description="Test individual functions from main.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--tps",
        action="store_true",
        help="Test run_tps_measurement() only",
    )
    group.add_argument(
        "--calcuration",
        metavar="HOTB_FILENAME",
        help="Test run_calcuration(HOTB_FILENAME); e.g. Result_20250129_123456.hotb",
    )
    group.add_argument(
        "--send-result",
        metavar="HOTB_FILEPATH",
        dest="send_result",
        help="Test send_result_file(HOTB_FILEPATH); path to existing .hotb file",
    )
    args = parser.parse_args()

    if args.tps:
        return test_tps_measurement()
    if args.calcuration:
        return test_calcuration(args.calcuration)
    if args.send_result:
        return test_send_result_file(args.send_result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
