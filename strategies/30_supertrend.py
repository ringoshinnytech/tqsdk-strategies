"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【关于 TqSdk —— 天勤量化开发包】

TqSdk 是由信易科技发起并开源的 Python 量化交易框架，专为国内期货市场设计，
是国内最主流的期货量化开发工具之一。

核心优势：
  ● 极简代码：几十行即可构建完整策略，内置 MA/MACD/BOLL/RSI/ATR 等近百个技术指标
  ● 全品种实时行情：期货、期权、股票，毫秒级推送，数据全在内存，零延迟
  ● 全流程支持：历史回测 → 模拟交易 → 实盘交易 → 运行监控，一套 API 全覆盖
  ● 广泛兼容：支持 90%+ 期货公司 CTP 直连及主流资管柜台
  ● Pandas 友好：K 线 / Tick 数据直接返回 DataFrame，与 NumPy 无缝配合

官方资源：
  📘 官方文档：https://doc.shinnytech.com/tqsdk/latest/
  🐙 GitHub  ：https://github.com/shinnytech/tqsdk-python
  🧑‍💻 账户注册：https://account.shinnytech.com/
  💬 用户社区：https://www.shinnytech.com/qa/

安装：pip install tqsdk -U
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

策略名称：SuperTrend 超级趋势指标策略
策略编号：30
作者：TqSdk 策略库
更新日期：2026-03-02

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【策略背景与原理】

SuperTrend（超级趋势指标）由 Olivier Seban 提出，是目前全球量化交易者中
最广泛使用的趋势跟踪指标之一。其核心逻辑简洁而强大：通过将真实波动幅度
（ATR，Average True Range）乘以一个倍数系数，以价格中轨（HL/2）为基准，
动态计算上下两条"趋势边界"。当价格收盘在上轨之上时，市场处于上升趋势；
反之，处于下降趋势。

SuperTrend 的最大优点是：
  1. 自适应波动率：ATR 会随市场波动自动扩缩带宽，减少假突破；
  2. 趋势明确：任意时刻市场非多即空，信号清晰无歧义；
  3. 止损内嵌：趋势线本身即为动态追踪止损线，无需额外设置止损逻辑；
  4. 参数少：仅需 ATR 周期（period）和倍数（multiplier）两个参数。

【计算公式】

  真实波动幅度（TR）：
    TR = max(high - low, |high - prev_close|, |low - prev_close|)

  平均真实波动幅度（ATR）：
    ATR(n) = 指数移动平均(TR, n)

  中轨（HL2）：
    HL2 = (high + low) / 2

  基础上轨（Basic Upper Band）：
    BUB = HL2 + multiplier × ATR

  基础下轨（Basic Lower Band）：
    BLB = HL2 - multiplier × ATR

  最终上轨（Final Upper Band）：若上一根K线的最终上轨 < 当前 BUB，
    或上一根K线收盘价 > 上一根K线最终上轨，则 FUB = BUB，否则 FUB = 上一根 FUB

  最终下轨（Final Lower Band）：若上一根K线的最终下轨 > 当前 BLB，
    或上一根K线收盘价 < 上一根K线最终下轨，则 FLB = BLB，否则 FLB = 上一根 FLB

  SuperTrend 值：
    若上一根SuperTrend == 上一根FUB：
      当前SuperTrend = FUB（若收盘 <= FUB），否则 = FLB
    若上一根SuperTrend == 上一根FLB：
      当前SuperTrend = FLB（若收盘 >= FLB），否则 = FUB

【交易信号】

  多头信号（买入开多）：SuperTrend 从上轨翻转为下轨（前一根为上轨压制状态，
    当前根转为下轨支撑状态），即趋势由空转多。

  空头信号（卖出开空）：SuperTrend 从下轨翻转为上轨，即趋势由多转空。

  持仓期间：动态止损线即为 SuperTrend 线，价格反向突破时平仓反手。

【参数说明】

  ATR_PERIOD  = 10   : ATR 计算周期，建议范围 7-14
  MULTIPLIER  = 3.0  : ATR 倍数，建议范围 2.0-4.0，值越大越不敏感
  SYMBOL      : 合约代码，默认螺纹钢主力合约
  KLINE_FREQ  : K 线周期，默认 15 分钟

【风险提示】

  1. SuperTrend 属于趋势跟踪策略，震荡行情中容易频繁被止损，需配合趋势判断；
  2. 参数敏感，强烈建议先做历史回测找到适合目标品种的参数组合；
  3. 资金管理：建议单笔风险不超过总资金的 2%，止损位即 SuperTrend 线价格。
