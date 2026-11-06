from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import sys
import threading
import sys
import kkrb_profit
import config_helper
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
CONFIG_PATH = BASE_DIR / "config.json"
sys.path.insert(0, str(BASE_DIR))

from launcher import Launcher  # noqa: E402
from planner import compute_schedule  # noqa: E402
from reader import Reader, load_config  # noqa: E402
import hotkey  # noqa: E402
import winutil  # noqa: E402

def bootstrap_profit_refresh(logger=print) -> dict:
    """
    启动第一步：拉取 kkrb 单小时利润最高物品，直接写 config.json。
    失败不阻断主程序，回退到原配置继续跑。
    """
    
    logger(f"配置路径是：{CONFIG_PATH}")
    try:
        logger("[boot] 正在从 kkrb 获取四工位单小时利润最高物品…")
        profit_map = kkrb_profit.fetch_hourly_best(timeout=60.0)
        logger(f"[boot] 利润榜结果：{profit_map}")

        config = config_helper.refresh_config_with_profit(
            CONFIG_PATH, profit_map, logger=logger
        )
        logger("[boot] 配置已按利润榜更新")
        return config
    except Exception as e:
        logger(f"[boot][WARN] 利润刷新失败，使用原配置继续：{e}")
        # 失败兜底：读原配置返回，不抛异常
        return config_helper.load_config(config)

def main() -> None:
    # 1) 启动第一步：利润刷新（覆盖 config.json）
    bootstrap_profit_refresh(logger=print)

if __name__ == "__main__":
    main()
