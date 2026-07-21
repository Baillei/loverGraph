#!/usr/bin/env python3
"""Show scenario background without starting trial."""

from lover_graph.cli import main

if __name__ == "__main__":
    import sys

    if "--show-scenario" not in sys.argv:
        sys.argv.insert(1, "--show-scenario")
    main()
