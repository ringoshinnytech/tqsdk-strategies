# TqSdk 量化交易策略集

基于 [天勤量化 TqSdk](https://github.com/shinnytech/tqsdk-python) 实现的期货量化交易策略示例集合。

## 策略列表

| 策略文件 | 策略名称 | 类型 | 难度 |
|---------|---------|------|------|
| [01_double_ma.py](strategies/01_double_ma.py) | 双均线趋势策略 | 趋势跟踪 | 初级 |
| [02_boll_breakout.py](strategies/02_boll_breakout.py) | 布林带突破策略 | 趋势突破 | 初级 |
| [03_rsi_mean_reversion.py](strategies/03_rsi_mean_reversion.py) | RSI 均值回归策略 | 均值回归 | 初级 |
| [04_dual_thrust.py](strategies/04_dual_thrust.py) | Dual Thrust 日内突破策略 | 日内突破 | 中级 |
| [05_turtle_trading.py](strategies/05_turtle_trading.py) | 海龟交易策略 | 趋势跟踪 | 中级 |

## 环境要求

```bash
pip install tqsdk -U
```

- Python >= 3.8
- 需要注册 [快期账户](https://account.shinnytech.com/) 并替换代码中的账户信息

## 使用说明

1. 克隆本仓库
2. 安装 tqsdk：`pip install tqsdk -U`
3. 在各策略文件中替换 `YOUR_ACCOUNT` / `YOUR_PASSWORD` 为你的快期账户信息
4. 运行对应策略：`python strategies/01_double_ma.py`

> ⚠️ **风险提示**：本仓库策略仅供学习参考，不构成任何投资建议。量化交易存在风险，请在充分了解策略逻辑后谨慎使用。

## 参考资料

- [TqSdk 官方文档](https://doc.shinnytech.com/tqsdk/latest/)
- [TqSdk GitHub 仓库](https://github.com/shinnytech/tqsdk-python)
- [天勤量化社区](https://www.shinnytech.com/)
