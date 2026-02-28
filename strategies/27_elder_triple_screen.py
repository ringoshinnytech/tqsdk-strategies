#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elder 三屏交易系统 (Elder's Triple Screen Trading System)
=========================================================

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

【策略背景与来源】
三屏交易系统（Triple Screen Trading System）由美国著名交易心理学家和量化交易专家
Dr. Alexander Elder 于 1986 年提出，发表于《期货》杂志，后在其经典著作
《以交易为生》（Trading for a Living）和《再谈以交易为生》（Come Into My Trading Room）
中详细阐述。该系统在提出后迅速成为全球最广泛引用的多周期综合交易系统之一。

Elder 认为，大多数交易者失败的根本原因之一是"只用单一时间周期"看问题：
- 只看短周期：容易被噪音欺骗，追涨杀跌
- 只看长周期：错过入场时机，进场点差

三屏系统的天才之处在于：用三个"屏幕"（三个时间尺度）将趋势判断、
信号过滤、精确入场三个问题拆分开来，各司其职，协同决策。

【三屏原理详解】

  第一屏（趋势屏 / Trend Screen）—— 中长周期，确定大方向
  -------------------------------------------------------
  使用比实际交易周期高一个量级的时间框架（例如交易周期是小时线，则第一屏用日线）。
  Elder 原版使用"周线"作为第一屏，但对国内期货来说日线或小时线更实用。
  指标：MACD Histogram（柱状图） = DIF - DEA
  信号：
    - MACD Hist 向上（本根比上根大）→ 大趋势向上，只做多
    - MACD Hist 向下（本根比上根小）→ 大趋势向下，只做空
    - Elder 强调要看"柱状图的斜率"而非绝对值正负，因为斜率更能反映动量变化

  第二屏（信号屏 / Signal Screen）—— 中短周期，等待回调机会
  ----------------------------------------------------------
  使用实际交易周期（例如小时线）。
  指标：振荡类指标（Elder 推荐 Force Index / Stochastic）
  信号：
    - 大趋势向上时，等待振荡指标回调至超卖区（Stochastic %K < 30）
      → 顺势回调买入机会
    - 大趋势向下时，等待振荡指标反弹至超买区（Stochastic %K > 70）
      → 顺势反弹卖出机会
  本策略使用 Stochastic（随机指标）%K 替代 Force Index，更通用

  第三屏（入场屏 / Entry Screen）—— 最短周期，精确入场
  -------------------------------------------------------
  使用比交易周期低一个量级的时间框架（例如15分钟线）。
  Elder 原版使用"追踪止损单"（Buy Stop / Sell Stop）来入场：
    - 大趋势向上，第二屏回调确认后，在前一根15分钟K线的最高价挂 Buy Stop
    - 大趋势向下，第二屏超买确认后，在前一根15分钟K线的最低价挂 Sell Stop
  本策略简化为：第三屏检测到短周期小均线金叉/死叉时精确触发入场

【本策略实现方式（简化版三屏）】
  第一屏（日线）：MACD Histogram 斜率
    hist_rising  = MACD_hist[-2] > MACD_hist[-3]  → 大趋势向上
    hist_falling = MACD_hist[-2] < MACD_hist[-3]  → 大趋势向下

  第二屏（小时线）：Stochastic %K 超买超卖
    stoch_oversold  = %K[-2] < 30  → 超卖，大趋势向上时有回调买入机会
    stoch_overbought= %K[-2] > 70  → 超买，大趋势向下时有反弹卖出机会

  第三屏（15分钟线）：MA快线上穿/下穿慢线精确入场
    cross_up   = MA5 上穿 MA10  → 精确做多入场点
    cross_down = MA5 下穿 MA10  → 精确做空入场点

做多条件（三屏全部满足）：
  日线 MACD Hist 向上 AND 小时线 %K < 30 AND 15分钟 MA5上穿MA10
  → target_pos.set_target_volume(+VOLUME)

做空条件（三屏全部满足）：
  日线 MACD Hist 向下 AND 小时线 %K > 70 AND 15分钟 MA5下穿MA10
  → target_pos.set_target_volume(-VOLUME)

出场条件：
  大趋势反转（日线 MACD Hist 方向改变）→ 平仓离场

【Stochastic %K 计算公式】
  Stochastic %K = (Close - Lowest_Low_N) / (Highest_High_N - Lowest_Low_N) × 100
  参数：N = 9（Elder 推荐的快速随机指标默认参数）
  含义：收盘价在过去N根K线高低点区间内的百分位位置

【MACD Histogram 计算】
  EMA_fast = EMA(Close, 12)
  EMA_slow = EMA(Close, 26)
  DIF      = EMA_fast - EMA_slow
  DEA      = EMA(DIF, 9)
  MACD_hist= DIF - DEA
  斜率判断：hist[-2] vs hist[-3]（避免使用未收盘的最新bar）

