# config_helper.py
"""配置加载 / 合并利润物品 / 原子写盘"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional


def load_config(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_config_atomic(path: Path, data: dict) -> None:
    """先写临时文件 + fsync，再 os.replace 原子替换，避免半截文件。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8",
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
            delete=False,
        ) as tmp:
            temp_path = Path(tmp.name)
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(temp_path, path)          # 原子替换
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def apply_profit_items(config: dict, profit_map: dict[str, str]) -> list[str]:
    """
    把利润榜物品名写进 config["craft"]["items"] 里对应 station 的 name。
    只改 name，保留 fallback_xy 等其他字段。
    返回：实际更新了的 station 列表（用于日志）。
    """
    craft = config.setdefault("craft", {})
    items = craft.setdefault("items", [])

    # 建索引：station -> item 字典
    by_station: dict[str, dict] = {it.get("station"): it for it in items if it.get("station")}

    updated = []
    for station, item_name in profit_map.items():
        if station not in by_station:
            # config 里没有这个工位，按原结构追加一项
            new_item = {"station": station, "name": item_name, "fallback_xy": None}
            items.append(new_item)
            by_station[station] = new_item
            updated.append(station)
            continue
        entry = by_station[station]
        old = entry.get("name")
        if old != item_name:
            entry["name"] = item_name
            updated.append(station)

    return updated


def refresh_config_with_profit(
    config_path: Path,
    profit_map: dict[str, str],
    logger=print,
) -> dict:
    """
    完整动作：读盘 -> 合并利润物品 -> 原子写回。
    返回更新后的 config。
    """
    config = load_config(config_path)
    updated = apply_profit_items(config, profit_map)
    if updated:
        write_config_atomic(config_path, config)
        logger(f"[profit] 已更新 {len(updated)} 个工位目标：{updated}")
    else:
        logger("[profit] 利润物品无变化，未写盘")
    return config