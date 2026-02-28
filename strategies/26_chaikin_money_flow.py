#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
蔡金资金流量策略 (Chaikin Money Flow, CMF)
==========================================

【策略背景与来源】
蔡金资金流量（CMF）指标由著名技术分析师 Marc Chaikin 在 20 世纪 80 年代发明。
Chaikin 将其职业生涯大部分时间花在研究"资金流向"与价格的关系上，他认为机构大资金
的买卖行为会在 K 线形态与成交量中留下痕迹。CMF 正是对这一思想的量化体现：通过
每根K线收盘在高低价区间中的相对位置，结合当根的成交量加权，衡量一段时间内
"买方力量"与"卖方力量"的净值。

CMF 的核心思路来源于两个经典观察：
1. **收盘价越靠近高点，说明多方力量越强，买盘资金流入越充分**；
   反之，收盘越靠近低点，则空方资金主导。
2. **成交量是力量的量化放大器**：相同的价格位置，成交量越大，代表当日资金行为越
   坚决，对后市走势的指示意义越强。

将以上两点结合，CMF 在国际股市与期货市场均被广泛运用，尤其适合趋势过滤与
量价背离的判断。

【核心公式推导】

Step 1：计算每根K线的"资金流量乘数"（Money Flow Multiplier, MFM）
  MFM = [(Close - Low) - (High - Close)] / (High - Low)
      = [2 × Close - High - Low] / (High - Low)

  解释：
  - 分子 = 收盘价在高低范围中的位置偏移（正值→靠近高点→买方强势；负值→靠近低点→卖方强势）
  - 分母 = 当根K线的总振幅（归一化处理）
  - MFM 范围：[-1, +1]，完全收最高点时=+1，完全收最低点时=-1

Step 2：计算"资金流量成交量"（Money Flow Volume, MFV）
  MFV = MFM × Volume

  解释：用成交量对 MFM 进行加权，放大高成交量日的资金流向信号

Step 3：计算 CMF（N日滚动平均）
  CMF(N) = Sum(MFV, N) / Sum(Volume, N)

  解释：N 日内资金流量成交量的累加，再除以 N 日总成交量，得到归一化的资金流量指标
  CMF 范围同样在 [-1, +1] 内，常用 N = 20

【信号解读】
  CMF > +0.05  : 资金持续净流入，多方力量占优，偏多
  CMF < -0.05  : 资金持续净流出，空方力量占优，偏空
  -0.05 ≤ CMF ≤ +0.05 : 中性区，资金方向不明，不操作

【交易规则】
入场（信号由[-0.05, 0.05]中性区突破进入强势区）：
  开多 = CMF 由 ≤0.05 上穿 +0.05（资金流入确认，趋势转多）
       → target_pos.set_target_volume(+VOLUME)
  开空 = CMF 由 ≥-0.05 下穿 -0.05（资金流出确认，趋势转空）
       → target_pos.set_target_volume(-VOLUME)

出场（CMF 信号反转或回归中性）：
  平多 = CMF 跌回 0 以下（资金净流入消失）→ set_target_volume(0)
  平空 = CMF 升回 0 以上（资金净流出消失）→ set_target_volume(0)

附加过滤：
  - 当 High == Low 时（一字涨停/跌停板），MFM 无法计算（除零），跳过该根K线
  - 使用 pandas 的 rolling().sum() 实现窗口内累加，性能高效

【量价背离的高阶用法（仅说明，代码未实现）】
  CMF 指标最经典的高阶用法是"量价背离"：
  - 价格创新高，但 CMF 未创新高（顶背离）→ 趋势可能见顶，做空机会
  - 价格创新低，但 CMF 未创新低（底背离）→ 趋势可能见底，做多机会
  在实盘中，结合背离判断能显著提高胜率，但实现较复杂，本策略以简洁可运行为主。

【适用品种和周期】
品种：有稳定成交量的主力合约，如沪铜（CU）、豆粕（M）、螺纹钢（RB）、黄金（AU）
周期：日线（86400秒）或小时线（3600秒）均可，默认使用日线
周期选择：成交量数据在日线上更稳定，噪音更少，信号质量更高

【优缺点分析】
优点：
  - 结合价格位置与成交量，比单纯价格指标更立体
  - 归一化处理后，不同品种、不同波动率下阈值（±0.05）相对通用
  - 计算简单直观，逻辑链条清晰，易于理解和验证
  - 对机构大资金的进出行为有一定预测能力

缺点：
  - 在成交量不活跃的品种或时段（夜盘清淡时段）信号可靠性降低
  - CMF 本身存在一定滞后性（窗口期 N 越大，滞后越明显）
  - 纯粹的 CMF 信号在震荡市中容易发出连续假信号
  - 不含止损机制，建议结合 ATR 追踪止损使用