【与 17_stochastic_rsi 的区别】
  - 17号策略是将随机算法应用在 RSI 上（StochRSI），是指标套指标
  - 27号策略（本策略）是 Elder 三屏系统的完整实现，核心是三周期协同判断
  - 27号策略的 Stochastic 应用在原始价格上（标准随机指标 %K/%D）
  - 最重要的区别：本策略强调三屏联动逻辑，而非单纯超买超卖反转

【适用品种和周期】
品种：趋势性强、流动性好的品种，如螺纹钢（RB）、黄金（AU）、铜（CU）、原油（SC）
交易周期：小时线（3600秒）为主周期，日线为第一屏，15分钟为第三屏

【优缺点分析】
优点：
  - 三屏联动过滤大量假信号，尤其在震荡市中效果显著
  - 大趋势 + 超买超卖回调 + 精确入场，形成完整的交易逻辑链
  - Elder 系统经过数十年实盘验证，全球应用广泛
  - 顺趋势操作，理论上盈亏比较高

缺点：
  - 三屏同时满足的条件较为苛刻，信号频率低（机会少）
  - 在单边强趋势市场，第二屏可能长期不出现超买超卖，错过大行情
  - 多周期K线同步订阅耗用更多API资源
  - 参数较多，每个屏幕都有独立参数，调优复杂

【参数说明】
  SYMBOL       : 交易合约代码
  MACD_FAST    : 日线 MACD 快线周期，默认 12
  MACD_SLOW    : 日线 MACD 慢线周期，默认 26
  MACD_SIGNAL  : 日线 MACD 信号线周期，默认 9
  STOCH_N      : 小时线随机指标窗口，默认 9
  STOCH_OB     : 随机指标超买线，默认 70
  STOCH_OS     : 随机指标超卖线，默认 30
  MA_FAST_N    : 15分钟快线周期，默认 5
  MA_SLOW_N    : 15分钟慢线周期，默认 10
  VOLUME       : 每次开仓手数
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import ema, ma, crossup, crossdown
import pandas as pd

# ===================== 策略参数 =====================
SYMBOL      = "SHFE.rb2510"    # 交易合约：螺纹钢2510
MACD_FAST   = 12               # 第一屏：日线 MACD 快线
MACD_SLOW   = 26               # 第一屏：日线 MACD 慢线
MACD_SIGNAL = 9                # 第一屏：日线 MACD 信号线
STOCH_N     = 9                # 第二屏：小时线随机指标窗口
STOCH_OB    = 70               # 第二屏：超买阈值
STOCH_OS    = 30               # 第二屏：超卖阈值
MA_FAST_N   = 5                # 第三屏：15分钟快线
MA_SLOW_N   = 10               # 第三屏：15分钟慢线
VOLUME      = 1                # 每次开仓手数
# ===================================================


def calc_macd_histogram(close: pd.Series, fast: int, slow: int, signal: int) -> pd.Series:
    """
    计算 MACD 柱状图（Histogram = DIF - DEA）
    Elder 三屏系统中，关注柱状图的斜率（连续两根的差值方向）
    """
    ema_fast = ema(close, fast)   # 快线 EMA
    ema_slow = ema(close, slow)   # 慢线 EMA
    dif      = ema_fast - ema_slow  # DIF 线
    dea      = ema(dif, signal)     # DEA 信号线
    hist     = dif - dea            # 柱状图
    return hist


def calc_stochastic_k(klines: pd.DataFrame, n: int) -> pd.Series:
    """
    计算随机指标 %K（Fast Stochastic Oscillator）
    %K = (Close - Lowest_Low_N) / (Highest_High_N - Lowest_Low_N) × 100
    """
    lowest_low   = klines["low"].rolling(n).min()
    highest_high = klines["high"].rolling(n).max()
    hl_range     = highest_high - lowest_low
    hl_range     = hl_range.replace(0, float("nan"))  # 避免除零
    k = 100 * (klines["close"] - lowest_low) / hl_range
    return k


