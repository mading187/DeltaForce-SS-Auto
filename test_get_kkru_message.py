from __future__ import annotations

import json
import time
import requests
from dataclasses import dataclass
from typing import List, Optional


BASE_URL = "https://www.kkrb.net"
OVERVIEW_PAGE = BASE_URL + "/?viewpage=view%2Foverview"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 网站设施键 -> 业务设施名
FACILITY_MAP = [
    ("tech", "技术中心"),
    ("workbench", "工作台"),
    ("pharmacy", "制药台"),
    ("armory", "防具台"),
]


class AdvisorError(Exception):
    """数据获取或解析失败，带上下文。"""


@dataclass(frozen=True)
class ProfitItem:
    facility_key: str
    facility_name: str
    item_name: str
    profit: float


@dataclass(frozen=True)
class RecommendationSet:
    total_profit: List[ProfitItem]     # spData
    hourly_profit: List[ProfitItem]    # sphData


class ProfitAdvisor:
    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    def fetch(self) -> RecommendationSet:
        try:
            return self._fetch_core()
        except requests.RequestException as e:
            raise AdvisorError(f"网络请求失败：{e}") from e
        except TimeoutError as e:
            raise AdvisorError(
                f"获取利润推荐超时（{int(self.timeout)}秒），请检查网络后重试。"
            ) from e

    # ---------- 内部实现 ----------

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": OVERVIEW_PAGE,
            "Origin": BASE_URL,
        })
        return s

    def _post_api(self, s: requests.Session, endpoint: str,
                  body: Optional[dict] = None) -> dict:
        # 每次从当前 Cookie 里取 csrf_token 回传（getMenu 之后才有）
        csrf = s.cookies.get("csrf_token")
        headers = {}
        if csrf:
            headers["X-CSRF-Token"] = csrf

        resp = s.post(
            f"{BASE_URL}/{endpoint}",
            data=body,
            headers=headers,
            timeout=(10, self.timeout),
        )
        if not resp.ok:
            raise AdvisorError(
                f"推荐数据接口 {endpoint} 失败：HTTP {resp.status_code}"
            )

        try:
            payload = resp.json()
        except json.JSONDecodeError:
            raise AdvisorError(
                f"接口 {endpoint} 返回无法解析的内容，可能被风控拦截，请稍后重试。"
            )

        if payload.get("code") != 1:
            raise AdvisorError(
                f"接口 {endpoint} 返回 code={payload.get('code')} "
                f"({payload.get('msg', '')})，可能被风控拦截。"
            )
        return payload

    def _fetch_core(self) -> RecommendationSet:
        s = self._build_session()

        # ① 概览页：建会话，拿 PHPSESSID
        r = s.get(OVERVIEW_PAGE, timeout=(10, self.timeout))
        if not r.ok:
            raise AdvisorError(f"访问推荐站点失败：HTTP {r.status_code}")

        # ②③ 前置握手
        self._post_api(s, "getMenu", {"globalData": "false"})
        self._post_api(s, "checkUAStatus")

        # ④ 取数据
        data_resp = self._post_api(s, "getOVData", {"globalData": "false"})
        return self._parse(data_resp)

    # ---------- 解析 ----------

    def _parse(self, payload: dict) -> RecommendationSet:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise AdvisorError("推荐数据缺少 data 字段，站点结构可能已变化。")

        total = self._parse_group(data, "spData", "总利润")
        hourly = self._parse_group(data, "sphData", "每小时利润")
        return RecommendationSet(total, hourly)

    def _parse_group(self, data: dict, group_name: str, metric_name: str) \
            -> List[ProfitItem]:
        group = data.get(group_name)
        if not isinstance(group, dict):
            raise AdvisorError(
                f"推荐数据缺少 {group_name}({metric_name})，站点结构可能已变化。"
            )

        result = []
        for key, name in FACILITY_MAP:
            entry = group.get(key)
            if not isinstance(entry, dict):
                raise AdvisorError(
                    f"{metric_name}推荐缺少设施「{name}」({key})，拒绝按残缺数据继续。"
                )

            item_name = (entry.get("itemName") or "").strip()
            if not item_name:
                raise AdvisorError(
                    f"{metric_name}推荐中「{name}」缺少物品名。"
                )

            profit = entry.get("profit")
            if not isinstance(profit, (int, float)):
                raise AdvisorError(
                    f"{metric_name}推荐中「{name}」缺少数值 profit 字段。"
                )

            result.append(ProfitItem(key, name, item_name, float(profit)))
        return result


if __name__ == "__main__":
    advisor = ProfitAdvisor(timeout=60.0)
    try:
        recs = advisor.fetch()
        print("=== 总利润最高 ===")
        for it in recs.total_profit:
            print(f"{it.facility_name:6} | {it.item_name:20} | {it.profit:,.0f}")
        print("\n=== 每小时利润最高 ===")
        for it in recs.hourly_profit:
            print(f"{it.facility_name:6} | {it.item_name:20} | {it.profit:,.0f}")
    except AdvisorError as e:
        print("出错：", e)