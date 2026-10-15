"""Complete provider inputs must fit before every model call."""
from types import SimpleNamespace

import pytest

from apps.helios.console.conversation import ConversationService, MCPClientConfig
from helios_core.llm import ToolCall, ToolTurn


@pytest.mark.anyio
async def test_input_budget_preserves_history_and_stops_before_provider():
    class LLM:
        def tool_turn(self, *args):
            pytest.fail("oversized complete input must not reach provider")
    service = ConversationService(LLM(), MCPClientConfig("http://unused", "token", "secret", 30), max_input_tokens=100)
    result = await service._tool_loop(None, [], "sales", "question", history=[{"role": "user", "content": "context " * 10000}])
    assert result["failure"]["code"] == "conversation_input_budget_exceeded"


@pytest.mark.anyio
async def test_accumulated_tool_results_are_counted_before_next_provider_call():
    class LLM:
        calls = 0
        def tool_turn(self, *args):
            self.calls += 1
            assert self.calls == 1
            return ToolTurn("", (ToolCall("one", "resolve_context", {}),), "tool_use", 0, 0)
    class Session:
        async def call_tool(self, *args, **kwargs):
            return SimpleNamespace(structured_content={"evidence": "x" * 10000})
    llm = LLM()
    service = ConversationService(llm, MCPClientConfig("http://unused", "token", "secret", 30), max_input_tokens=6000)
    result = await service._tool_loop(Session(), [{"name": "resolve_context", "inputSchema": {"properties": {}}}], "sales", "question")
    assert llm.calls == 1
    assert result["failure"]["code"] == "conversation_input_budget_exceeded"


@pytest.mark.parametrize("budget", [0, -1, True, 1.5, "10"])
def test_input_budget_requires_positive_integer(budget):
    with pytest.raises(ValueError):
        ConversationService(object(), MCPClientConfig("http://unused", "token", "secret"), max_input_tokens=budget)


@pytest.mark.anyio
@pytest.mark.parametrize("count", [-1, True, 1.5, None, "10"])
async def test_invalid_token_counter_fails_before_provider(count):
    class LLM:
        def tool_turn(self, *args):
            pytest.fail("invalid token counter must fail before provider")
    service = ConversationService(LLM(), MCPClientConfig("http://unused", "token", "secret"), token_counter=lambda text: count)
    result = await service._tool_loop(None, [], "sales", "question")
    assert result["failure"]["code"] == "conversation_input_budget_invalid"


@pytest.mark.anyio
async def test_document_tools_are_not_exposed_or_executed():
    class LLM:
        def tool_turn(self, system, messages, tools):
            assert {tool["name"] for tool in tools} == {"resolve_context"}
            assert "Document questions are unsupported" in system
            assert "search_evidence" not in system
            return ToolTurn("", (ToolCall("one", "search_evidence", {}),), "tool_use")
    class Session:
        async def call_tool(self, *args, **kwargs):
            pytest.fail("document tools must not execute")
    service = ConversationService(LLM(), MCPClientConfig("http://unused", "token", "secret"))
    result = await service._tool_loop(Session(), [{"name": "resolve_context"}, {"name": "search_evidence"}, {"name": "entity_claims"}], "sales", "question")
    assert result["failure"]["code"] == "unknown_tool"
