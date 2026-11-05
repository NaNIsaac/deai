"""Compatibility entry point for the renamed distribution."""

import sys


def main() -> int:
    from uncredit.cli import main as uncredit_main

    print("deai is now uncredit", file=sys.stderr)
    return uncredit_main()
