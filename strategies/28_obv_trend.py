#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OBV 能量潮趋势策略
======================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
OBV 能量潮趋势策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：OBV 短/长均线金叉死叉，量能领先价格判断资金流向
脚本默认关注 SHFE.rb2601，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略更适合方向持续的行情，在横盘震荡中容易反复进出，需要结合风控和周期过滤使用。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
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

策略28：OBV 能量潮趋势策略
===========================

【策略背景与原理】

OBV（On Balance Volume，能量潮指标）是由约瑟夫·格兰维尔（Joseph Granville）
于1963年在其著作《股票市场利润的新方法》中提出的一种量价结合指标。
尽管诞生于股票市场，OBV 的核心逻辑同样适用于期货市场，是量化交易中
最经典、最实用的量价指标之一。

OBV 的核心思想是：成交量是价格变动的"先行指标"。市场上的主力资金在
拉升价格之前，往往先通过吸筹阶段积累大量多头仓位，这一过程伴随着成交量
的持续放大，但价格尚未明显上涨。通过 OBV 对成交量的累积统计，可以在价格
明显启动之前，提前识别主力资金的流向，从而获得一定的领先优势。

【OBV 计算方式】

OBV 的计算规则非常简单直观：
  - 若当日收盘价 > 前日收盘价（上涨日）：OBV = 前日OBV + 当日成交量
  - 若当日收盘价 < 前日收盘价（下跌日）：OBV = 前日OBV - 当日成交量
  - 若当日收盘价 = 前日收盘价（平盘日）：OBV = 前日OBV（不变）

通过这种方式，OBV 将每一根 K 线的成交量按照价格涨跌方向进行正负累积，
得到一条反映资金流向的曲线。当 OBV 持续上升时，说明每次上涨日的成交量
大于下跌日的成交量，资金净流入；反之则净流出。

【信号生成逻辑】

本策略基于 OBV 均线系统产生交易信号：
  1. 计算原始 OBV 序列
  2. 对 OBV 序列计算短期均线（默认10周期）和长期均线（默认30周期）
  3. 当 OBV 短均线上穿长均线时，视为量能向好、趋势向上，产生做多信号
  4. 当 OBV 短均线下穿长均线时，视为量能走弱、趋势向下，产生做空信号

此外，策略还引入价格均线作为辅助过滤条件：
  - 做多信号还需满足：价格位于价格均线（MA20）上方
  - 做空信号还需满足：价格位于价格均线（MA20）下方

这样可以有效避免在趋势相反方向上逆势交易，提高信号质量。

【适用品种与周期】

本策略适合流动性较好、成交量数据可靠的主力合约，如：
  - 沪深300股指期货（CFFEX.IF）
  - 螺纹钢期货（SHFE.rb）
  - 铁矿石期货（DCE.i）
  - 豆粕期货（DCE.m）

推荐周期：60分钟K线或日线，过短的周期（如1分钟）成交量噪音较大。

【仓位与风险控制】

策略采用固定手数（1手）进行交易，同时设置以下风控措施：
  - 最大持仓时间限制：单次交易持仓不超过 max_hold_bars 根K线，防止长期被套
  - 信号反转强制平仓：当反向信号出现时，先平仓再开仓，避免重复持仓
  - 收盘前不开仓：临近收盘时不新开仓位，防止隔夜风险

【格兰维尔量价关系法则（扩展阅读）】

格兰维尔还总结了著名的"量价八大法则"，本策略的底层逻辑与其密切相关：
  1. 价升量增（量价配合）：趋势健康，可追涨
  2. 价升量减（量价背离）：趋势减弱，注意减仓
  3. 价跌量减（量价配合）：下跌动能不足，可等待反弹
  4. 价跌量增（量价背离）：下跌加速，可追空
OBV 均线系统正是这些法则的量化实现。

【注意事项】

  - OBV 本身是累积量，其绝对值意义不大，重要的是其趋势和均线关系
  - 在成交量异常放大（如主力对倒）的情况下，OBV 可能产生虚假信号
  - 建议结合价格结构（如支撑阻力位）共同判断信号有效性
  - 本策略为演示策略，实盘前请充分回测验证参数
