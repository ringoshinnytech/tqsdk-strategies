"""
================================================================================
策略24：R-Breaker日内策略（R-Breaker Intraday Strategy）
================================================================================

【策略背景与来源】
R-Breaker是由Richard Saidenberg于20世纪90年代开发的经典日内期货交易策略，
并在Futures Magazine中发表，一经推出即受到职业日内交易员的广泛青睐。R-Breaker
曾连续多年被评为最赚钱的日内技术策略之一（参考Futures杂志评选），在全球期货
市场广泛应用，尤其在股指期货和商品期货日内交易领域表现突出。

R-Breaker的核心思想是：基于前一日的高、低、收价格，计算出6条关键价格线，
将当日价格空间分为不同的操作区域。当价格突破"突破线"时顺势追单，当价格达到
"反转线"附近且出现反转信号时逆势做单。这种双重机制（趋势突破 + 日内反转）
使R-Breaker能适应不同的市场环境。

根据国内期货市场实证研究，R-Breaker在股指期货（IF/IC/IM）的5分钟级别上
有较好的历史表现，是目前国内使用最广泛的日内量化策略框架之一。

【核心逻辑】
基于昨日高（H）、低（L）、收（C）计算6条价格线：

  枢轴点：  Pivot = (H + L + C) / 3

  突破买入线：BBreak = H + 2 × (Pivot - L)      ← 价格上穿做多
  观察卖出线：SSetup = Pivot + (H - L)           ← 接近此线注意反转做空
  反转卖出线：SEnter = 2 × Pivot - L             ← 价格冲高回落时做空

  突破卖出线：SBreak = L - 2 × (H - Pivot)      ← 价格下穿做空
  观察买入线：BSetup = Pivot - (H - L)           ← 接近此线注意反转做多
  反转买入线：BEnter = 2 × Pivot - H             ← 价格回落反弹时做多

价格线从高到低排列：
  BBreak > SSetup > SEnter > Pivot > BEnter > BSetup > SBreak

【交易信号说明】
突破信号（趋势跟随）：
  开多：当日价格上穿BBreak → set_target_volume(VOLUME)
  开空：当日价格下穿SBreak → set_target_volume(-VOLUME)

反转信号（逆势反转，仅在触及观察线后有效）：
  空转多（反转买入）：
    条件1：当日价格曾经到过SSetup以上（即曾触及观察卖出线）
    条件2：当前价格 < SEnter（价格从高位回落到反转卖出线以下）
    → set_target_volume(-VOLUME)（反转做空）

  多转空（反转卖出）：
    条件1：当日价格曾经到过BSetup以下（即曾触及观察买入线）
    条件2：当前价格 > BEnter（价格从低位反弹到反转买入线以上）
    → set_target_volume(VOLUME)（反转做多）

平仓规则：
  当日收盘前强制平仓 → set_target_volume(0)

【为何使用 TargetPosTask】
本策略使用 TargetPosTask 替代直接调用 insert_order，原因如下：
- TargetPosTask 内部自动处理追单、撤单、部分成交等复杂场景，无需手动管理订单状态
- 只需指定目标持仓量（正数=多仓，负数=空仓，0=平仓），框架自动计算需要的净操作
- 避免了先平后开的繁琐逻辑（日内多档位方向切换时尤为关键），代码更简洁、更健壮
- 在网络延迟或行情快速变化时，TargetPosTask 能正确处理未成交订单的撤单重发
- 收盘强制平仓直接调用 set_target_volume(0) 即可，无需区分当前方向

【适用品种和周期】
适用品种：流动性好的期货主力合约，尤其适合股指期货IF/IC/IM、螺纹钢RB
适用周期：分钟K线，以5分钟为主（日内交易）
最佳场景：价格围绕枢轴点震荡，有日内规律性反转特征的行情

【优缺点分析】
优点：
  1. 经典策略，有大量实盘验证，在多个市场历经检验
  2. 同时具备趋势追踪（突破）和均值回归（反转）两种逻辑
  3. 计算简单，每日仅需三个参数即可确定所有价格线
  4. 日内策略，不承担隔夜风险
  5. 有明确的价格线参考，止损逻辑清晰

缺点：
  1. 依赖前一日价格水平，开盘跳空会影响策略效果
  2. 在单边大趋势日，反转信号会产生大亏损
  3. 参数（Pivot计算方式）固定，缺乏自适应性
  4. 国内股指期货引入做市商机制后，该策略效果有所减弱

【参数说明】
SYMBOL         : 交易品种，默认股指期货 CFFEX.IF2406
DAY_DURATION   : 日线K线周期，86400秒=1天
TRADE_DURATION : 交易K线周期（秒），默认300秒（5分钟）
VOLUME         : 每次下单手数，默认1手
CLOSE_TIME     : 日内强制平仓时间（小时，24小时制），默认14:55
DATA_LENGTH    : 日线K线数量，建议 > 5
TRADE_LENGTH   : 分钟K线数量，建议 > 100
================================================================================
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from datetime import datetime

# ==================== 策略参数配置 ====================
SYMBOL         = "CFFEX.IF2406"  # 交易品种：沪深300股指期货主力
DAY_DURATION   = 86400            # 日线K线：1天（秒）
TRADE_DURATION = 5 * 60           # 交易K线：5分钟（秒）
VOLUME         = 1                # 每次交易手数
CLOSE_HOUR     = 14               # 强制平仓小时（14点55分平仓）
CLOSE_MINUTE   = 55               # 强制平仓分钟
DATA_LENGTH    = 10               # 日线K线数量（取最新2根即可）
TRADE_LENGTH   = 300              # 分钟K线数量


def calc_rbreaker_levels(prev_high, prev_low, prev_close):
    """
    根据昨日高低收计算R-Breaker的6条价格线
    
    参数：
        prev_high:  昨日最高价
        prev_low:   昨日最低价
        prev_close: 昨日收盘价
    
    返回：
        dict: 包含6条价格线的字典
    """
    pivot = (prev_high + prev_low + prev_close) / 3.0  # 枢轴点

    # 突破做多线（最高，突破此线顺势做多）
    bbreak  = prev_high + 2 * (pivot - prev_low)
    # 观察做空线（观察：价格曾涨到这里，后续可能反转做空）
    ssetup  = pivot + (prev_high - prev_low)
    # 反转做空线（价格从SSetup回落到此线以下时，做空信号）
    senter  = 2 * pivot - prev_low

    # 反转做多线（价格从BSetup反弹到此线以上时，做多信号）
    benter  = 2 * pivot - prev_high
    # 观察做多线（观察：价格曾跌到这里，后续可能反转做多）
    bsetup  = pivot - (prev_high - prev_low)
    # 突破做空线（最低，突破此线顺势做空）
    sbreak  = prev_low - 2 * (prev_high - pivot)

    return {
        "pivot":  pivot,
        "bbreak": bbreak,   # 突破买入线（最高）
        "ssetup": ssetup,   # 观察卖出线
        "senter": senter,   # 反转卖出线
        "benter": benter,   # 反转买入线
        "bsetup": bsetup,   # 观察买入线
        "sbreak": sbreak,   # 突破卖出线（最低）
    }


def main():
    # 初始化API，使用模拟账户
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    print(f"[R-Breaker策略] 启动，品种={SYMBOL}, 强制平仓时间={CLOSE_HOUR}:{CLOSE_MINUTE:02d}")

    # 获取日线K线（用于计算价格线）
    day_klines   = api.get_kline_serial(SYMBOL, DAY_DURATION, data_length=DATA_LENGTH)

    # 获取分钟K线（用于日内交易）
    trade_klines = api.get_kline_serial(SYMBOL, TRADE_DURATION, data_length=TRADE_LENGTH)

    account  = api.get_account()

    # 初始化 TargetPosTask，自动管理持仓目标（自动处理追单/撤单/部分成交）
    target_pos = TargetPosTask(api, SYMBOL)

    # 当日R-Breaker价格线（初始为None）
    levels = None

    # 日内状态跟踪（每日重置）
    has_touched_ssetup = False   # 当日是否曾经触达SSetup（观察卖出线）
    has_touched_bsetup = False   # 当日是否曾经触达BSetup（观察买入线）
    today_date         = None    # 当前日期（用于检测日期切换）

    try:
        while True:
            api.wait_update()

            # ====== 当日线K线更新时，重新计算R-Breaker价格线 ======
            if api.is_changing(day_klines.iloc[-1], "datetime"):
                # 用昨日（已完成的）日线数据计算价格线
                prev = day_klines.iloc[-2]
                levels = calc_rbreaker_levels(
                    prev["high"],
                    prev["low"],
                    prev["close"]
                )
                # 新的一天，重置日内状态
                has_touched_ssetup = False
                has_touched_bsetup = False
                print(f"\n[日线更新] R-Breaker价格线：")
                print(f"  BBreak={levels['bbreak']:.2f} | SSetup={levels['ssetup']:.2f} | "
                      f"SEnter={levels['senter']:.2f}")
                print(f"  Pivot={levels['pivot']:.2f}")
                print(f"  BEnter={levels['benter']:.2f} | BSetup={levels['bsetup']:.2f} | "
                      f"SBreak={levels['sbreak']:.2f}")

            # ====== 在分钟K线更新时执行交易逻辑 ======
            if api.is_changing(trade_klines.iloc[-1], "datetime") and levels is not None:

                curr_close = trade_klines["close"].iloc[-1]   # 当前收盘价
                curr_high  = trade_klines["high"].iloc[-1]    # 当前最高价
                curr_low   = trade_klines["low"].iloc[-1]     # 当前最低价
                prev_close = trade_klines["close"].iloc[-2]   # 上一根收盘价

                # ====== 获取当前时间（用于判断是否到平仓时间） ======
                # tqsdk的K线时间戳为纳秒，转换为秒
                ts_ns    = trade_klines.iloc[-1]["datetime"]
                dt_now   = pd.Timestamp(ts_ns)                   # 转换为Timestamp
                hour_now = dt_now.hour
                min_now  = dt_now.minute

                # ====== 强制平仓：临近收盘（日内策略不过夜） ======
                if (hour_now > CLOSE_HOUR or
                    (hour_now == CLOSE_HOUR and min_now >= CLOSE_MINUTE)):
                    # 直接设目标仓位为0，TargetPosTask 自动平掉所有持仓
                    target_pos.set_target_volume(0)
                    print(f"  → 收盘强制平仓（{hour_now}:{min_now:02d}）")
                    continue  # 强制平仓后不再执行其他逻辑

                # ====== 更新日内状态：检测是否触达观察线 ======
                # 当日最高价是否曾达到SSetup（观察卖出线）
                if curr_high >= levels["ssetup"]:
                    has_touched_ssetup = True

                # 当日最低价是否曾达到BSetup（观察买入线）
                if curr_low <= levels["bsetup"]:
                    has_touched_bsetup = True

                print(f"[{dt_now.strftime('%H:%M')}] Close={curr_close:.2f} | "
                      f"触SSetup={has_touched_ssetup}, 触BSetup={has_touched_bsetup}")

                # ====== 交易逻辑 ======

                # --- 突破做多：价格上穿BBreak ---
                if curr_close > levels["bbreak"] and prev_close <= levels["bbreak"]:
                    target_pos.set_target_volume(VOLUME)
                    print(f"  → 突破做多 {VOLUME}手（上穿BBreak={levels['bbreak']:.2f}）")

                # --- 突破做空：价格下穿SBreak ---
                elif curr_close < levels["sbreak"] and prev_close >= levels["sbreak"]:
                    target_pos.set_target_volume(-VOLUME)
                    print(f"  → 突破做空 {VOLUME}手（下穿SBreak={levels['sbreak']:.2f}）")

                # --- 反转做空：曾触及SSetup，且价格回落到SEnter以下 ---
                elif (has_touched_ssetup
                      and curr_close < levels["senter"]
                      and prev_close >= levels["senter"]):
                    target_pos.set_target_volume(-VOLUME)
                    print(f"  → 反转做空 {VOLUME}手（冲高回落穿SEnter={levels['senter']:.2f}）")
                    has_touched_ssetup = False   # 重置标志，避免重复触发

                # --- 反转做多：曾触及BSetup，且价格反弹到BEnter以上 ---
                elif (has_touched_bsetup
                      and curr_close > levels["benter"]
                      and prev_close <= levels["benter"]):
                    target_pos.set_target_volume(VOLUME)
                    print(f"  → 反转做多 {VOLUME}手（回落反弹穿BEnter={levels['benter']:.2f}）")
                    has_touched_bsetup = False   # 重置标志，避免重复触发

    finally:
        api.close()
        print("[R-Breaker策略] 已退出")


if __name__ == "__main__":
    main()
