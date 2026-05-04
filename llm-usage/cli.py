#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
from typing import Optional

import main as core


class CliError(Exception):
    pass


def money(value: object, currency: str = "usd") -> str:
    return f"{float(value or 0):.4f} {currency.upper()}"


def require_deepseek_key() -> tuple[str, str]:
    api_key, key_source = core._get_deepseek_key()
    if not api_key:
        raise CliError(
            "未配置 DEEPSEEK_API_KEY。可以设置环境变量，或在 Claude settings.json 中配置 DeepSeek 的 ANTHROPIC_AUTH_TOKEN。"
        )
    return api_key, key_source


def api_error(prefix: str, error: urllib.error.HTTPError) -> CliError:
    detail = core._extract_api_error(error.read().decode("utf-8", errors="replace"))
    return CliError(f"{prefix}: HTTP {error.code}: {detail}")


def format_balance(data: dict[str, object]) -> str:
    lines = [
        "DeepSeek 余额",
        f"密钥来源: {data.get('key_source')}",
        f"账户状态: {'可用' if data.get('is_available') else '不可用'}",
    ]
    balances = data.get("balances", [])
    for item in balances:
        if not isinstance(item, dict):
            continue
        currency = str(item.get("currency") or "cny")
        lines.append(
            f"- {currency.upper()}: 总余额 {money(item.get('total_balance'), currency)}，赠送 {money(item.get('granted_balance'), currency)}，充值 {money(item.get('topped_up_balance'), currency)}"
        )
    budget = data.get("budget")
    if isinstance(budget, dict) and not budget.get("error"):
        currency = str(budget.get("currency") or "cny")
        lines.append(
            f"预算: 已用 {money(budget.get('spent'), currency)} / {money(budget.get('budget'), currency)}，剩余 {money(budget.get('remaining'), currency)}"
        )
    recharge = data.get("recharge_advice")
    if isinstance(recharge, dict) and recharge.get("needs_recharge"):
        suggestion = recharge.get("suggested_top_up")
        lines.append("余额不足: 建议前往 DeepSeek 官方页面手动充值。")
        if isinstance(suggestion, dict):
            lines.append(f"建议充值: {money(suggestion.get('value'), str(suggestion.get('currency') or 'cny'))}")
        lines.append(f"充值地址: {recharge.get('top_up_url')}")
    return "\n".join(lines)


def get_balance_data() -> dict[str, object]:
    api_key, key_source = require_deepseek_key()
    try:
        payload = core._request_deepseek_balance(api_key)
    except urllib.error.HTTPError as e:
        raise api_error("DeepSeek 余额查询失败", e) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise CliError(f"无法连接 DeepSeek 余额接口: {e}") from e
    summary = core._summarize_deepseek_balance(payload)
    primary = summary["primary"]
    data = {
        "provider": "deepseek",
        "scope": "api_balance",
        "key_source": key_source,
        "is_available": summary["is_available"],
        "balances": summary["balances"],
        "primary": primary,
        "budget": core._budget_summary(
            "cny",
            core.DEEPSEEK_MONTHLY_BUDGET_CNY,
            available=primary["total_balance"] if primary else 0,
        ),
    }
    data["recharge_advice"] = core._build_deepseek_recharge_advice(summary, key_source)
    return data


def command_balance(args: argparse.Namespace) -> dict[str, object]:
    return get_balance_data()


HELP_TEXT = """\
llm-usage - 查询 DeepSeek API 余额

用法:
  cli.py              直接查询余额
  cli.py --json       JSON 格式输出
  cli.py help         显示此帮助

环境变量:
  DEEPSEEK_API_KEY            DeepSeek API 密钥
  DEEPSEEK_API_BASE           API 地址 (默认 https://api.deepseek.com)
  DEEPSEEK_MONTHLY_BUDGET_CNY 月度预算 (可选)
  DEEPSEEK_LOW_BALANCE_CNY    低余额提醒阈值 (默认 10)
  DEEPSEEK_TARGET_BALANCE_CNY 目标充值金额 (默认 50)
  DEEPSEEK_TOP_UP_URL         充值页面地址

如果没有 DEEPSEEK_API_KEY，工具会尝试从 ~/.claude/settings.json 读取
ANTHROPIC_AUTH_TOKEN（当 ANTHROPIC_BASE_URL 或 ANTHROPIC_MODEL 指向 DeepSeek 时）。"""


def command_help(args: argparse.Namespace) -> dict[str, object]:
    print(HELP_TEXT)
    return {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="llm-usage", add_help=False)
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    subparsers = parser.add_subparsers(dest="command")

    balance_parser = subparsers.add_parser("balance", help="查询 DeepSeek API 余额")
    balance_parser.set_defaults(handler=command_balance, formatter=format_balance)

    help_parser = subparsers.add_parser("help", help="显示帮助信息")
    help_parser.set_defaults(handler=command_help, formatter=lambda _: "")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        args.handler = command_balance
        args.formatter = format_balance
    try:
        data = args.handler(args)
    except CliError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    if args.command == "help":
        return 0
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(args.formatter(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
