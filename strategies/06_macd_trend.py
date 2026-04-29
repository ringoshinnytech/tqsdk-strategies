#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD 趋势策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
MACD 趋势策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：DIF/DEA 金叉死叉，动能确认趋势方向
脚本默认关注 SHFE.cu2506，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略更适合方向持续的行情，在横盘震荡中容易反复进出，需要结合风控和周期过滤使用。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
06_macd_trend.py - MACD趋势跟踪策略（TargetPosTask版）

【策略背景与来源】
MACD（Moving Average Convergence Divergence）由 Gerald Appel 于1970年代末发明，
是技术分析领域最经典的趋势跟踪指标之一。通过计算两条不同周期EMA之差来衡量价格的
趋势方向与动能强弱，兼具趋势跟踪与动量测量的双重功能。

【核心逻辑】
  DIF = EMA(close, 12) - EMA(close, 26)   # 差离值：短期与长期EMA之差
  DEA = EMA(DIF, 9)                        # 信号线：对DIF再做EMA平滑
  金叉（DIF上穿DEA）→ 趋势转多，做多
  死叉（DIF下穿DEA）→ 趋势转空，做空

【为什么使用 TargetPosTask】
  TargetPosTask 自动处理追单、撤单、部分成交等所有下单细节。
  策略只需调用 set_target_volume(n)：正数=多头，负数=空头，0=平仓。
  比 insert_order 简洁得多，不需要跟踪订单状态。

【适用品种和周期】
  品种：原油（SC）、黄金（AU）、铜（CU）、股指（IF/IC/IM）等趋势性品种
  周期：60分钟或日线

【优缺点】
  优点：逻辑直观，趋势行情捕捉能力强，天然过滤小幅震荡
  缺点：滞后指标，震荡市假信号多，无内置止损

【参数说明】
  SYMBOL        : 交易合约代码
  FAST_PERIOD   : 快线EMA周期，默认12
  SLOW_PERIOD   : 慢线EMA周期，默认26
  SIGNAL_PERIOD : 信号线DEA周期，默认9
  VOLUME        : 持仓手数
  KLINE_DURATION: K线周期（秒）
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import ema, crossup, crossdown

# ===================== 策略参数 =====================
SYMBOL = "SHFE.cu2506"
FAST_PERIOD = 12
SLOW_PERIOD = 26
SIGNAL_PERIOD = 9
VOLUME = 1
KLINE_DURATION = 3600
DATA_LENGTH = 300
# ===================================================

def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)

    # TargetPosTask：声明目标仓位，自动追单直到达到目标
    target_pos = TargetPosTask(api, SYMBOL)

    print(f"[MACD策略] 启动 | {SYMBOL} | 快线:{FAST_PERIOD} 慢线:{SLOW_PERIOD} 信号:{SIGNAL_PERIOD}")

    try:
        while True:
            api.wait_update()
            if not api.is_changing(klines):
                continue

            close = klines["close"]

            # 计算 MACD 三线
            ema_fast = ema(close, FAST_PERIOD)
            ema_slow = ema(close, SLOW_PERIOD)
            dif = ema_fast - ema_slow          # DIF：差离值
            dea = ema(dif, SIGNAL_PERIOD)      # DEA：信号线
            macd_bar = (dif - dea) * 2         # MACD柱

            # 使用已完成K线（-2）判断金叉/死叉，避免用未完成K线产生假信号
            is_golden = bool(crossup(dif, dea).iloc[-2])    # DIF上穿DEA：金叉
            is_death  = bool(crossdown(dif, dea).iloc[-2])  # DIF下穿DEA：死叉

            print(f"DIF={dif.iloc[-2]:.4f} DEA={dea.iloc[-2]:.4f} BAR={macd_bar.iloc[-2]:.4f} | 金叉={is_golden} 死叉={is_death}")

            if is_golden:
                # 金叉 → 目标仓位设为多头 VOLUME 手
                # TargetPosTask 自动处理：先平空（若有）再开多
                print(f">>> 金叉！目标仓位 +{VOLUME}")
                target_pos.set_target_volume(VOLUME)

            elif is_death:
                # 死叉 → 目标仓位设为空头 VOLUME 手
                # TargetPosTask 自动处理：先平多（若有）再开空
                print(f">>> 死叉！目标仓位 -{VOLUME}")
                target_pos.set_target_volume(-VOLUME)

    except KeyboardInterrupt:
        print("[MACD策略] 用户中断")
    finally:
        api.close()

if __name__ == "__main__":
    main()
