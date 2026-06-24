#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
布林 %B 均值回归策略
============

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本策略脚本默认使用 TqSim 模拟账户演示交易流程，不包含任何真实账号、交易密码、Token 或 API Key。
运行前可以通过环境变量 TQ_ACCOUNT / TQ_PASSWORD 提供天勤或快期账号；如果不设置，代码只保留 YOUR_ACCOUNT / YOUR_PASSWORD 占位符，方便公开托管时避免泄露敏感信息。

【策略介绍】
布林 %B 均值回归策略用于演示如何把“用 %B 衡量价格在布林带内的位置，极端偏离后回归中轨”这一交易想法落到 TqSdk 策略脚本中。
脚本默认关注 CZCE.SR505，使用 单合约时序信号：根据加权因子得分决定目标多空仓位。
核心因子包括：布林 %B 极端回归、波动收缩状态、RSI 超买超卖反转。核心因子会被标准化并加权成综合得分，得分超过入场阈值时建立目标仓位，得分回落到退出阈值附近时降低或清空仓位。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 建议通过环境变量设置账号：set TQ_ACCOUNT=你的账号，set TQ_PASSWORD=你的密码；也可以把占位符替换为自己的账号信息。
3. 本示例使用 TqSim 模拟账户，不会直接连接实盘资金账号。
4. 合约月份只是示例，运行前请替换为当前在市、流动性充足的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。因子信号、历史价差、成交量结构和波动率规律都会失效，趋势反转、跳空、流动性不足、手续费和滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。
"""

import os

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask


STRATEGY_ID = 71
STRATEGY_NAME = "布林 %B 均值回归策略"
SYMBOLS = ["CZCE.SR505"]
MODE = "single"
PAIR_STYLE = "mean_reversion"
KLINE_DUR = 60 * 60
DATA_LENGTH = 180
ENTRY_SCORE = 0.85
EXIT_SCORE = 0.25
BASE_VOLUME = 1
MAX_VOLUME = 1
FACTOR_WEIGHTS = {"boll_reversion": 1.2, "volatility_decline": 0.4, "rsi_reversal": 0.2}
EPS = 1e-12


def create_api():
    """创建 TqApi；账号从环境变量读取，避免把真实敏感信息写进公开仓库。"""
    tq_account = os.getenv("TQ_ACCOUNT", "YOUR_ACCOUNT")
    tq_password = os.getenv("TQ_PASSWORD", "YOUR_PASSWORD")
    return TqApi(account=TqSim(), auth=TqAuth(tq_account, tq_password))


def latest(series, default=0.0):
    try:
        value = series.iloc[-1]
    except Exception:
        return default
    if pd.isna(value) or np.isinf(value):
        return default
    return float(value)


def clamp(value, lower=-3.0, upper=3.0):
    return max(lower, min(upper, float(value)))


def rolling_zscore(series, window=40):
    if len(series) < window + 2:
        return 0.0
    sample = series.iloc[-window:]
    std = sample.std()
    if pd.isna(std) or std < EPS:
        return 0.0
    return latest((series - sample.mean()) / std)


def calc_atr(df, period=14):
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_rsi(close, period=14):
    diff = close.diff()
    up = diff.clip(lower=0).rolling(period).mean()
    down = (-diff.clip(upper=0)).rolling(period).mean()
    rs = up / (down + EPS)
    return 100 - 100 / (1 + rs)


def calc_mfi(df, period=14):
    typical = (df["high"] + df["low"] + df["close"]) / 3
    raw_money = typical * df["volume"].replace(0, np.nan).fillna(0)
    direction = typical.diff()
    positive = raw_money.where(direction > 0, 0.0).rolling(period).sum()
    negative = raw_money.where(direction < 0, 0.0).rolling(period).sum().abs()
    ratio = positive / (negative + EPS)
    return 100 - 100 / (1 + ratio)


def calc_kama(close, er_period=10, fast=2, slow=30):
    if len(close) < slow + er_period + 2:
        return close.rolling(slow).mean()
    change = (close - close.shift(er_period)).abs()
    volatility = close.diff().abs().rolling(er_period).sum()
    er = (change / (volatility + EPS)).fillna(0)
    fast_sc = 2 / (fast + 1)
    slow_sc = 2 / (slow + 1)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    kama = close.copy().astype(float)
    kama.iloc[:slow] = close.iloc[:slow].mean()
    for i in range(slow, len(close)):
        kama.iloc[i] = kama.iloc[i - 1] + sc.iloc[i] * (close.iloc[i] - kama.iloc[i - 1])
    return kama


def calc_nvi(close, volume):
    nvi = pd.Series(1000.0, index=close.index)
    returns = close.pct_change().fillna(0)
    for i in range(1, len(close)):
        if volume.iloc[i] < volume.iloc[i - 1]:
            nvi.iloc[i] = nvi.iloc[i - 1] * (1 + returns.iloc[i])
        else:
            nvi.iloc[i] = nvi.iloc[i - 1]
    return nvi


def open_interest_series(df):
    for field in ("close_oi", "open_oi", "open_interest", "interest"):
        if field in df.columns:
            return df[field].astype(float)
    return pd.Series(0.0, index=df.index)


def calculate_features(df):
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float).replace(0, np.nan).ffill().fillna(0)
    oi = open_interest_series(df)
    atr = calc_atr(df)
    rsi = calc_rsi(close)
    mfi = calc_mfi(df)
    ma_fast = close.rolling(10).mean()
    ma_slow = close.rolling(30).mean()
    kama = calc_kama(close)
    returns = close.pct_change().fillna(0)
    vol_20 = returns.rolling(20).std()
    high_20 = high.rolling(20).max().shift(1)
    low_20 = low.rolling(20).min().shift(1)
    range_20 = (high_20 - low_20).replace(0, np.nan)
    mid_40 = close.rolling(40).mean()
    std_40 = close.rolling(40).std()
    boll_upper = mid_40 + 2 * std_40
    boll_lower = mid_40 - 2 * std_40
    percent_b = (close - boll_lower) / (boll_upper - boll_lower + EPS)
    typical = (high + low + close) / 3
    vwap = (typical * volume).rolling(30).sum() / (volume.rolling(30).sum() + EPS)
    nvi = calc_nvi(close, volume)
    efficiency = (close.diff(10).abs() / (close.diff().abs().rolling(10).sum() + EPS)).fillna(0)
    path_ratio = (high.rolling(20).max() - low.rolling(20).min()) / (close.diff().abs().rolling(20).sum() + EPS)
    drawdown = close / (close.rolling(40).max() + EPS) - 1
    runup = close / (close.rolling(40).min() + EPS) - 1
    atr_now = latest(atr, 0.0)
    price = latest(close, 0.0)
    atr_pct = atr_now / max(price, EPS)
    avg_atr_pct = latest((atr / (close + EPS)).rolling(60).mean())
    volume_ratio = latest(volume / (volume.rolling(20).mean() + EPS) - 1)
    channel_high = latest(high_20)
    channel_low = latest(low_20)
    short_high = latest(high.rolling(6).max().shift(1))
    short_low = latest(low.rolling(6).min().shift(1))
    close_sign_10 = np.sign(latest(close.diff(10), 0))
    rsi_sign_10 = np.sign(latest(rsi.diff(10), 0))

    features = {
        "momentum_5": clamp(latest(close.pct_change(5)) * 20),
        "momentum_20": clamp(latest(close.pct_change(20)) * 10),
        "trend_slope": clamp((latest(ma_fast) - latest(ma_slow)) / max(price, EPS) * 30),
        "kama_trend": clamp((price - latest(kama)) / max(atr_now, EPS)),
        "efficiency": clamp(latest(efficiency) * np.sign(latest(close.diff(10))) * 2),
        "volatility_filter": clamp(-(atr_pct - avg_atr_pct) * 100),
        "fractal_trend": clamp((latest(path_ratio) - 0.45) * 3),
        "range_breakout": clamp((price - channel_high) / max(atr_now, EPS)) if price > channel_high else clamp((price - channel_low) / max(atr_now, EPS)) if price < channel_low else 0.0,
        "volume_confirm": clamp(volume_ratio),
        "cmo": clamp((returns.tail(14).clip(lower=0).sum() + returns.tail(14).clip(upper=0).sum()) / (returns.tail(14).abs().sum() + EPS) * 2),
        "squeeze_breakout": clamp((1 if latest(std_40 / (mid_40 + EPS)) < latest((std_40 / (mid_40 + EPS)).rolling(80).quantile(0.25)) else 0) * latest(np.sign(close.diff(5))) * abs(volume_ratio + 1)),
        "range_expansion": clamp((latest(high - low) / max(latest(atr), EPS) - 1) * np.sign(latest(close.diff()))),
        "atr_position": clamp((price - latest(close.rolling(20).mean())) / max(atr_now, EPS)),
        "vwap_reversion": clamp(-(price - latest(vwap)) / max(atr_now, EPS)),
        "rsi_reversal": clamp((50 - latest(rsi, 50)) / 18),
        "divergence": clamp(-close_sign_10 if close_sign_10 != rsi_sign_10 else 0),
        "mean_reversion": clamp(-rolling_zscore(close, 40)),
        "boll_reversion": clamp((0.5 - latest(percent_b, 0.5)) * 3),
        "volatility_decline": clamp((avg_atr_pct - atr_pct) * 80),
        "range_reversion": clamp((0.5 - latest((close - low_20) / (range_20 + EPS), 0.5)) * 2),
        "atr_zscore_reversion": clamp(-(price - latest(mid_40)) / max(atr_now, EPS)),
        "mfi_reversal": clamp((50 - latest(mfi, 50)) / 18),
        "price_volume_divergence": clamp(-np.sign(latest(close.diff(5))) if volume_ratio < -0.2 else 0),
        "value_area_reversion": clamp(-(price - latest((typical * volume).rolling(60).sum() / (volume.rolling(60).sum() + EPS))) / max(atr_now, EPS)),
        "oi_momentum": clamp(latest(oi.pct_change(5)) * 20 * np.sign(latest(close.pct_change(5), 0))),
        "turnover_breakout": clamp(volume_ratio * np.sign(latest(close.diff(5), 0))),
        "nvi_trend": clamp((latest(nvi) - latest(nvi.rolling(30).mean())) / (latest(nvi.rolling(30).std()) + EPS)),
        "risk_adjusted_momentum": clamp(latest(close.pct_change(20)) / (latest(vol_20) + EPS) / 3),
        "low_volatility": clamp((latest(vol_20.rolling(60).mean()) - latest(vol_20)) * 20),
        "liquidity": clamp(np.log1p(latest(volume.rolling(20).mean())) / 12 - 0.5),
        "carry_proxy": clamp((latest(ma_fast) - latest(ma_slow)) / max(price, EPS) * 20),
        "term_structure_proxy": clamp((latest(close.pct_change(60)) - latest(close.pct_change(20))) * 8),
        "regime_trend": clamp((abs(latest(ma_fast - ma_slow)) / max(atr_now, EPS) - 0.3) * np.sign(latest(ma_fast - ma_slow))),
        "opening_range_breakout": clamp((price - short_high) / max(atr_now, EPS)) if price > short_high else clamp((price - short_low) / max(atr_now, EPS)) if price < short_low else 0.0,
        "vol_target": clamp(0.015 / max(atr_pct, 0.003) - 1),
        "drawdown_guard": clamp((latest(runup) + latest(drawdown)) * 2),
    }
    return features


def weighted_score(features):
    score = 0.0
    detail = []
    for name, weight in FACTOR_WEIGHTS.items():
        value = features.get(name, 0.0)
        score += weight * value
        detail.append(f"{name}={value:.2f}")
    return clamp(score), ", ".join(detail)


def score_to_volume(score):
    if abs(score) < EXIT_SCORE:
        return 0
    if abs(score) < ENTRY_SCORE:
        return None
    volume = min(MAX_VOLUME, max(1, int(abs(score) // ENTRY_SCORE) + BASE_VOLUME - 1))
    return volume if score > 0 else -volume


def calculate_pair_signal(df_a, df_b):
    close_a = df_a["close"].astype(float)
    close_b = df_b["close"].astype(float)
    aligned = pd.concat([close_a, close_b], axis=1).dropna()
    aligned.columns = ["a", "b"]
    if len(aligned) < 80:
        return 0, 0, "等待价差历史数据"
    log_a = np.log(aligned["a"].clip(lower=EPS))
    log_b = np.log(aligned["b"].clip(lower=EPS))
    beta_window = aligned.tail(60)
    beta = np.cov(np.log(beta_window["a"]), np.log(beta_window["b"]))[0, 1] / (np.var(np.log(beta_window["b"])) + EPS)
    residual = log_a - beta * log_b
    z = rolling_zscore(residual, 60)
    spread_momentum = latest(residual.diff(10), 0.0) / (latest(residual.diff().abs().rolling(60).mean(), EPS) + EPS)
    raw_score = FACTOR_WEIGHTS.get("spread_zscore", 1.0) * z + FACTOR_WEIGHTS.get("spread_momentum", 0.0) * spread_momentum
    if "beta_residual" in FACTOR_WEIGHTS:
        raw_score += FACTOR_WEIGHTS["beta_residual"] * clamp(z - spread_momentum)
    score = clamp(raw_score)
    if abs(score) < EXIT_SCORE:
        return 0, 0, f"z={z:.2f}, momentum={spread_momentum:.2f}, beta={beta:.2f}"
    if abs(score) < ENTRY_SCORE:
        return None, None, f"z={z:.2f}, momentum={spread_momentum:.2f}, beta={beta:.2f}"
    volume = min(MAX_VOLUME, max(1, int(abs(score) // ENTRY_SCORE) + BASE_VOLUME - 1))
    if PAIR_STYLE == "momentum":
        direction = 1 if score > 0 else -1
    else:
        direction = -1 if score > 0 else 1
    return direction * volume, -direction * volume, f"z={z:.2f}, momentum={spread_momentum:.2f}, beta={beta:.2f}"


def run_single(api):
    symbol = SYMBOLS[0]
    klines = api.get_kline_serial(symbol, KLINE_DUR, data_length=DATA_LENGTH)
    target_pos = TargetPosTask(api, symbol)
    print(f"[策略{STRATEGY_ID}] {STRATEGY_NAME}启动 | 合约: {symbol} | 模式: 单合约")
    while True:
        api.wait_update()
        if not api.is_changing(klines):
            continue
        features = calculate_features(klines)
        score, detail = weighted_score(features)
        target_volume = score_to_volume(score)
        if target_volume is not None:
            target_pos.set_target_volume(target_volume)
        print(f"[策略{STRATEGY_ID}] {symbol} score={score:.2f} target={target_volume} | {detail}")


def run_cross_section(api):
    klines = {symbol: api.get_kline_serial(symbol, KLINE_DUR, data_length=DATA_LENGTH) for symbol in SYMBOLS}
    target_pos = {symbol: TargetPosTask(api, symbol) for symbol in SYMBOLS}
    print(f"[策略{STRATEGY_ID}] {STRATEGY_NAME}启动 | 品种数: {len(SYMBOLS)} | 模式: 截面轮动")
    while True:
        api.wait_update()
        scores = []
        for symbol, df in klines.items():
            if len(df) < 80:
                continue
            features = calculate_features(df)
            score, detail = weighted_score(features)
            scores.append((symbol, score, detail))
        if len(scores) < 2:
            continue
        scores.sort(key=lambda item: item[1], reverse=True)
        long_symbol, long_score, long_detail = scores[0]
        short_symbol, short_score, short_detail = scores[-1]
        for symbol in SYMBOLS:
            target_pos[symbol].set_target_volume(0)
        if long_score >= ENTRY_SCORE:
            target_pos[long_symbol].set_target_volume(BASE_VOLUME)
        if short_score <= -ENTRY_SCORE:
            target_pos[short_symbol].set_target_volume(-BASE_VOLUME)
        print(f"[策略{STRATEGY_ID}] long={long_symbol}({long_score:.2f}) short={short_symbol}({short_score:.2f})")
        print(f"    long factors: {long_detail}")
        print(f"    short factors: {short_detail}")


def run_pair(api):
    symbol_a, symbol_b = SYMBOLS
    klines_a = api.get_kline_serial(symbol_a, KLINE_DUR, data_length=DATA_LENGTH)
    klines_b = api.get_kline_serial(symbol_b, KLINE_DUR, data_length=DATA_LENGTH)
    target_a = TargetPosTask(api, symbol_a)
    target_b = TargetPosTask(api, symbol_b)
    print(f"[策略{STRATEGY_ID}] {STRATEGY_NAME}启动 | {symbol_a} vs {symbol_b} | style={PAIR_STYLE}")
    while True:
        api.wait_update()
        if not (api.is_changing(klines_a) or api.is_changing(klines_b)):
            continue
        vol_a, vol_b, detail = calculate_pair_signal(klines_a, klines_b)
        if vol_a is not None and vol_b is not None:
            target_a.set_target_volume(vol_a)
            target_b.set_target_volume(vol_b)
        print(f"[策略{STRATEGY_ID}] {symbol_a} target={vol_a}, {symbol_b} target={vol_b} | {detail}")


def main():
    api = create_api()
    try:
        if MODE == "cross_section":
            run_cross_section(api)
        elif MODE == "pair":
            run_pair(api)
        else:
            run_single(api)
    except KeyboardInterrupt:
        print(f"[策略{STRATEGY_ID}] 用户中断，准备退出")
    finally:
        api.close()


if __name__ == "__main__":
    main()
