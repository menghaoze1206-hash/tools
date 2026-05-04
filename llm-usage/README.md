# llm-usage

查询 DeepSeek API 余额的 CLI 工具。

## 快速开始

```bash
pip3 install -r requirements.txt
python3 cli.py balance
```

## 命令

```bash
python3 cli.py balance          # 查询余额
python3 cli.py --json balance   # JSON 格式输出
python3 cli.py help             # 显示帮助
```

## 环境变量

```bash
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_API_BASE=https://api.deepseek.com        # 可选
DEEPSEEK_MONTHLY_BUDGET_CNY=100                   # 可选
DEEPSEEK_LOW_BALANCE_CNY=10                       # 可选，默认 10
DEEPSEEK_TARGET_BALANCE_CNY=50                    # 可选，默认 50
DEEPSEEK_TOP_UP_URL=https://platform.deepseek.com/top_up  # 可选
```

如果没有 `DEEPSEEK_API_KEY`，工具会尝试从 `~/.claude/settings.json` 读取
`ANTHROPIC_AUTH_TOKEN`（当 `ANTHROPIC_BASE_URL` 或 `ANTHROPIC_MODEL` 指向 DeepSeek 时）。

余额低于 `DEEPSEEK_LOW_BALANCE_CNY` 时会自动提示充值。

## 测试

```bash
python3 -m pytest test_main.py -q
```

## Docker

```bash
docker build -t llm-usage .
docker run --rm llm-usage balance
docker run --rm -e DEEPSEEK_API_KEY=your-key llm-usage balance
```
