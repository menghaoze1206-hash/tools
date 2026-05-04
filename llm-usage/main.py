import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MONTHLY_BUDGET_CNY = os.environ.get("DEEPSEEK_MONTHLY_BUDGET_CNY", "")
DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_BALANCE_URL = f"{DEEPSEEK_API_BASE}/user/balance"
DEEPSEEK_LOW_BALANCE_CNY = os.environ.get("DEEPSEEK_LOW_BALANCE_CNY", "10")
DEEPSEEK_TARGET_BALANCE_CNY = os.environ.get("DEEPSEEK_TARGET_BALANCE_CNY", "50")
DEEPSEEK_TOP_UP_URL = os.environ.get("DEEPSEEK_TOP_UP_URL", "https://platform.deepseek.com/top_up").strip()
CLAUDE_SETTINGS_FILE = Path.home() / ".claude" / "settings.json"


def _load_claude_env() -> dict[str, str]:
    try:
        data = json.loads(CLAUDE_SETTINGS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    env = data.get("env", {})
    if not isinstance(env, dict):
        return {}
    return {str(k): str(v) for k, v in env.items()}


def _get_deepseek_key() -> tuple[str, str]:
    if DEEPSEEK_API_KEY:
        return DEEPSEEK_API_KEY, "DEEPSEEK_API_KEY"

    claude_env = _load_claude_env()
    base_url = claude_env.get("ANTHROPIC_BASE_URL", "")
    model = claude_env.get("ANTHROPIC_MODEL", "")
    token = claude_env.get("ANTHROPIC_AUTH_TOKEN", "")
    host = urllib.parse.urlparse(base_url).netloc.lower()
    if token and ("deepseek" in host or "deepseek" in model.lower()):
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        return token, str(CLAUDE_SETTINGS_FILE)

    return "", ""


def _extract_api_error(body: str) -> str:
    try:
        data = json.loads(body)
        error = data.get("error", {})
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if isinstance(error, str):
            return error
        if data.get("message"):
            return str(data["message"])
    except json.JSONDecodeError:
        pass
    return body[:500]


def _budget_summary(
    currency: str,
    budget_value: str,
    spent: Optional[float] = None,
    available: Optional[float] = None,
) -> Optional[dict[str, object]]:
    if not budget_value:
        return None
    try:
        budget = float(budget_value)
    except ValueError:
        return {"error": "预算环境变量不是有效数字"}
    if available is None:
        spent_value = float(spent or 0)
        remaining = budget - spent_value
    else:
        remaining = float(available)
        spent_value = budget - remaining
    return {
        "currency": currency,
        "budget": round(budget, 6),
        "spent": round(spent_value, 6),
        "remaining": round(remaining, 6),
    }


def _optional_float(value: str) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _request_deepseek_balance(api_key: str) -> dict[str, object]:
    request = urllib.request.Request(
        DEEPSEEK_BALANCE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _summarize_deepseek_balance(payload: dict[str, object]) -> dict[str, object]:
    balances = []
    for item in payload.get("balance_infos", []):
        if not isinstance(item, dict):
            continue
        currency = str(item.get("currency") or "CNY").lower()
        total = float(item.get("total_balance") or 0)
        granted = float(item.get("granted_balance") or 0)
        topped_up = float(item.get("topped_up_balance") or 0)
        balances.append({
            "currency": currency,
            "total_balance": round(total, 6),
            "granted_balance": round(granted, 6),
            "topped_up_balance": round(topped_up, 6),
        })
    primary = next((item for item in balances if item["currency"] == "cny"), None)
    if primary is None and balances:
        primary = balances[0]
    return {
        "is_available": bool(payload.get("is_available", False)),
        "balances": balances,
        "primary": primary,
    }


def _build_deepseek_recharge_advice(
    summary: dict[str, object],
    key_source: str,
) -> dict[str, object]:
    primary = summary.get("primary")
    balance = float(primary.get("total_balance") or 0) if isinstance(primary, dict) else 0.0
    threshold = _optional_float(DEEPSEEK_LOW_BALANCE_CNY)
    target = _optional_float(DEEPSEEK_TARGET_BALANCE_CNY)
    needs_recharge = threshold is not None and balance < threshold
    suggested_top_up = None
    if needs_recharge and target is not None and target > balance:
        suggested_top_up = {
            "currency": "cny",
            "value": round(target - balance, 2),
        }

    return {
        "supported": True,
        "automatic_recharge_supported": False,
        "provider": "deepseek",
        "scope": "recharge_advice",
        "key_source": key_source,
        "is_available": summary["is_available"],
        "balance": {
            "currency": "cny",
            "value": round(balance, 6),
        },
        "low_balance_threshold": (
            {"currency": "cny", "value": round(threshold, 6)}
            if threshold is not None else None
        ),
        "target_balance": (
            {"currency": "cny", "value": round(target, 6)}
            if target is not None else None
        ),
        "needs_recharge": needs_recharge,
        "suggested_top_up": suggested_top_up,
        "top_up_url": DEEPSEEK_TOP_UP_URL,
        "note": "DeepSeek 官方没有公开自动充值 API；这里仅根据余额生成充值建议，支付需在官方平台手动确认。",
    }
