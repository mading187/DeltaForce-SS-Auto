# kkrb_profit.py（在原有代码基础上替换/追加）
from __future__ import annotations

import time
from typing import Optional, Literal
import sys
import config_helper
from pathlib import Path

from test_get_kkru_message import ProfitAdvisor, AdvisorError

BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)

CONFIG_PATH = BASE_DIR / "config.json"

ProfitMode = Literal["hourly", "total"]


# ───────────────────────── 取数层 ─────────────────────────

def fetch_hourly_best(timeout: float = 60.0, retries: int = 2) -> dict[str, str]:
    """
    取四设施「单小时利润最高」物品。
    返回：{"技术中心": "xxx", "工作台": "xxx", ...}
    """
    return _fetch_profit_list("hourly", timeout, retries)


def fetch_total_best(timeout: float = 60.0, retries: int = 2) -> dict[str, str]:
    """
    取四设施「总利润最高」物品。
    返回：{"技术中心": "xxx", "工作台": "xxx", ...}
    """
    return _fetch_profit_list("total", timeout, retries)


def _fetch_profit_list(
    mode: ProfitMode, timeout: float, retries: int
) -> dict[str, str]:
    attr = "total_profit" if mode == "total" else "hourly_profit"
    metric_name = "总利润" if mode == "total" else "单小时利润"

    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            recs = ProfitAdvisor(timeout=timeout).fetch()
            items = getattr(recs, attr)
            mapping: dict[str, str] = {}
            for item in items:               # 已按设施顺序
                if item.facility_name and item.item_name:
                    mapping[item.facility_name] = item.item_name
            if not mapping:
                raise AdvisorError(f"{metric_name}榜返回为空")
            return mapping
        except AdvisorError as e:
            last_exc = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise AdvisorError(f"kkrb 取数失败（{metric_name}）：{last_exc}")


# ───────────────────────── 刷新入口 ─────────────────────────

def bootstrap_profit_refresh(
    logger=print,
    mode: ProfitMode = "hourly",
) -> dict:
    """
    统一入口：拉取 kkrb 利润最高物品，写 config.json。
    :param mode: "hourly" 单小时利润最高 | "total" 总利润最高
    失败不阻断主程序，回退到原配置继续跑。
    """
    logger(f"配置路径是：{CONFIG_PATH}")

    try:
        if mode == "total":
            logger("[boot] 正在从 kkrb 获取四工位【总利润最高】物品…")
            profit_map = fetch_total_best(timeout=60.0)
        else:
            logger("[boot] 正在从 kkrb 获取四工位【单小时利润最高】物品…")
            profit_map = fetch_hourly_best(timeout=60.0)

        logger(f"[boot] 利润榜结果：{profit_map}")

        config = config_helper.refresh_config_with_profit(
            CONFIG_PATH, profit_map, logger=logger
        )
        logger(f"[boot] 配置已按{mode}利润榜更新")
        return config

    except Exception as e:
        logger(f"[boot][WARN] 利润刷新失败，使用原配置继续：{e}")
        # 修复原 bug：直接读原配置文件，不引用未定义变量
        return config_helper.load_config(CONFIG_PATH)


# ── 语义化快捷入口（给 GUI 按钮用，可读性更好）──

def bootstrap_hourly_profit_refresh(logger=print) -> dict:
    return bootstrap_profit_refresh(logger=logger, mode="hourly")


def bootstrap_total_profit_refresh(logger=print) -> dict:
    return bootstrap_profit_refresh(logger=logger, mode="total")


# # kkrb_profit.py
# """kkrb 利润榜取数层：返回 {设施中文名: 单小时利润最高物品名}"""
# from __future__ import annotations

# import time
# from typing import Optional
# import sys
# import config_helper
# from pathlib import Path

# from test_get_kkru_message import ProfitAdvisor, AdvisorError

# BASE_DIR = (
#     Path(sys.executable).resolve().parent
#     if getattr(sys, "frozen", False)
#     else Path(__file__).resolve().parent
# )

# CONFIG_PATH = BASE_DIR / "config.json"

# def bootstrap_profit_refresh(logger=print) -> dict:
#     """
#     启动第一步：拉取 kkrb 单小时利润最高物品，直接写 config.json。
#     失败不阻断主程序，回退到原配置继续跑。
#     """
    
#     logger(f"配置路径是：{CONFIG_PATH}")
#     try:
#         logger("[boot] 正在从 kkrb 获取四工位单小时利润最高物品…")
#         profit_map = fetch_hourly_best(timeout=60.0)
#         logger(f"[boot] 利润榜结果：{profit_map}")

#         config = config_helper.refresh_config_with_profit(
#             CONFIG_PATH, profit_map, logger=logger
#         )
#         logger("[boot] 配置已按利润榜更新")
#         return config
#     except Exception as e:
#         logger(f"[boot][WARN] 利润刷新失败，使用原配置继续：{e}")
#         # 失败兜底：读原配置返回，不抛异常
#         return config_helper.load_config(config)





# def fetch_hourly_best(timeout: float = 60.0, retries: int = 2) -> dict[str, str]:
#     """
#     取四设施「单小时利润最高」物品。
#     返回：{"技术中心": "xxx", "工作台": "xxx", "制药台": "xxx", "防具台": "xxx"}
#     失败重试 retries 次，仍失败抛 AdvisorError。
#     """
#     last_exc: Optional[Exception] = None
#     for attempt in range(retries + 1):
#         try:
#             recs = ProfitAdvisor(timeout=timeout).fetch()
#             mapping: dict[str, str] = {}
#             for item in recs.hourly_profit:          # 已按设施顺序
#                 if item.facility_name and item.item_name:
#                     mapping[item.facility_name] = item.item_name
#             if not mapping:
#                 raise AdvisorError("利润榜返回为空")
#             return mapping
#         except AdvisorError as e:
#             last_exc = e
#             if attempt < retries:
#                 time.sleep(1.5 * (attempt + 1))
#     raise AdvisorError(f"kkrb 取数失败：{last_exc}")


# # 设施中文名 -> config 里的 station key（和你 config.json 完全一致）
# EXPECTED_STATIONS = ["技术中心", "工作台", "制药台", "防具台"]