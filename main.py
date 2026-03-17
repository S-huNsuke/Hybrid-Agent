#!/usr/bin/env python3
"""Hybrid-Agent 主入口"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from hybrid_agent.cli.main import run_cli


def main() -> None:
    """主函数"""
    run_cli()


if __name__ == "__main__":
    main()