def main():
    api = TqApi(
        account=TqSim(),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
    )

    # 第一屏：日线（MACD 斜率判断大趋势）
    # data_length 需覆盖 MACD_SLOW(26) + MACD_SIGNAL(9) 的计算需求，加冗余
    klines_day  = api.get_kline_serial(SYMBOL, 86400, data_length=MACD_SLOW + MACD_SIGNAL + 20)

    # 第二屏：小时线（Stochastic %K 判断超买超卖）
    klines_hour = api.get_kline_serial(SYMBOL, 3600, data_length=STOCH_N + 10)

    # 第三屏：15分钟线（快慢均线金叉死叉精确入场）
    klines_15m  = api.get_kline_serial(SYMBOL, 900, data_length=MA_SLOW_N + 10)

    # 初始化目标仓位任务
    target_pos = TargetPosTask(api, SYMBOL)

    print(
        f"[Elder三屏] 启动 | {SYMBOL} | "
        f"第一屏日线MACD({MACD_FAST},{MACD_SLOW},{MACD_SIGNAL}) | "
        f"第二屏小时Stoch({STOCH_N}) OB={STOCH_OB} OS={STOCH_OS} | "
        f"第三屏15mMA({MA_FAST_N},{MA_SLOW_N})"
    )

    while True:
        api.wait_update()

        # 三个周期任意一个有新K线时，重新判断
        if not (api.is_changing(klines_day) or
                api.is_changing(klines_hour) or
                api.is_changing(klines_15m)):
            continue

        # ========================
        # 第一屏：日线 MACD Histogram 斜率
        # ========================
        hist = calc_macd_histogram(klines_day["close"], MACD_FAST, MACD_SLOW, MACD_SIGNAL)
        # 用倒数第二、三根（已完成的bar），判断柱状图是否在上升或下降
        hist_curr = hist.iloc[-2]
        hist_prev = hist.iloc[-3]

        if pd.isna(hist_curr) or pd.isna(hist_prev):
            print("[Elder三屏] 日线数据不足，等待积累...")
            continue

        # MACD Hist 斜率：上升（向多），下降（向空）
        screen1_long  = hist_curr > hist_prev   # 柱状图在扩张（多方动能增强）
        screen1_short = hist_curr < hist_prev   # 柱状图在收缩（空方动能增强）

        # ========================
        # 第二屏：小时线 Stochastic %K
        # ========================
        stoch_k = calc_stochastic_k(klines_hour, STOCH_N)
        k_curr  = stoch_k.iloc[-2]  # 已完成的最新小时bar的 %K 值

        if pd.isna(k_curr):
            print("[Elder三屏] 小时线数据不足，等待积累...")
            continue

        # 超买超卖状态
        screen2_oversold   = k_curr < STOCH_OS   # 超卖（大趋势向上时等回调买入）
        screen2_overbought = k_curr > STOCH_OB   # 超买（大趋势向下时等反弹卖出）

        # ========================
        # 第三屏：15分钟均线金叉/死叉
        # ========================
        ma_fast_15m = ma(klines_15m["close"], MA_FAST_N)
        ma_slow_15m = ma(klines_15m["close"], MA_SLOW_N)

        if pd.isna(ma_fast_15m.iloc[-2]) or pd.isna(ma_slow_15m.iloc[-2]):
            print("[Elder三屏] 15分钟线数据不足，等待积累...")
            continue

        # 金叉/死叉（用倒数第二、三根判断穿越）
        cross_up_15m   = (ma_fast_15m.iloc[-3] <= ma_slow_15m.iloc[-3] and
                          ma_fast_15m.iloc[-2] >  ma_slow_15m.iloc[-2])   # 金叉
        cross_down_15m = (ma_fast_15m.iloc[-3] >= ma_slow_15m.iloc[-3] and
                          ma_fast_15m.iloc[-2] <  ma_slow_15m.iloc[-2])   # 死叉

        print(
            f"[Elder三屏] "
            f"第一屏 MACD_Hist={hist_curr:.4f}({'↑多' if screen1_long else '↓空' if screen1_short else '平'}) | "
            f"第二屏 %K={k_curr:.1f}({'超卖' if screen2_oversold else '超买' if screen2_overbought else '中性'}) | "
            f"第三屏 MA5={'金叉' if cross_up_15m else '死叉' if cross_down_15m else '-'}"
        )

        # ========================
        # 三屏联合信号判断
        # ========================

        # 做多：大趋势向上 + 小时超卖（回调到位）+ 15分钟金叉（精确入场）
        if screen1_long and screen2_oversold and cross_up_15m:
            print(">>> ✅ 三屏共振！大趋势↑ + 小时超卖回调 + 15分钟金叉 → 开多")
            target_pos.set_target_volume(VOLUME)

        # 做空：大趋势向下 + 小时超买（反弹到位）+ 15分钟死叉（精确入场）
        elif screen1_short and screen2_overbought and cross_down_15m:
            print(">>> ✅ 三屏共振！大趋势↓ + 小时超买反弹 + 15分钟死叉 → 开空")
            target_pos.set_target_volume(-VOLUME)

        # 平多：大趋势转空（日线MACD Hist 开始下行）→ 离场
        elif screen1_short and cross_down_15m:
            print(">>> 大趋势转空，平多离场")
            target_pos.set_target_volume(0)

        # 平空：大趋势转多（日线MACD Hist 开始上行）→ 离场
        elif screen1_long and cross_up_15m:
            print(">>> 大趋势转多，平空离场")
            target_pos.set_target_volume(0)

    api.close()


if __name__ == "__main__":
    main()