【参数说明】
  SYMBOL   : 交易合约代码
  CMF_N    : CMF 计算窗口期，默认 20 根K线
  VOLUME   : 每次开仓手数
  BULL_TH  : CMF 多头阈值（上穿时做多），默认 +0.05
  BEAR_TH  : CMF 空头阈值（下穿时做空），默认 -0.05
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
import pandas as pd

# ===================== 策略参数 =====================
SYMBOL  = "SHFE.cu2506"    # 交易合约：沪铜2506
CMF_N   = 20               # CMF 计算窗口期（日线根数）
VOLUME  = 1                # 每次开仓手数
BULL_TH = 0.05             # CMF 多头阈值（超过此值视为资金净流入）
BEAR_TH = -0.05            # CMF 空头阈值（低于此值视为资金净流出）
# ===================================================


def calc_cmf(klines: pd.DataFrame, n: int) -> pd.Series:
    """
    计算蔡金资金流量指标（Chaikin Money Flow）

    参数：
      klines : TqSdk 返回的 K 线 DataFrame，包含 high/low/close/volume 列
      n      : 滚动窗口大小

    返回：
      cmf : pd.Series，与 klines 等长，最新的值在 iloc[-1]
    """
    high   = klines["high"]
    low    = klines["low"]
    close  = klines["close"]
    volume = klines["volume"]

    # 高低价差（振幅），避免除零
    hl_range = high - low
    hl_range = hl_range.replace(0, float("nan"))  # 一字板时为 NaN，跳过

    # 资金流量乘数 MFM = (2*close - high - low) / (high - low)
    mfm = (2 * close - high - low) / hl_range

    # 资金流量成交量 MFV = MFM × volume
    mfv = mfm * volume

    # CMF = rolling_sum(MFV, N) / rolling_sum(volume, N)
    cmf = mfv.rolling(n).sum() / volume.rolling(n).sum()

    return cmf


def main():
    api = TqApi(
        account=TqSim(),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
    )

    # 订阅日线K线，数据长度需覆盖 CMF 计算所需的窗口期加一定冗余
    klines = api.get_kline_serial(SYMBOL, 86400, data_length=CMF_N + 10)

    # 初始化目标仓位任务（自动处理追单/撤单/部分成交）
    target_pos = TargetPosTask(api, SYMBOL)

    # 记录上一根K线结束时的 CMF 值，用于判断穿越
    prev_cmf = None

    print(f"[CMF策略] 启动 | {SYMBOL} | CMF窗口={CMF_N} | 阈值={BEAR_TH}/{BULL_TH}")

    while True:
        api.wait_update()

        # 只在K线更新时（新bar产生）重新计算，避免在bar内部重复触发
        if not api.is_changing(klines):
            continue

        # 计算 CMF 序列
        cmf_series = calc_cmf(klines, CMF_N)

        # 取倒数第二根（已完成的K线），避免使用未收盘的最新bar
        current_cmf = cmf_series.iloc[-2]

        if pd.isna(current_cmf):
            # 数据不足 N 根，跳过
            print(f"[CMF策略] 数据不足，等待积累中 (CMF=NaN)")
            prev_cmf = current_cmf
            continue

        print(
            f"[CMF策略] CMF={current_cmf:.4f} | "
            f"前值={prev_cmf:.4f if prev_cmf is not None and not pd.isna(prev_cmf) else 'N/A'} | "
            f"阈值 [{BEAR_TH}, {BULL_TH}]"
        )

        if prev_cmf is not None and not pd.isna(prev_cmf):
            # ---- 做多信号：CMF 上穿 BULL_TH，资金净流入确认 ----
            if prev_cmf <= BULL_TH and current_cmf > BULL_TH:
                print(f">>> CMF 上穿 {BULL_TH}，资金净流入！开多")
                target_pos.set_target_volume(VOLUME)

            # ---- 做空信号：CMF 下穿 BEAR_TH，资金净流出确认 ----
            elif prev_cmf >= BEAR_TH and current_cmf < BEAR_TH:
                print(f">>> CMF 下穿 {BEAR_TH}，资金净流出！开空")
                target_pos.set_target_volume(-VOLUME)

            # ---- 平多信号：CMF 跌回 0 以下（多方资金优势消失）----
            elif prev_cmf >= 0 and current_cmf < 0:
                print(">>> CMF 跌破 0，多方资金优势消失，平多")
                target_pos.set_target_volume(0)

            # ---- 平空信号：CMF 升回 0 以上（空方资金优势消失）----
            elif prev_cmf <= 0 and current_cmf > 0:
                print(">>> CMF 升破 0，空方资金优势消失，平空")
                target_pos.set_target_volume(0)

        # 更新 prev_cmf，记录本根K线的CMF值，供下一根K线比较
        prev_cmf = current_cmf

    api.close()


if __name__ == "__main__":
    main()
