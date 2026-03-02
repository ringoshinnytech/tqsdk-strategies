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

策略名称：VWAP 均值回归日内策略
策略编号：31
作者：TqSdk 策略库
更新日期：2026-03-02

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【策略背景与原理】

VWAP（Volume Weighted Average Price，成交量加权平均价格）是机构交易员和
做市商最常用的基准价格指标，也是量化交易中日内均值回归策略的核心工具。

VWAP 代表了当日全体参与者的平均成本价。从统计学角度看，价格在一个交易日内
长时间偏离 VWAP 后，往往会产生回归压力——市场中的机构力量会趋向以接近 VWAP
的价格完成大批量成交，从而形成拉回效应。

本策略基于以下逻辑：
  1. 计算日内滚动 VWAP（每日开盘重置）；
  2. 计算价格偏离 VWAP 的标准差（VWAP-STD），定义超买/超卖区间；
  3. 当价格向上大幅偏离 VWAP（超过 +N 倍标准差）时，认为超买 → 做空；
  4. 当价格向下大幅偏离 VWAP（超过 -N 倍标准差）时，认为超卖 → 做多；
  5. 价格回归至 VWAP ± 0.5 倍标准差区间时，平仓了结。

VWAP 计算公式：
  VWAP = Σ(成交量 × 典型价格) / Σ成交量
  典型价格（Typical Price）= (最高价 + 最低价 + 收盘价) / 3

偏离度（Z-score）：
  Z = (当前价格 - VWAP) / VWAP_STD

【策略特点】

  1. 纯日内策略：每日尾盘强制平仓，不持有隔夜仓位，规避隔夜风险；
  2. 均值回归逻辑：适合震荡市场，特别是成交量活跃、日内波动规律的主力合约；
  3. 动态标准差带：随着日内成交量累积，标准差会收窄，信号越来越保守，
     避免尾盘频繁交易；
  4. 与趋势策略互补：VWAP 策略与趋势跟踪策略相关性低，可构成多策略组合
     以平滑净值曲线。

【适用品种与时间周期】

  推荐品种：成交量大、流动性好的主力合约，如螺纹钢(rb)、铁矿石(i)、
            沪铜(cu)、豆粕(m) 等。
  推荐周期：1 分钟 K 线（可调整为 3 分钟或 5 分钟以减少噪音）。
  不适合：成交量极小的合约，VWAP 计算不稳定。

【参数说明】

  SYMBOL         : 目标合约代码
  KLINE_FREQ     : K 线周期（秒），默认 60 秒（1 分钟）
  Z_ENTRY        : 开仓偏离倍数，默认 2.0（价格偏离 VWAP 2 个标准差时入场）
  Z_EXIT         : 平仓偏离倍数，默认 0.3（价格回归至 0.3 倍标准差内时平仓）
  LOT_SIZE       : 每次开仓手数
  CLOSE_HOUR     : 强制平仓小时（日内策略收盘前平仓），默认 14 时 50 分

【风险提示】

  1. VWAP 均值回归在单边趋势行情中损失惨重，需严格设置止损（如 3 倍标准差反向止损）；
  2. 日内震荡程度会受消息面影响，重大数据发布日（如 PMI、CPI）慎用；
  3. 滑点敏感：1 分钟级别高频策略需关注实盘滑点，回测时应加入手续费和滑点假设；
  4. 本策略仅供学习参考，实盘请做充分回测和风控验证。