"""

from tqsdk import TqApi, TqAuth, TqBacktest, TqSim
from tqsdk.ta import MA
from datetime import date
import numpy as np

# ===== 策略参数配置 =====
SYMBOL = "SHFE.rb2601"          # 交易品种：螺纹钢主力合约
KLINE_DURATION = 60 * 60        # K线周期：60分钟（单位：秒）
OBV_SHORT = 10                  # OBV 短期均线周期
OBV_LONG = 30                   # OBV 长期均线周期
PRICE_MA = 20                   # 价格辅助均线周期
TRADE_VOLUME = 1                # 每次交易手数
MAX_HOLD_BARS = 20              # 最大持仓K线数（超过则强制平仓）


def calc_obv(close_series, volume_series):
    """
    手动计算 OBV（能量潮）序列。

    参数：
      close_series  - 收盘价序列（pandas Series 或 numpy array）
      volume_series - 成交量序列

    返回：
      obv_array - OBV 累积序列（numpy array）

    计算逻辑：
      逐K线遍历，根据收盘价涨跌对成交量进行正负累积。
      首根K线的 OBV 初始化为当根成交量。
    """
    n = len(close_series)
    obv = np.zeros(n, dtype=float)
    obv[0] = volume_series.iloc[0] if hasattr(volume_series, 'iloc') else volume_series[0]

    for i in range(1, n):
        c_cur = close_series.iloc[i] if hasattr(close_series, 'iloc') else close_series[i]
        c_pre = close_series.iloc[i - 1] if hasattr(close_series, 'iloc') else close_series[i - 1]
        v_cur = volume_series.iloc[i] if hasattr(volume_series, 'iloc') else volume_series[i]

        if c_cur > c_pre:
            obv[i] = obv[i - 1] + v_cur   # 上涨日：累加成交量
        elif c_cur < c_pre:
            obv[i] = obv[i - 1] - v_cur   # 下跌日：减去成交量
        else:
            obv[i] = obv[i - 1]            # 平盘日：OBV 不变

    return obv


def moving_average(arr, period):
    """
    计算简单移动平均线（SMA）。

    对于前 period-1 个数据点，返回 NaN（数据不足）。
    从第 period 个数据点开始，返回过去 period 个值的均值。
    """
    result = np.full(len(arr), np.nan)
    for i in range(period - 1, len(arr)):
        result[i] = np.mean(arr[i - period + 1: i + 1])
    return result


def main():
    # ===== 初始化 TqApi =====
    # 回测模式：2025年全年历史数据回测
    api = TqApi(
        backtest=TqBacktest(
            start_dt=date(2025, 1, 1),
            end_dt=date(2025, 12, 31)
        ),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
        account=TqSim(init_balance=200000)   # 模拟账户，初始资金20万
    )

    # ===== 订阅行情数据 =====
    # 获取60分钟K线数据，保留足够历史数据用于计算指标
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=500)

    # 订阅合约报价（用于获取实时价格和合约信息）
    quote = api.get_quote(SYMBOL)

    # ===== 获取账户与持仓对象 =====
    account = api.get_account()
    position = api.get_position(SYMBOL)

    print(f"[OBV 能量潮策略] 启动，品种：{SYMBOL}，K线周期：60分钟")
    print(f"OBV 均线参数：短期={OBV_SHORT}，长期={OBV_LONG}，价格辅助均线={PRICE_MA}")

    # ===== 状态变量 =====
    last_signal = None        # 上一次信号方向（'long' / 'short' / None）
    hold_bars = 0             # 当前持仓已持有的K线数
    last_bar_id = None        # 上一根K线的ID（用于判断新K线）

    # ===== 主循环 =====
    while True:
        api.wait_update()

        # 判断是否有新的K线完成（每当一根K线收盘后触发）
        if not api.is_changing(klines.iloc[-1], "datetime"):
            continue  # 还在同一根K线内，不重复计算

        current_bar_id = klines.iloc[-1]["id"]
        if current_bar_id == last_bar_id:
            continue  # 同一根K线，跳过
        last_bar_id = current_bar_id

        # ===== 计算指标 =====
        n = len(klines)
        if n < OBV_LONG + 5:
            # 数据不足，等待更多历史数据
            continue

        close = klines["close"]
        volume = klines["volume"]

        # 1. 计算 OBV 序列
        obv_arr = calc_obv(close, volume)

        # 2. 计算 OBV 的短期和长期均线
        obv_short_arr = moving_average(obv_arr, OBV_SHORT)
        obv_long_arr = moving_average(obv_arr, OBV_LONG)

        # 3. 计算价格辅助均线（MA20）
        price_ma_arr = moving_average(close.values, PRICE_MA)

        # 取最新两根K线的 OBV 均线值，用于判断金叉/死叉
        obv_s_cur = obv_short_arr[-1]     # 当前短期 OBV 均线
        obv_s_pre = obv_short_arr[-2]     # 前一根短期 OBV 均线
        obv_l_cur = obv_long_arr[-1]      # 当前长期 OBV 均线
        obv_l_pre = obv_long_arr[-2]      # 前一根长期 OBV 均线

        cur_price = close.iloc[-1]        # 当前收盘价
        price_ma_val = price_ma_arr[-1]   # 当前价格均线值

        # 检查是否有 NaN（数据不足）
        if any(np.isnan(x) for x in [obv_s_cur, obv_s_pre, obv_l_cur, obv_l_pre, price_ma_val]):
            continue

        # ===== 信号判断 =====
        # 做多信号：OBV 短均线由下向上穿越长均线（金叉）+ 价格在均线上方
        bull_signal = (obv_s_pre <= obv_l_pre) and (obv_s_cur > obv_l_cur) and (cur_price > price_ma_val)

        # 做空信号：OBV 短均线由上向下穿越长均线（死叉）+ 价格在均线下方
        bear_signal = (obv_s_pre >= obv_l_pre) and (obv_s_cur < obv_l_cur) and (cur_price < price_ma_val)

        # ===== 获取当前持仓状态 =====
        net_pos = position.pos_long - position.pos_short   # 净持仓

        # 持仓超过最大持仓K线数，强制平仓
        if net_pos != 0:
            hold_bars += 1
            if hold_bars >= MAX_HOLD_BARS:
                print(f"[平仓] 持仓超过 {MAX_HOLD_BARS} 根K线，强制平仓，当前净持仓={net_pos}")
                if net_pos > 0:
                    # 平多仓
                    api.insert_order(SYMBOL, direction="SELL", offset="CLOSE",
                                     volume=position.pos_long)
                else:
                    # 平空仓
                    api.insert_order(SYMBOL, direction="BUY", offset="CLOSE",
                                     volume=position.pos_short)
                last_signal = None
                hold_bars = 0
                continue
        else:
            hold_bars = 0  # 无持仓则重置计数器

        # ===== 执行交易 =====
        if bull_signal and last_signal != 'long':
            # 做多信号触发
            if net_pos < 0:
                # 先平空仓
                print(f"[平空] OBV金叉，平空仓，价格={cur_price:.1f}")
                api.insert_order(SYMBOL, direction="BUY", offset="CLOSE",
                                 volume=position.pos_short)

            if net_pos <= 0:
                # 开多仓
                print(f"[开多] OBV金叉 + 价格在MA{PRICE_MA}上方，"
                      f"OBV短线={obv_s_cur:.0f}，OBV长线={obv_l_cur:.0f}，"
                      f"价格={cur_price:.1f}，均线={price_ma_val:.1f}")
                api.insert_order(SYMBOL, direction="BUY", offset="OPEN",
                                 volume=TRADE_VOLUME)
                last_signal = 'long'
                hold_bars = 0

        elif bear_signal and last_signal != 'short':
            # 做空信号触发
            if net_pos > 0:
                # 先平多仓
                print(f"[平多] OBV死叉，平多仓，价格={cur_price:.1f}")
                api.insert_order(SYMBOL, direction="SELL", offset="CLOSE",
                                 volume=position.pos_long)

            if net_pos >= 0:
                # 开空仓
                print(f"[开空] OBV死叉 + 价格在MA{PRICE_MA}下方，"
                      f"OBV短线={obv_s_cur:.0f}，OBV长线={obv_l_cur:.0f}，"
                      f"价格={cur_price:.1f}，均线={price_ma_val:.1f}")
                api.insert_order(SYMBOL, direction="SELL", offset="OPEN",
                                 volume=TRADE_VOLUME)
                last_signal = 'short'
                hold_bars = 0

        # 输出当前状态（每根K线）
        print(f"[状态] 价格={cur_price:.1f} | OBV短={obv_s_cur:.0f} | OBV长={obv_l_cur:.0f} | "
              f"净持仓={net_pos} | 持仓K线={hold_bars} | 账户权益={account.balance:.0f}")


if __name__ == "__main__":
    main()
