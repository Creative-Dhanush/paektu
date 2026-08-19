"""Entry point so the tool runs as `python -m plumbline`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