"""

import math
import datetime
import numpy as np
from tqsdk import TqApi, TqAuth, TqSim, BacktestFinished

# ─────────────────────────────────────────────
# 策略参数
# ─────────────────────────────────────────────
SYMBOL = "KQ.m@SHFE.rb"    # 螺纹钢主力合约（自动展期）
KLINE_FREQ = 60             # K 线周期：1 分钟 = 60 秒
Z_ENTRY = 2.0               # 开仓阈值（偏离 VWAP 的标准差倍数）
Z_EXIT = 0.3                # 平仓阈值（回归至 VWAP 附近的标准差倍数内）
Z_STOP = 3.5                # 止损阈值（偏离超过此值反向止损）
LOT_SIZE = 1                # 每次开仓手数
CLOSE_HOUR = 14             # 强制平仓小时
CLOSE_MINUTE = 50           # 强制平仓分钟（14:50 前清仓）


class VwapCalculator:
    """
    日内滚动 VWAP 及标准差计算器。
    每个交易日开盘自动重置，累计计算当日 VWAP 和价格偏离标准差。

    成员变量：
        vwap      : 当前 VWAP 值
        std       : 当前价格偏离 VWAP 的标准差（基于典型价格）
        cum_vol   : 累计成交量（用于判断样本是否充足）
    """

    def __init__(self):
        self._reset()

    def _reset(self):
        """重置所有日内累计状态"""
        self._cum_vol = 0.0          # 累计成交量
        self._cum_tp_vol = 0.0       # 累计 (典型价格 × 成交量)
        self._cum_tp2_vol = 0.0      # 累计 (典型价格² × 成交量)，用于方差计算
        self.vwap = None
        self.std = None
        self.cum_vol = 0.0

    def update(self, high: float, low: float, close: float, volume: float, new_day: bool):
        """
        更新一根 K 线数据。

        参数：
            high     : 本根 K 线最高价
            low      : 本根 K 线最低价
            close    : 本根 K 线收盘价
            volume   : 本根 K 线成交量（手）
            new_day  : 是否为新交易日第一根 K 线（触发重置）
        """
        if new_day:
            self._reset()

        if volume <= 0:
            return

        # 典型价格
        tp = (high + low + close) / 3.0

        # 累计加权求和
        self._cum_vol += volume
        self._cum_tp_vol += tp * volume
        self._cum_tp2_vol += tp * tp * volume

        # VWAP
        self.vwap = self._cum_tp_vol / self._cum_vol
        self.cum_vol = self._cum_vol

        # 方差 = E[x²] - E[x]²（Welford's 公式变体）
        variance = (self._cum_tp2_vol / self._cum_vol) - (self.vwap ** 2)
        variance = max(variance, 0.0)   # 浮点误差保护
        self.std = math.sqrt(variance) if variance > 1e-10 else None

    def z_score(self, price: float) -> float | None:
        """
        计算当前价格相对于 VWAP 的 Z-score。
        正值表示价格高于 VWAP，负值表示低于 VWAP。
        返回 None 表示数据不足（标准差为 0 或尚未初始化）。
        """
        if self.vwap is None or self.std is None or self.std < 1e-10:
            return None
        return (price - self.vwap) / self.std


def main():
    # ─────────────────────────────────────────
    # 初始化 TqApi
    # ─────────────────────────────────────────
    api = TqApi(
        account=TqSim(init_balance=200000),
        auth=TqAuth("your_username", "your_password"),  # 请替换为实际账号
    )

    klines = api.get_kline_serial(SYMBOL, KLINE_FREQ, data_length=500)
    quote = api.get_quote(SYMBOL)
    account = api.get_account()
    position = api.get_position(SYMBOL)

    print(f"[VWAP回归] 启动策略：{SYMBOL} | 开仓阈值={Z_ENTRY}σ | 平仓阈值={Z_EXIT}σ")

    vwap_calc = VwapCalculator()

    # 记录上一根 K 线的日期，用于检测新交易日
    last_bar_date = None

    # 当前仓位方向（1=多, -1=空, 0=空仓）
    position_side = 0

    try:
        while True:
            api.wait_update()

            # 等待 K 线更新（有新的已完成 K 线出现）
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue

            # 取倒数第 2 根（已完成的 K 线）
            bar = klines.iloc[-2]
            bar_dt = datetime.datetime.fromtimestamp(
                bar["datetime"] / 1e9,
                tz=datetime.timezone(datetime.timedelta(hours=8))
            )
            bar_date = bar_dt.date()
            bar_time = bar_dt.time()

            # 检测是否新交易日
            is_new_day = (last_bar_date is not None and bar_date != last_bar_date)
            last_bar_date = bar_date

            # 更新 VWAP 计算器
            vwap_calc.update(
                high=bar["high"],
                low=bar["low"],
                close=bar["close"],
                volume=bar["volume"],
                new_day=is_new_day,
            )

            # 样本不足时（日内成交量太少）跳过
            if vwap_calc.cum_vol < 10 or vwap_calc.std is None:
                continue

            current_price = quote.last_price
            z = vwap_calc.z_score(current_price)

            if z is None:
                continue

            vwap = vwap_calc.vwap
            std = vwap_calc.std
            long_pos = position.pos_long_today + position.pos_long
            short_pos = position.pos_short_today + position.pos_short

            # ─────────────────────────────────────────
            # 尾盘强制平仓（14:50 前清仓）
            # ─────────────────────────────────────────
            if (bar_time.hour > CLOSE_HOUR or
                    (bar_time.hour == CLOSE_HOUR and bar_time.minute >= CLOSE_MINUTE)):
                if long_pos > 0:
                    api.insert_order(SYMBOL, "SELL", "CLOSE", long_pos, quote.bid_price1)
                    print(f"[VWAP回归] 尾盘强平多头 {long_pos} 手")
                    position_side = 0
                if short_pos > 0:
                    api.insert_order(SYMBOL, "BUY", "CLOSE", short_pos, quote.ask_price1)
                    print(f"[VWAP回归] 尾盘强平空头 {short_pos} 手")
                    position_side = 0
                continue

            # ─────────────────────────────────────────
            # 止损逻辑（偏离超过 Z_STOP 倍标准差）
            # ─────────────────────────────────────────
            if position_side == 1 and z < -Z_STOP:
                # 持多，价格继续暴跌，止损平多
                if long_pos > 0:
                    api.insert_order(SYMBOL, "SELL", "CLOSE", long_pos, quote.bid_price1)
                    print(f"[VWAP回归] 止损平多 z={z:.2f} < -{Z_STOP}")
                    position_side = 0

            elif position_side == -1 and z > Z_STOP:
                # 持空，价格继续暴涨，止损平空
                if short_pos > 0:
                    api.insert_order(SYMBOL, "BUY", "CLOSE", short_pos, quote.ask_price1)
                    print(f"[VWAP回归] 止损平空 z={z:.2f} > {Z_STOP}")
                    position_side = 0

            # ─────────────────────────────────────────
            # 平仓逻辑（价格回归至 VWAP 附近）
            # ─────────────────────────────────────────
            elif position_side == 1 and abs(z) <= Z_EXIT:
                # 多头回归平仓
                if long_pos > 0:
                    api.insert_order(SYMBOL, "SELL", "CLOSE", long_pos, quote.bid_price1)
                    print(f"[VWAP回归] 多头回归平仓 VWAP={vwap:.2f} z={z:.2f}")
                    position_side = 0

            elif position_side == -1 and abs(z) <= Z_EXIT:
                # 空头回归平仓
                if short_pos > 0:
                    api.insert_order(SYMBOL, "BUY", "CLOSE", short_pos, quote.ask_price1)
                    print(f"[VWAP回归] 空头回归平仓 VWAP={vwap:.2f} z={z:.2f}")
                    position_side = 0

            # ─────────────────────────────────────────
            # 开仓逻辑（价格大幅偏离 VWAP）
            # ─────────────────────────────────────────
            elif position_side == 0:
                if z >= Z_ENTRY:
                    # 价格远高于 VWAP → 超买 → 做空
                    api.insert_order(SYMBOL, "SELL", "OPEN", LOT_SIZE, quote.bid_price1)
                    print(f"[VWAP回归] 做空开仓 price={current_price:.2f} "
                          f"VWAP={vwap:.2f} STD={std:.2f} z={z:.2f}")
                    position_side = -1

                elif z <= -Z_ENTRY:
                    # 价格远低于 VWAP → 超卖 → 做多
                    api.insert_order(SYMBOL, "BUY", "OPEN", LOT_SIZE, quote.ask_price1)
                    print(f"[VWAP回归] 做多开仓 price={current_price:.2f} "
                          f"VWAP={vwap:.2f} STD={std:.2f} z={z:.2f}")
                    position_side = 1

    except BacktestFinished:
        bal = account.balance
        mdd = account.max_drawdown
        print("\n════════════════════════════════════")
        print(f"[VWAP回归] 回测结束")
        print(f"  最终权益：{bal:.2f}")
        print(f"  最大回撤：{mdd:.2f}%")
        print("════════════════════════════════════")
    finally:
        api.close()


if __name__ == "__main__":
    main()
