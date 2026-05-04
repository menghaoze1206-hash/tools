import pytest

import cli
import main


def test_get_deepseek_key_returns_env_var(monkeypatch):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "sk-test")
    key, source = main._get_deepseek_key()
    assert key == "sk-test"
    assert source == "DEEPSEEK_API_KEY"


def test_get_deepseek_key_reads_claude_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "")
    settings = tmp_path / "settings.json"
    settings.write_text(
        '{"env":{"ANTHROPIC_BASE_URL":"https://api.deepseek.com",'
        '"ANTHROPIC_MODEL":"deepseek-v4-pro[1m]",'
        '"ANTHROPIC_AUTH_TOKEN":"sk-from-claude"}}'
    )
    monkeypatch.setattr(main, "CLAUDE_SETTINGS_FILE", settings)

    key, source = main._get_deepseek_key()
    assert key == "sk-from-claude"
    assert source == str(settings)


def test_get_deepseek_key_strips_bearer_prefix(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "")
    settings = tmp_path / "settings.json"
    settings.write_text(
        '{"env":{"ANTHROPIC_BASE_URL":"https://api.deepseek.com",'
        '"ANTHROPIC_AUTH_TOKEN":"Bearer sk-bearer-token"}}'
    )
    monkeypatch.setattr(main, "CLAUDE_SETTINGS_FILE", settings)

    key, _ = main._get_deepseek_key()
    assert key == "sk-bearer-token"


def test_summarize_balance():
    payload = {
        "is_available": True,
        "balance_infos": [
            {
                "currency": "CNY",
                "total_balance": "42.5",
                "granted_balance": "2.5",
                "topped_up_balance": "40",
            }
        ],
    }
    result = main._summarize_deepseek_balance(payload)
    assert result["is_available"] is True
    assert result["primary"]["currency"] == "cny"
    assert result["primary"]["total_balance"] == 42.5


def test_build_recharge_advice(monkeypatch):
    monkeypatch.setattr(main, "DEEPSEEK_LOW_BALANCE_CNY", "10")
    monkeypatch.setattr(main, "DEEPSEEK_TARGET_BALANCE_CNY", "50")
    monkeypatch.setattr(main, "DEEPSEEK_TOP_UP_URL", "https://platform.deepseek.com/top_up")

    summary = {
        "is_available": True,
        "balances": [],
        "primary": {"currency": "cny", "total_balance": 8.0},
    }
    result = main._build_deepseek_recharge_advice(summary, "DEEPSEEK_API_KEY")
    assert result["needs_recharge"] is True
    assert result["suggested_top_up"] == {"currency": "cny", "value": 42.0}


def test_cli_balance_outputs_text(monkeypatch, capsys):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setattr(main, "DEEPSEEK_MONTHLY_BUDGET_CNY", "100")

    def fake_request(api_key):
        assert api_key == "sk-deepseek-test"
        return {
            "is_available": True,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "42.5",
                    "granted_balance": "2.5",
                    "topped_up_balance": "40",
                }
            ],
        }

    monkeypatch.setattr(main, "_request_deepseek_balance", fake_request)

    code = cli.main(["balance"])
    assert code == 0
    output = capsys.readouterr().out
    assert "DeepSeek 余额" in output
    assert "42.5000 CNY" in output
    assert "预算:" in output


def test_cli_balance_prints_top_up_when_low(monkeypatch, capsys):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setattr(main, "DEEPSEEK_LOW_BALANCE_CNY", "10")
    monkeypatch.setattr(main, "DEEPSEEK_TARGET_BALANCE_CNY", "50")
    monkeypatch.setattr(main, "DEEPSEEK_TOP_UP_URL", "https://platform.deepseek.com/top_up")

    def fake_request(api_key):
        return {
            "is_available": True,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "8",
                    "granted_balance": "0",
                    "topped_up_balance": "8",
                }
            ],
        }

    monkeypatch.setattr(main, "_request_deepseek_balance", fake_request)

    code = cli.main(["balance"])
    assert code == 0
    output = capsys.readouterr().out
    assert "余额不足" in output
    assert "建议充值: 42.0000 CNY" in output
    assert "充值地址: https://platform.deepseek.com/top_up" in output


def test_cli_balance_json_output(monkeypatch, capsys):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "sk-deepseek-test")

    def fake_request(api_key):
        return {
            "is_available": True,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "99.5",
                    "granted_balance": "0",
                    "topped_up_balance": "99.5",
                }
            ],
        }

    monkeypatch.setattr(main, "_request_deepseek_balance", fake_request)

    code = cli.main(["--json", "balance"])
    assert code == 0
    output = capsys.readouterr().out
    assert '"provider": "deepseek"' in output
    assert '"total_balance": 99.5' in output


def test_cli_help_outputs_text(capsys):
    code = cli.main(["help"])
    assert code == 0
    output = capsys.readouterr().out
    assert "llm-usage" in output
    assert "查询余额" in output


def test_cli_no_command_runs_balance(monkeypatch, capsys):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "sk-test")

    def fake_request(api_key):
        return {
            "is_available": True,
            "balance_infos": [
                {"currency": "CNY", "total_balance": "50", "granted_balance": "0", "topped_up_balance": "50"}
            ],
        }

    monkeypatch.setattr(main, "_request_deepseek_balance", fake_request)
    code = cli.main([])
    assert code == 0
    assert "DeepSeek 余额" in capsys.readouterr().out
