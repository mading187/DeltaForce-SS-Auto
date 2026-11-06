# -*- coding: utf-8 -*-
"""
========================================================================
gui.py 接入 kkrb 利润榜 —— 最小侵入补丁
========================================================================

用法：把下面 4 个「插入点」按标记粘进你的 gui.py。
你原有的 _auto_item / _auto_all / _save / _load_fields 一律**不用改**，
本补丁只「新增方法 + 挂两个控件」。

如果某个插入点与你现有代码命名冲突（比如你已经有 _auto_item_from_ocr），
把新方法名改掉即可，逻辑照搬。

依赖：kkrb_adapter.py 与 test_get_kkru_message.py 放在同一目录
      （app.py 已把 BASE_DIR 加入 sys.path，无需额外处理）。
========================================================================
"""

# =====================================================================
# 【插入点 1 / 顶部 import 区】
#   位置：gui.py 现有 import 块末尾（from accounts import get_accounts 之后）
# =====================================================================
import threading
from tkinter import messagebox          # 若你已导入可省略
from kkrb_adapter import (              # ← 新增这一组
    fetch_hourly_map,
    fetch_total_map,
    fill_from_map,
    DEFAULT_FACILITY_ORDER,
    KkrAdapterError,
)


# =====================================================================
# 【插入点 2 / __init__ 里，self.item_vars 建完之后】
#   位置：for station in self.config["stations"]: ... 那个循环结束之后
# =====================================================================
#
#   # ---- kkrb 利润榜来源开关（新增开始）----
#   self._auto_source = tk.StringVar(value="ocr")
#   self._build_kkrb_source_row(items)   # items 是该区那个 LabelFrame
#   # ---- 新增结束 ----
#
#   说明：把 _build_kkrb_source_row 定义在下文【插入点 3】里。


# =====================================================================
# 【插入点 3 / 类体里，随便找个空处，比如 _path_row 方法之后】
#   新增的 4 个方法 + 1 个构建小控件
# =====================================================================

    def _build_kkrb_source_row(self, parent):
        """在「四工位目标物品」区顶部加一行：OCR / 利润榜 来源单选。"""
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 6))
        ttk.Label(row, text="自动获取来源：", foreground="#3a7").pack(side="left")
        ttk.Radiobutton(
            row, text="游戏画面 OCR", variable=self._auto_source, value="ocr",
        ).pack(side="left", padx=(4, 10))
        ttk.Radiobutton(
            row, text="kkrb 利润榜(每小时)", variable=self._auto_source, value="kkrb",
        ).pack(side="left")
        ttk.Radiobutton(
            row, text="kkrb 利润榜(总利润)", variable=self._auto_source, value="kkrb_total",
        ).pack(side="left", padx=(6, 0))


    def _auto_item(self, station: str) -> None:
        """
        ★ 覆盖你原来的 _auto_item ★

        原来你这里只有 OCR 一条路，现在按 self._auto_source 分发。
        若你不想覆盖原方法，把下面 OCR 分支改成调用 self._auto_item_from_ocr(station)。
        """
        src = getattr(self, "_auto_source", tk.StringVar(value="ocr")).get()
        if src == "ocr":
            self._auto_item_from_ocr(station)     # 你原来的逻辑搬到这里（见插入点 4）
        elif src == "kkrb_total":
            self._auto_item_from_kkrb(station, total=True)
        else:  # "kkrb"
            self._auto_item_from_kkrb(station, total=False)


    def _auto_item_from_kkrb(self, station: str, *, total: bool = False) -> None:
        """单工位：从利润榜填。后台线程抓，主线程回写，绝不堵 UI。"""
        var = self.item_vars.get(station)
        if var is None:
            return

        var.set("加载中…")
        self.status_var.set(f"正在从利润榜获取「{station}」…")

        def worker():
            try:
                mapping = (fetch_total_map() if total else fetch_hourly_map())
            except KkrAdapterError as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "利润榜获取失败",
                    f"无法从 kkrb.net 获取数据（{'可重试' if e.retryable else '站点结构变化'}）：\n{e}\n\n"
                    "可切回「游戏画面 OCR」手动获取，或稍后再试。",
                ))
                self.root.after(0, lambda: var.set(""))
                self.root.after(0, lambda: self.status_var.set("获取失败"))
                return

            def apply():
                item = mapping.get(station)
                if item:
                    var.set(item)
                    self.status_var.set(f"「{station}」→ {item}（未保存，请核对后点保存配置）")
                else:
                    messagebox.showwarning(
                        "设施名不匹配",
                        f"利润榜未返回「{station}」。\n可用键：{list(mapping)}",
                    )
                    var.set("")
                    self.status_var.set("设施名不匹配，已留空")

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()


    def _auto_all_from_kkrb(self, *, total: bool = False) -> None:
        """一键填充全部四工位（利润榜口径）。"""
        for station in self.config["stations"]:
            self.item_vars[station].set("加载中…")
        self.status_var.set("正在从利润榜获取全部工位…")

        def worker():
            try:
                mapping = (fetch_total_map() if total else fetch_hourly_map())
            except KkrAdapterError as e:
                self.root.after(0, lambda: messagebox.showerror("利润榜获取失败", str(e)))
                self.root.after(0, lambda: self.status_var.set("获取失败"))
                return

            def apply():
                missing = fill_from_map(mapping, self.item_vars, clear_missing=True)
                if missing:
                    messagebox.showwarning(
                        "部分工位未匹配",
                        f"利润榜无数据，已留空：{', '.join(missing)}",
                    )
                self.status_var.set(
                    "利润榜推荐已填入四工位，请核对后点「保存配置」才会生效"
                )

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()


# =====================================================================
# 【插入点 4 / 你原来的 OCR 逻辑，原样搬成这个方法】
# =====================================================================
#
#   把你现在 _auto_item 里的「截屏 → OCR → 填 self.item_vars[station]」那段
#   原封不动搬进下面这个方法，方法名与上面分发分支保持一致即可：
#
#     def _auto_item_from_ocr(self, station: str) -> None:
#         ...  你原来的代码，一个字不改 ...
#
#   同理，你原来「一键自动获取全部」的那个方法，建议改名成：
#
#     def _auto_all_from_ocr(self):
#         ...  你原来的代码 ...
#
#   然后在「一键自动获取全部」按钮的 command 里按来源分发：
#
#     ttk.Button(
#         items,
#         text="一键自动获取全部（路径 + 游戏 + 物品）",
#         command=self._auto_all,          # ← 新建这个分发方法
#     )
#
#     def _auto_all(self):
#         src = self._auto_source.get()
#         if src.startswith("kkrb"):
#             self._auto_all_from_kkrb(total=(src == "kkrb_total"))
#         else:
#             self._auto_all_from_ocr()    # 你原来的逻辑
#
# =====================================================================


# =====================================================================
# 【插入点 5 / _save 成功分支，追加 2 行日志（可选但强烈建议）】
#   位置：_save() 里 self._write_config(...) 或 json.dump 成功之后
# =====================================================================
#
#   names = {
#       it.get("station"): it.get("name")
#       for it in self.config.get("craft", {}).get("items", [])
#   }
#   self.logger(f"[保存] 四工位目标已更新：{names}")
#   self.status_var.set("配置已保存，下次执行将使用新物品")
#
#   说明：_save 原本就在读 self.item_vars 回写 craft.items，
#        所以利润榜填进来的物品名会「自动」落进 config.json，无需改回写逻辑。
#
# =====================================================================