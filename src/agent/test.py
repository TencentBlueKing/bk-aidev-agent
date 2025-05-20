from langgraph.prebuilt import create_react_agent


def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


create_react_agent(model="anthropic:claude-3-7-sonnet", tools=[multiply])
