#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
币安现货网格复盘工具 v0.2
输入：币安 App 导出的「交易机器人 - 交易历史」CSV
输出：终端对账摘要 + Markdown 复盘报告（report.md，可直接用于内容发布）

用法：python grid_review.py 账单.csv [--out report.md]
依赖：仅 Python 标准库。
"""

import csv
import re
import sys
from collections import Counter
from datetime import datetime


def pf(s):
    m = re.search(r"[+-]?\d+(?:\.\d+)?", str(s).replace(",", ""))
    return float(m.group()) if m else 0.0


def find_col(headers, *keywords):
    lowered = [h.lower() for h in headers]
    for i, h in enumerate(lowered):
        for kw in keywords:
            if kw.lower() in h:
                return i
    return None


def main():
    if len(sys.argv) < 2:
        print("用法：python grid_review.py 账单.csv [--out report.md]")
        return
    path = sys.argv[1]
    out = "report.md"
    since = ""
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]

    with open(path, encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        headers = next(reader)
        rows = [r for r in reader if r and any(c.strip() for c in r)]

    c_time = find_col(headers, "date", "time", "时间", "日期")
    c_pair = find_col(headers, "pair", "market", "symbol", "交易对", "市场")
    c_side = find_col(headers, "side", "type", "方向", "类型")
    c_price = find_col(headers, "price", "价格")
    c_qty = find_col(headers, "executed", "amount", "数量", "成交量", "已执行")
    c_total = find_col(headers, "total", "quote", "总额", "成交额", "金额")
    c_fee = find_col(headers, "fee", "手续费")

    if c_side is None:
        print("无法识别账单列，表头：", headers)
        return

    trades = []
    for r in rows:
        side = r[c_side].strip().upper()
        price = pf(r[c_price]) if c_price is not None else 0.0
        qty = pf(r[c_qty]) if c_qty is not None else 0.0
        total = pf(r[c_total]) if c_total is not None else qty * price
        fee_raw = r[c_fee].strip() if c_fee is not None else ""
        fee_amt = pf(fee_raw)
        # 手续费换算成 U：BTC 计价的按当时成交价折算
        fee_u = fee_amt * price if "BTC" in fee_raw.upper() else fee_amt
        trades.append({
            "time": r[c_time] if c_time is not None else "",
            "pair": r[c_pair] if c_pair is not None else "",
            "side": "BUY" if side.startswith("BUY") or side.startswith("买") else "SELL",
            "price": price, "qty": qty, "total": total, "fee_u": fee_u,
        })
    trades.sort(key=lambda t: t["time"])
    if since:
        trades = [t for t in trades if t["time"] >= since]
    if not trades:
        print("过滤后没有成交记录，请检查 --since 参数。")
        return
    # 交易对取出现最多的值；兼容币安导出截断（如 BTCU 实为 BTCUSDT）
    pair_name = Counter(t["pair"] for t in trades).most_common(1)[0][0]
    if pair_name == "BTCU":
        pair_name = "BTCUSDT"
    t0, t1 = trades[0]["time"], trades[-1]["time"]

    # 配对：每笔卖出匹配其之前、价格低于卖出价的未配对买入中价格最高者（网格就近格配对）
    unmatched = []
    pairs = []
    for t in trades:
        if t["side"] == "BUY":
            unmatched.append([t["price"], t["qty"]])
        else:
            cands = [(i, b) for i, b in enumerate(unmatched) if b[0] < t["price"]]
            if not cands:
                continue
            i, b = max(cands, key=lambda x: x[1][0])
            take = min(t["qty"], b[1])
            pairs.append({"buy": b[0], "sell": t["price"], "qty": take,
                          "profit": (t["price"] - b[0]) * take, "time": t["time"]})
            b[1] -= take
            if b[1] <= 1e-12:
                unmatched.pop(i)

    gross = sum(p["profit"] for p in pairs)
    fees = sum(t["fee_u"] for t in trades)
    net = gross - fees
    n_buy = sum(1 for t in trades if t["side"] == "BUY")
    n_sell = len(trades) - n_buy
    days = (datetime.strptime(t1[:10], "%Y-%m-%d") - datetime.strptime(t0[:10], "%Y-%m-%d")).days or 1
    per_day = Counter(p["time"][:10] for p in pairs)

    # ---------- 终端摘要 ----------
    print("\n========== 网格复盘 ==========")
    print(f"交易对：{pair_name}  |  {t0[:10]} ~ {t1[:10]}（{days} 天）")
    print(f"成交 {len(trades)} 笔（买 {n_buy} / 卖 {n_sell}），配对 {len(pairs)} 对")
    print(f"配对毛利润 +{gross:.2f}U，手续费约 -{fees:.2f}U，净配对利润 +{net:.2f}U")
    if pairs:
        print(f"平均每对 +{gross/len(pairs):.4f}U，配对频率 {len(pairs)/days:.1f} 对/天")
    print("==============================\n")

    # ---------- Markdown 报告 ----------
    lines = [
        f"# 网格实盘复盘（{t0[:10]} ~ {t1[:10]}）",
        "",
        f"- 交易对：{pair_name} ｜ 周期 {days} 天",
        f"- 成交 {len(trades)} 笔（买入 {n_buy} / 卖出 {n_sell}），配对 {len(pairs)} 对",
        f"- 配对毛利润 **+{gross:.2f}U**，手续费约 -{fees:.2f}U，**净配对利润 +{net:.2f}U**",
    ]
    if pairs:
        lines.append(f"- 平均每对 +{gross/len(pairs):.4f}U，配对频率 {len(pairs)/days:.1f} 对/天")
    lines += ["", "## 每日配对", ""]
    for d in sorted(per_day):
        lines.append(f"- {d}：{per_day[d]} 对")
    lines += ["", "## 最近 5 对", ""]
    for p in pairs[-5:]:
        lines.append(f"- {p['buy']:.0f} → {p['sell']:.0f}（{p['time'][:10]}），+{p['profit']:.4f}U")
    lines += ["", "_本报告由网格复盘工具自动生成，仅做记录，不构成投资建议。_", ""]

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"报告已生成：{out}")


if __name__ == "__main__":
    main()