"""

import numpy as np
from tqsdk import TqApi, TqAuth, TqSim, BacktestFinished
from tqsdk.tafunc import atr

# ─────────────────────────────────────────────
# 策略参数
# ─────────────────────────────────────────────
SYMBOL = "KQ.m@SHFE.rb"      # 螺纹钢主力合约（自动展期）
KLINE_FREQ = 60 * 15          # K 线周期：15 分钟 = 900 秒
ATR_PERIOD = 10               # ATR 计算周期
MULTIPLIER = 3.0              # ATR 倍数
LOT_SIZE = 1                  # 每次开仓手数


def compute_supertrend(df, period: int, multiplier: float):
    """
    在 DataFrame 上计算 SuperTrend 指标，返回含 supertrend 列的 df。

    参数:
        df        : TqSdk K 线 DataFrame，含 high / low / close 列
        period    : ATR 计算周期
        multiplier: ATR 倍数

    返回列：
        st_value  : SuperTrend 数值（即当前趋势线的价格水平）
        st_dir    : 趋势方向，1 = 多头（价格在下轨上方），-1 = 空头（价格在上轨下方）
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # 计算 ATR（使用 tqsdk 内置函数）
    atr_series = atr(df, period)

    hl2 = (high + low) / 2.0

    # 基础上下轨
    bub = hl2 + multiplier * atr_series
    blb = hl2 - multiplier * atr_series

    n = len(df)
    fub = np.full(n, np.nan)   # 最终上轨
    flb = np.full(n, np.nan)   # 最终下轨
    st_value = np.full(n, np.nan)   # SuperTrend 值
    st_dir = np.zeros(n, dtype=int)  # 趋势方向

    # 初始化
    fub[0] = bub.iloc[0]
    flb[0] = blb.iloc[0]
    st_value[0] = fub[0]
    st_dir[0] = -1  # 初始假设空头

    for i in range(1, n):
        # 更新最终上轨
        if bub.iloc[i] < fub[i - 1] or close.iloc[i - 1] > fub[i - 1]:
            fub[i] = bub.iloc[i]
        else:
            fub[i] = fub[i - 1]

        # 更新最终下轨
        if blb.iloc[i] > flb[i - 1] or close.iloc[i - 1] < flb[i - 1]:
            flb[i] = blb.iloc[i]
        else:
            flb[i] = flb[i - 1]

        # 确定当前 SuperTrend 值与方向
        if st_dir[i - 1] == -1:
            # 前一根处于空头（SuperTrend == 上轨）
            if close.iloc[i] > fub[i]:
                # 价格突破上轨 → 趋势翻多
                st_value[i] = flb[i]
                st_dir[i] = 1
            else:
                st_value[i] = fub[i]
                st_dir[i] = -1
        else:
            # 前一根处于多头（SuperTrend == 下轨）
            if close.iloc[i] < flb[i]:
                # 价格跌破下轨 → 趋势翻空
                st_value[i] = fub[i]
                st_dir[i] = -1
            else:
                st_value[i] = flb[i]
                st_dir[i] = 1

    df = df.copy()
    df["st_value"] = st_value
    df["st_dir"] = st_dir
    return df


def main():
    # ─────────────────────────────────────────
    # 初始化 TqApi（回测模式，使用模拟账户）
    # ─────────────────────────────────────────
    api = TqApi(
        account=TqSim(init_balance=200000),
        auth=TqAuth("your_username", "your_password"),  # 请替换为实际账号
        backtest=...,   # 如需回测，传入 TqBacktest 对象；实盘删除此参数
    )

    # 订阅 K 线（需要 period+2 根以上才能计算指标，多订阅几根缓冲）
    klines = api.get_kline_serial(SYMBOL, KLINE_FREQ, data_length=ATR_PERIOD + 50)
    quote = api.get_quote(SYMBOL)
    account = api.get_account()
    position = api.get_position(SYMBOL)

    print(f"[SuperTrend] 启动策略：{SYMBOL} | ATR周期={ATR_PERIOD} | 倍数={MULTIPLIER}")

    prev_dir = 0   # 上一根 K 线的趋势方向（0=未知）

    try:
        while True:
            api.wait_update()

            # 每次 K 线完成一根时触发
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue

            # 数据量不足时跳过
            if len(klines) < ATR_PERIOD + 5:
                continue

            # 计算 SuperTrend（取最近 ATR_PERIOD*3 根 K 线避免过长计算）
            recent = klines.copy()
            recent = compute_supertrend(recent, ATR_PERIOD, MULTIPLIER)

            # 取倒数第 2 根（已完成）的方向，避免用未完成 K 线信号
            cur_dir = int(recent["st_dir"].iloc[-2])
            cur_st = float(recent["st_value"].iloc[-2])

            long_pos = position.pos_long_today + position.pos_long
            short_pos = position.pos_short_today + position.pos_short

            # ─────────────────────────────────────────
            # 交易逻辑
            # ─────────────────────────────────────────
            if prev_dir != 0 and cur_dir != prev_dir:
                # 方向发生翻转
                if cur_dir == 1:
                    # 趋势翻多：平空开多
                    if short_pos > 0:
                        api.insert_order(
                            symbol=SYMBOL,
                            direction="BUY",
                            offset="CLOSE",
                            volume=short_pos,
                            limit_price=quote.ask_price1,
                        )
                        print(f"[SuperTrend] 平空 {short_pos} 手 @ {quote.ask_price1:.2f}")
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="OPEN",
                        volume=LOT_SIZE,
                        limit_price=quote.ask_price1,
                    )
                    print(f"[SuperTrend] 开多 {LOT_SIZE} 手 @ {quote.ask_price1:.2f} | ST={cur_st:.2f}")

                elif cur_dir == -1:
                    # 趋势翻空：平多开空
                    if long_pos > 0:
                        api.insert_order(
                            symbol=SYMBOL,
                            direction="SELL",
                            offset="CLOSE",
                            volume=long_pos,
                            limit_price=quote.bid_price1,
                        )
                        print(f"[SuperTrend] 平多 {long_pos} 手 @ {quote.bid_price1:.2f}")
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="OPEN",
                        volume=LOT_SIZE,
                        limit_price=quote.bid_price1,
                    )
                    print(f"[SuperTrend] 开空 {LOT_SIZE} 手 @ {quote.bid_price1:.2f} | ST={cur_st:.2f}")

            # 更新上一根方向
            prev_dir = cur_dir

    except BacktestFinished:
        stat = account
        print("\n════════════════════════════════════")
        print(f"[SuperTrend] 回测结束")
        print(f"  最终权益：{stat.balance:.2f}")
        print(f"  最大回撤：{stat.max_drawdown:.2f}%")
        print("════════════════════════════════════")
    finally:
        api.close()


if __name__ == "__main__":
    main()
