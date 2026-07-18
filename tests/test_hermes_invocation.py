from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from tqe.workshop.hermes_invocation import _run_agent_with_product_config


class HermesInvocationTests(unittest.TestCase):
    def test_product_bridge_passes_configured_reasoning_effort_to_agent(self) -> None:
        captured: dict[str, object] = {}

        class FakeAgent:
            def __init__(self, **kwargs: object) -> None:
                captured.update(kwargs)

            def chat(self, prompt: str) -> str:
                captured["prompt"] = prompt
                return "ok"

        hermes_cli = types.ModuleType("hermes_cli")
        config = types.ModuleType("hermes_cli.config")
        config.load_config = lambda: {
            "model": {"provider": "openai-codex", "default": "gpt-5.5"},
            "agent": {"reasoning_effort": "xhigh"},
        }
        fallback = types.ModuleType("hermes_cli.fallback_config")
        fallback.get_fallback_chain = lambda _config: []
        models = types.ModuleType("hermes_cli.models")
        models.detect_provider_for_model = lambda _model, _provider: None
        oneshot = types.ModuleType("hermes_cli.oneshot")
        oneshot._create_session_db_for_oneshot = lambda: object()
        oneshot._normalize_toolsets = lambda value: value
        oneshot._oneshot_clarify_callback = lambda _question, _choices=None: "continue"
        runtime = types.ModuleType("hermes_cli.runtime_provider")
        runtime.resolve_runtime_provider = lambda **_kwargs: {
            "api_key": "subscription-token-placeholder",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "credential_pool": object(),
        }
        constants = types.ModuleType("hermes_constants")
        constants.parse_reasoning_effort = lambda effort: (
            {"enabled": True, "effort": effort} if effort == "xhigh" else None
        )
        run_agent = types.ModuleType("run_agent")
        run_agent.AIAgent = FakeAgent

        fake_modules = {
            "hermes_cli": hermes_cli,
            "hermes_cli.config": config,
            "hermes_cli.fallback_config": fallback,
            "hermes_cli.models": models,
            "hermes_cli.oneshot": oneshot,
            "hermes_cli.runtime_provider": runtime,
            "hermes_constants": constants,
            "run_agent": run_agent,
        }
        with patch.dict(sys.modules, fake_modules):
            result = _run_agent_with_product_config(
                "probe",
                model="gpt-5.6-sol",
                provider="openai-codex",
                toolsets=["mcp-priori_tactical"],
                max_output_tokens=32768,
            )

        self.assertEqual("ok", result)
        self.assertEqual({"enabled": True, "effort": "xhigh"}, captured["reasoning_config"])
        self.assertEqual(32768, captured["max_tokens"])
        self.assertEqual("openai-codex", captured["provider"])
        self.assertEqual("gpt-5.6-sol", captured["model"])

    def test_product_bridge_rejects_unknown_configured_effort(self) -> None:
        constants = types.ModuleType("hermes_constants")
        constants.parse_reasoning_effort = lambda _effort: None
        with patch.dict(sys.modules, {"hermes_constants": constants}):
            with self.assertRaisesRegex(ValueError, "rejected configured reasoning_effort 'max'"):
                from tqe.workshop.hermes_invocation import configured_reasoning_config

                configured_reasoning_config({"agent": {"reasoning_effort": "max"}})


if __name__ == "__main__":
    unittest.main()
