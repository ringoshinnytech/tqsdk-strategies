# TqSdk 量化交易策略集

> 基于 [天勤量化 TqSdk](https://github.com/shinnytech/tqsdk-python) 实现的期货量化交易策略示例集合，每个策略附有完整中文注释和详细策略思路讲解。

---

## 📖 关于 TqSdk

**TqSdk（天勤量化开发包）** 是由 [信易科技](https://www.shinnytech.com/) 发起并开源的 Python 量化交易框架，专为国内期货市场设计。

### 核心特性

- 🚀 **极简代码**：几十行代码即可构建完整的量化交易策略
- 📊 **全品种数据**：覆盖期货、期权、股票，提供全历史 Tick 与 K 线数据（从上市日起）
- ⚡ **实时行情**：毫秒级行情推送，数据全在内存，零访问延迟
- 🔄 **全流程支持**：历史数据 → 开发调试 → 策略回测 → 模拟交易 → 实盘交易 → 运行监控
- 🏦 **广泛兼容**：支持市场上 90% 以上的期货公司实盘交易
- 🐼 **Pandas 友好**：K 线、Tick 数据直接以 `pandas.DataFrame` 返回，配合 numpy 无缝分析
- 📐 **近百个技术指标**：内置 MA、EMA、BOLL、RSI、MACD、ATR 等常用指标函数及源码
- 🤖 **多账户支持**：支持多个实盘账户、模拟账户同时运行
- 🔁 **灵活回测**：支持 Tick 级和 K 线级回测，无需建立和维护数据库

### 系统架构

```
策略程序 (TqSdk)
    ├── 行情网关  ←→  实时行情 / 历史数据（Diff 协议）
    └── 交易中继  ←→  期货公司交易系统（CTP / 资管柜台 / 高速柜台）
```

### 支持的交易类型

| 类型 | 说明 |
|------|------|
| 期货实盘 | 支持 CTP 直连及众期、融航、杰宜斯等资管柜台，易达、ctpmini 等高速柜台 |
| 期权交易 | 商品期权、股指期权 |
| 股票交易 | A 股实盘与回测 |
| 模拟交易 | TqKq 快期模拟账户或内置临时模拟账户 |

---

## 🔗 官方资源

| 资源 | 链接 |
|------|------|
| 📘 官方文档 | https://doc.shinnytech.com/tqsdk/latest/ |
| ⚡ 快速入门 | https://doc.shinnytech.com/tqsdk/latest/quickstart.html |
| 🎯 策略示例库 | https://doc.shinnytech.com/tqsdk/latest/demo/strategy.html |
| 📐 API 参考 | https://doc.shinnytech.com/tqsdk/latest/reference/index.html |
| 🐙 GitHub 仓库 | https://github.com/shinnytech/tqsdk-python |
| 🌐 信易科技官网 | https://www.shinnytech.com/ |
| 🧑‍💻 快期账户注册 | https://account.shinnytech.com/ |
| 💬 用户社区论坛 | https://www.shinnytech.com/qa/ |
| 📺 入门视频教程 | https://www.shinnytech.com/tqsdkquickstart/ |
| 🤖 天勤 AI 助手 | https://www.shinnytech.com/products/tqsdk |

---

## 📦 安装

```bash
pip install tqsdk -U
```

**要求：** Python >= 3.8（推荐 3.10+）

使用国内镜像（推荐，速度更快）：

```bash
pip install tqsdk -U -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host=pypi.tuna.tsinghua.edu.cn
```

---

## 🚀 快速上手

### 获取实时行情

```python
from tqsdk import TqApi, TqAuth

api = TqApi(auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
quote = api.get_quote("SHFE.rb2501")

while True:
    api.wait_update()
    print(quote.last_price, quote.volume)
```

### 策略回测

```python
from datetime import date
from tqsdk import TqApi, TqAuth, TqBacktest

api = TqApi(
    backtest=TqBacktest(start_dt=date(2023, 1, 1), end_dt=date(2024, 1, 1)),
    auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD")
)
```

---

## 📁 策略分类（100个）

> 每个策略文件包含：**500字以上策略思路讲解 + 完整可运行代码 + 详细中文注释**。以下按策略主逻辑重新归类；如果一个策略同时具备多种特征，只放在最主要的一类中，方便快速查找。

### 趋势跟踪与趋势强度类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [01_double_ma.py](strategies/01_double_ma.py) | 双均线趋势策略 | MA5/MA20 金叉做多、死叉做空 |
| [05_turtle_trading.py](strategies/05_turtle_trading.py) | 海龟交易策略 | 唐奇安通道突破 + ATR 仓位管理 |
| [06_macd_trend.py](strategies/06_macd_trend.py) | MACD 趋势策略 | DIF/DEA 金叉死叉，动能确认趋势方向 |
| [09_atr_stop_loss.py](strategies/09_atr_stop_loss.py) | ATR 动态止损策略 | 均线趋势入场 + ATR 追踪止损出场 |
| [16_aroon_trend.py](strategies/16_aroon_trend.py) | Aroon 指标趋势策略 | Aroon Up/Down 强弱对比判断趋势 |
| [18_parabolic_sar.py](strategies/18_parabolic_sar.py) | 抛物线转向策略 | SAR 跟踪止损点，价格穿越 SAR 转向 |
| [19_ichimoku_cloud.py](strategies/19_ichimoku_cloud.py) | 一目均衡表趋势策略 | 转换线、基准线和云层共同确认趋势 |
| [20_hull_ma.py](strategies/20_hull_ma.py) | Hull 移动平均线策略 | 减少均线滞后的 WMA 加权趋势跟踪 |
| [22_trix_trend.py](strategies/22_trix_trend.py) | TRIX 三重指数策略 | 三重 EMA 变化率过滤短期噪音 |
| [25_multiperiod_ma.py](strategies/25_multiperiod_ma.py) | 多周期均线共振策略 | 日/小时/分钟三周期均线方向一致才入场 |
| [29_adx_trend_filter.py](strategies/29_adx_trend_filter.py) | ADX 趋势强度过滤策略 | ADX 确认趋势强度，+DI/-DI 判断方向，ATR 追踪止损 |
| [30_supertrend.py](strategies/30_supertrend.py) | SuperTrend 超级趋势策略 | ATR 倍数动态上下轨，趋势翻转时平仓反手 |
| [32_ichimoku_cloud.py](strategies/32_ichimoku_cloud.py) | 一目均衡云图策略 | 云层突破与多线确认结合的趋势策略 |
| [36_guppy_ma.py](strategies/36_guppy_ma.py) | 顾比均线复合策略 | 短期均线组与长期均线组比较趋势强弱 |
| [40_momentum_acceleration.py](strategies/40_momentum_acceleration.py) | 趋势动量加速策略 | 趋势确认后捕捉动量继续增强阶段 |
| [41_bullish_ma_arrangement.py](strategies/41_bullish_ma_arrangement.py) | 均线多头排列趋势策略 | 短中长期均线多头排列确认上升趋势 |
| [43_ma_crossover.py](strategies/43_ma_crossover.py) | 均线金叉死叉趋势策略 | 短长均线交叉结合成交量确认方向 |
| [44_guppy_ma_trend.py](strategies/44_guppy_ma_trend.py) | 顾比均线复合趋势策略 | 两组顾比均线共振确认趋势 |
| [64_kama_adaptive_trend.py](strategies/64_kama_adaptive_trend.py) | KAMA 自适应均线趋势策略 | 用效率系数调节均线快慢，在噪音较低时跟随趋势、震荡时降低换手 |
| [66_chande_momentum_trend.py](strategies/66_chande_momentum_trend.py) | Chande 动量振荡趋势策略 | 用 CMO 衡量净动量强度，并叠加中期收益率确认趋势延续 |
| [90_trailing_atr_pyramid.py](strategies/90_trailing_atr_pyramid.py) | ATR 追踪加仓趋势策略 | 趋势确认后用 ATR 管理追踪止损，并按信号强度逐步提高目标手数 |
| [92_drawdown_guard_trend.py](strategies/92_drawdown_guard_trend.py) | 回撤保护趋势策略 | 趋势信号有效时持仓，若价格相对近期高低点回撤过深则降低方向暴露 |

### 突破与通道类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [02_boll_breakout.py](strategies/02_boll_breakout.py) | 布林带突破策略 | 上轨突破做多、下轨跌破做空、带宽过滤 |
| [04_dual_thrust.py](strategies/04_dual_thrust.py) | Dual Thrust 日内突破 | 开盘价 ± Range 动态轨道，收盘前强制平仓 |
| [08_cci_breakout.py](strategies/08_cci_breakout.py) | CCI 顺势指标策略 | ±100 反向、±200 顺势突破 |
| [10_momentum_breakout.py](strategies/10_momentum_breakout.py) | 价格动量突破策略 | N 日涨跌幅动量信号触发入场 |
| [13_opening_range_breakout.py](strategies/13_opening_range_breakout.py) | 开盘区间突破策略 | 开盘前 30 分钟高低点作为当日突破区间 |
| [15_donchian_channel.py](strategies/15_donchian_channel.py) | 唐奇安通道策略 | N 日最高最低价通道突破入场 |
| [19_atr_channel_breakout.py](strategies/19_atr_channel_breakout.py) | ATR 通道突破策略 | ATR 动态通道突破后顺势入场 |
| [21_keltner_channel.py](strategies/21_keltner_channel.py) | 肯特纳通道策略 | EMA ± ATR 通道，价格突破做趋势 |
| [28_volatility_breakout.py](strategies/28_volatility_breakout.py) | 波动率动量突破策略 | ATR 突破 + ADX 趋势确认，动态止损跟踪趋势 |
| [32_linear_regression_channel.py](strategies/32_linear_regression_channel.py) | 线性回归通道策略 | 用回归中轴和通道衡量趋势与偏离 |
| [34_vwap_breakout.py](strategies/34_vwap_breakout.py) | VWAP 突破策略 | 价格带量突破 VWAP 后顺势跟进 |
| [37_volatility_breakout.py](strategies/37_volatility_breakout.py) | 波动率突破策略 | ATR 波动率通道突破确认趋势启动 |
| [39_vwap_breakout_volume.py](strategies/39_vwap_breakout_volume.py) | 成交量加权价格突破策略 | 价格突破叠加成交量放大过滤假突破 |
| [57_adaptive_volatility_breakout.py](strategies/57_adaptive_volatility_breakout.py) | 自适应波动率突破策略 | 波动率越高仓位越低，止损止盈随波动环境调整 |
| [65_fractal_dimension_breakout.py](strategies/65_fractal_dimension_breakout.py) | 分形维度过滤突破策略 | 用分形维度识别趋势化行情，仅在价格突破且路径效率较高时入场 |
| [67_squeeze_channel_breakout.py](strategies/67_squeeze_channel_breakout.py) | 窄幅压缩通道突破策略 | 先识别布林带宽收缩，再等待价格突破近期通道并配合放量确认 |
| [68_range_expansion_index.py](strategies/68_range_expansion_index.py) | 区间扩张强度突破策略 | 用真实波幅扩张和短期动量判断突破质量，过滤弱波动假突破 |
| [89_time_window_breakout.py](strategies/89_time_window_breakout.py) | 交易时段窗口突破策略 | 只在预设活跃时段响应突破信号，降低低流动性时段的假信号 |

### 均值回归与震荡反转类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [03_rsi_mean_reversion.py](strategies/03_rsi_mean_reversion.py) | RSI 均值回归策略 | RSI < 30 超卖做多、RSI > 70 超买做空 |
| [07_kdj_signal.py](strategies/07_kdj_signal.py) | KDJ 随机指标策略 | K/D/J 线超买超卖，捕捉短期反转 |
| [11_mean_reversion_zscore.py](strategies/11_mean_reversion_zscore.py) | Z-Score 均值回归策略 | 价格偏离均值 N 个标准差后等待回归 |
| [12_grid_trading.py](strategies/12_grid_trading.py) | 网格交易策略 | 价格区间内按网格间距自动挂单买卖 |
| [17_stochastic_rsi.py](strategies/17_stochastic_rsi.py) | 随机 RSI 策略 | 对 RSI 再做随机处理，提高超买超卖敏感度 |
| [18_bollinger_mean_reversion.py](strategies/18_bollinger_mean_reversion.py) | 布林带均值回归策略 | 价格触及布林带极端区间后做回归交易 |
| [18_vwap_mean_reversion.py](strategies/18_vwap_mean_reversion.py) | VWAP 日内均值回归策略 | 围绕日内 VWAP 偏离做回归，尾盘控制隔夜风险 |
| [19_williams_r.py](strategies/19_williams_r.py) | 威廉指标策略 | %R 超买超卖，观察短期情绪反转 |
| [23_pivot_point.py](strategies/23_pivot_point.py) | 枢轴点支撑阻力策略 | 昨日高低收计算今日支撑阻力，关键位反转 |
| [24_r_breaker.py](strategies/24_r_breaker.py) | R-Breaker 日内策略 | 6 条价格线结合突破、观察和反转信号 |
| [31_vwap_mean_reversion.py](strategies/31_vwap_mean_reversion.py) | VWAP 均值回归日内策略 | 日内 VWAP + 标准差带，价格回归至 VWAP 附近平仓 |
| [33_boll_mean_reversion.py](strategies/33_boll_mean_reversion.py) | 布林带均值回归策略 | 布林带极端偏离后的中轨回归 |
| [35_fibonacci_retracement.py](strategies/35_fibonacci_retracement.py) | 斐波那契回调策略 | 关键回调比例位结合趋势方向交易 |
| [38_boll_mean_reversion.py](strategies/38_boll_mean_reversion.py) | 布林带均值回归策略 | 上下轨极端位置反向交易，回归中轨平仓 |
| [42_bollinger_mean_reversion.py](strategies/42_bollinger_mean_reversion.py) | 布林带均值回归策略 | 布林带偏离结合 RSI 判断超买超卖 |
| [45_trend_filtered_rsi.py](strategies/45_trend_filtered_rsi.py) | 趋势过滤 RSI 震荡策略 | 趋势方向过滤后，用 RSI 寻找回调机会 |
| [69_intraday_vwap_band_reversion.py](strategies/69_intraday_vwap_band_reversion.py) | 日内 VWAP 标准差带回归策略 | 围绕 VWAP 构建动态偏离带，价格远离成交均价后等待回归 |
| [70_rsi_divergence_reversal.py](strategies/70_rsi_divergence_reversal.py) | RSI 背离反转策略 | 价格创新高低而 RSI 动能不确认时，捕捉短周期反转机会 |
| [71_boll_percent_b_reversion.py](strategies/71_boll_percent_b_reversion.py) | 布林 %B 均值回归策略 | 用 %B 衡量价格在布林带内的位置，极端偏离后回归中轨 |
| [72_volatility_contraction_reversion.py](strategies/72_volatility_contraction_reversion.py) | 波动收缩震荡回归策略 | 当 ATR 相对历史收缩时，降低追涨杀跌并交易区间内均值回归 |
| [73_atr_normalized_zscore.py](strategies/73_atr_normalized_zscore.py) | ATR 标准化 Z-Score 回归策略 | 用 ATR 标准化价格偏离，避免高波动阶段误判普通波动为极端偏离 |

### 量价资金流类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [14_volume_price_trend.py](strategies/14_volume_price_trend.py) | 量价趋势策略 | 成交量配合价格突破做信号验证 |
| [26_chaikin_money_flow.py](strategies/26_chaikin_money_flow.py) | 蔡金资金流量策略 | CMF 衡量买卖资金净流向，上穿阈值做多，下穿阈值做空 |
| [28_obv_trend.py](strategies/28_obv_trend.py) | OBV 能量潮趋势策略 | OBV 短/长均线金叉死叉，量能领先价格判断资金流向 |
| [74_mfi_money_flow_reversal.py](strategies/74_mfi_money_flow_reversal.py) | MFI 资金流反转策略 | 用资金流量指标识别量价超买超卖，寻找资金动能衰竭后的反转 |
| [75_volume_profile_value_area.py](strategies/75_volume_profile_value_area.py) | 成交密集区价值回归策略 | 用近似成交量分布估计价值区，价格远离高成交区域后做回归 |
| [76_open_interest_momentum.py](strategies/76_open_interest_momentum.py) | 持仓量动量确认策略 | 用价格动量叠加持仓量变化确认新增资金是否支持趋势延续 |
| [77_turnover_rate_breakout.py](strategies/77_turnover_rate_breakout.py) | 换手放大突破策略 | 用成交活跃度突增确认突破有效性，减少低流动性环境中的噪声交易 |
| [78_negative_volume_index.py](strategies/78_negative_volume_index.py) | 负成交量指数趋势策略 | 在低量日跟踪价格累积方向，用 NVI 均线判断主导趋势 |

### 多因子截面与组合轮动类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [27_elder_triple_screen.py](strategies/27_elder_triple_screen.py) | Elder 三屏交易系统 | 日线趋势、小时线震荡和 15 分钟入场信号分层确认 |
| [27_multi_factor_ranking.py](strategies/27_multi_factor_ranking.py) | 多因子截面排名策略 | 动量 + 波动率 + 趋势三因子截面排名，做多强势、做空弱势 |
| [46_multi_factor.py](strategies/46_multi_factor.py) | 多因子量化选股策略 | 动量、趋势、波动率、成交量四因子加权评分 |
| [48_sector_rotation_multi_factor.py](strategies/48_sector_rotation_multi_factor.py) | 截面多因子行业轮动策略 | 跨板块多因子打分，按强弱做轮动配置 |
| [49_mean_variance_portfolio.py](strategies/49_mean_variance_portfolio.py) | 均值方差最优组合策略 | 最大夏普比率组合，结合波动率目标调仓 |
| [50_volatility_skew.py](strategies/50_volatility_skew.py) | 截面波动率偏度交易策略 | 收益率偏度、波动率、动量和成交量因子共同筛选 |
| [52_multi_factor_ai_prediction.py](strategies/52_multi_factor_ai_prediction.py) | 多因子 AI 预测策略 | 融合多类因子生成预测信号，驱动品种轮动和仓位调整 |
| [54_multi_asset_long_short_hedge.py](strategies/54_multi_asset_long_short_hedge.py) | 多标的截面多空对冲策略 | 动量排名 + 趋势过滤 + 流动性过滤，构建等权多空组合 |
| [55_momentum_value_factor_composite.py](strategies/55_momentum_value_factor_composite.py) | 时序动量与截面价值因子复合策略 | 20 日动量与期限结构价值因子组合，做截面多空 |
| [56_cross_section_multi_factor_ranking.py](strategies/56_cross_section_multi_factor_ranking.py) | 截面多因子 Ranking 轮动策略 | 黑色系五品种按动量、波动率和 ADX 排名轮动 |
| [58_money_flow_rotation.py](strategies/58_money_flow_rotation.py) | 截面资金流向多空轮动策略 | CMF、持仓量背离和 VWAP 偏离共同打分轮动 |
| [59_vol_momentum_composite.py](strategies/59_vol_momentum_composite.py) | 时序波动率与截面动量复合趋势策略 | 时序信号和截面收益率双重确认，按趋势强弱调整仓位 |
| [60_cross_section_ml_ranking.py](strategies/60_cross_section_ml_ranking.py) | 截面多因子机器学习排名策略 | 用截面排名、多因子打分和机器学习思路筛选品种 |
| [62_macro_factor_rotation.py](strategies/62_macro_factor_rotation.py) | 宏观因子轮转截面策略 | 宏观因子暴露打分驱动多品种轮转 |
| [79_cross_section_risk_parity.py](strategies/79_cross_section_risk_parity.py) | 截面风险平价动量策略 | 跨品种比较风险调整后动量，偏向强趋势、低波动且流动性较好的合约 |
| [80_momentum_carry_composite.py](strategies/80_momentum_carry_composite.py) | 动量 Carry 复合轮动策略 | 把时间序列动量和近似期限结构收益结合，筛选相对更强的品种 |
| [81_term_structure_momentum_rotation.py](strategies/81_term_structure_momentum_rotation.py) | 期限结构动量轮动策略 | 用期限结构斜率代理库存预期，再与趋势动量共同决定多空轮动 |
| [82_liquidity_adjusted_momentum.py](strategies/82_liquidity_adjusted_momentum.py) | 流动性调整动量策略 | 在动量排序中惩罚成交不足的合约，降低滑点和盘口冲击风险 |
| [83_regime_switching_allocation.py](strategies/83_regime_switching_allocation.py) | 行情状态切换配置策略 | 先判断趋势/震荡状态，再在不同状态下调整动量和波动权重 |
| [91_volatility_target_position.py](strategies/91_volatility_target_position.py) | 波动率目标仓位策略 | 用风险预算约束目标手数，高波动时自动降仓、低波动趋势中适度增仓 |
| [93_adaptive_position_sizing.py](strategies/93_adaptive_position_sizing.py) | 自适应仓位 sizing 策略 | 综合趋势效率、波动目标和行情状态动态调整目标持仓规模 |

### 对冲套利与结构交易类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [47_cross_market_hedge.py](strategies/47_cross_market_hedge.py) | 跨市场对冲策略 | 基于 Z-Score 的跨品种价差套利，做多低估、做空高估 |
| [51_term_structure.py](strategies/51_term_structure.py) | 期限结构基差回归策略 | 近远月价比斜率偏离历史均值后做价差回归 |
| [53_market_maker_hedge.py](strategies/53_market_maker_hedge.py) | 跨品种做市商对冲策略 | 多品种挂单获取价差，并用相关品种对冲方向风险 |
| [61_statistical_arbitrage.py](strategies/61_statistical_arbitrage.py) | 统计套利跨品种对冲策略 | 协整检验 + Z-Score 均值回归，构建配对对冲 |
| [63_cross_industry_chain_hedge.py](strategies/63_cross_industry_chain_hedge.py) | 跨品种产业链对冲轮转策略 | 围绕产业链利润偏离进行配对对冲 |
| [84_calendar_spread_momentum.py](strategies/84_calendar_spread_momentum.py) | 跨期价差动量策略 | 跟踪近远月价差方向，价差持续扩张时顺势做跨期组合 |
| [85_crack_spread_monitor.py](strategies/85_crack_spread_monitor.py) | 裂解价差监控对冲策略 | 观察原油与燃料油价差变化，价差极端偏离时做相对价值对冲 |
| [86_intercommodity_ratio_reversion.py](strategies/86_intercommodity_ratio_reversion.py) | 跨品种比价回归策略 | 用豆粕/豆油比价衡量产业链相对定价，偏离历史区间后做回归 |
| [87_pairs_beta_neutral.py](strategies/87_pairs_beta_neutral.py) | Beta 中性配对交易策略 | 用滚动 Beta 调整配对合约敞口，在残差偏离时构建中性对冲 |
| [88_cointegration_residual_breakout.py](strategies/88_cointegration_residual_breakout.py) | 协整残差突破策略 | 把残差看作可交易状态，当残差突破长期区间时顺势持有价差 |

---

## 🛠️ 使用说明

1. **克隆仓库**

   ```bash
   git clone https://github.com/ringoshinnytech/tqsdk-strategies.git
   cd tqsdk-strategies
   ```

2. **安装依赖**

   ```bash
   pip install tqsdk -U
   ```

3. **配置账户**  
   在策略文件中替换 `YOUR_ACCOUNT` / `YOUR_PASSWORD` 为你的快期账户信息。  
   注册快期账户：https://account.shinnytech.com/

4. **运行策略（模拟模式）**

   ```bash
   python strategies/01_double_ma.py
   ```

---

## 📅 更新计划

---

## ⚠️ 风险提示

- 本仓库所有策略**仅供学习和研究使用**，不构成任何投资建议
- 量化交易存在亏损风险，请在充分理解策略逻辑后再用于实盘
- 建议先使用**模拟账户**充分测试后，再考虑实盘运行
- 过去的回测表现不代表未来的实际收益

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。  
TqSdk 本身基于 [Apache-2.0 License](https://github.com/shinnytech/tqsdk-python/blob/master/LICENSE)。
