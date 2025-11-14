import os
import requests
from dotenv import load_dotenv
from mcp.server import Server
import re
import mcp.types as types
from mcp.types import TextContent, Completion

load_dotenv()

POLY_API = os.getenv("POLYGON_API_KEY")
BASE_URL = os.getenv("POLYGON_BASE_URL", "https://api.polygon.io")

if not POLY_API:
    raise ValueError("POLYGON_API_KEY not found in environment variables.")

server = Server("polygon-mcp")

# math tool: mul/div
math_input_schema = {
    "type": "object",
    "properties": {
        "operation": {"type": "string", "enum": ["mul", "div"]},
        "a": {"type": "number"},
        "b": {"type": "number"}
    },
    "required": ["operation", "a", "b"],
    "additionalProperties": False,
}

math_output_schema = {
    "type": "object",
    "properties": {"result": {"type": "number"}},
    "required": ["result"],
    "additionalProperties": False,
}


@server.call_tool()
async def math_op(tool_name: str, arguments: dict):
    # supports mul/div
    op = arguments.get("operation")
    a = arguments.get("a")
    b = arguments.get("b")

    if op == "mul":
        res = a * b
    elif op == "div":
        if b == 0:
            raise ValueError("division by zero")
        res = a / b
    else:
        raise ValueError(f"unsupported operation: {op}")

    return {"result": res}

# polygon helper
def polygon_get(path: str, params: dict = None):
    if params is None:
        params = {}

    params["apiKey"] = POLY_API
    url = f"{BASE_URL}/{path.lstrip('/')}"
    r = requests.get(url, params=params, timeout=10)

    if r.status_code != 200:
        raise RuntimeError(f"Polygon API error {r.status_code}: {r.text}")

    return r.json()


@server.call_tool()
def get_price(symbol: str):
    try:
        try:
            data = polygon_get(f"v1/last/crypto/{symbol}")
            return TextContent(type="text", text=str(data))
        except:
            pass

        # Fallback to prev close
        data = polygon_get(f"v2/aggs/ticker/{symbol}/prev")
        return TextContent(type="text", text=str(data))

    except Exception as e:
        return TextContent(type="text", text=f"Error: {e}")


@server.call_tool()
def proxy(path: str, query: dict = None):
    try:
        data = polygon_get(path, params=query)
        return TextContent(type="text", text=str(data))
    except Exception as e:
        return TextContent(type="text", text=f"Error: {e}")


@server.call_tool()
def get_prev_close(symbol: str):
    try:
        data = polygon_get(f"v2/aggs/ticker/{symbol}/prev")
        return TextContent(type="text", text=str(data))
    except Exception as e:
        return TextContent(type="text", text=f"Error: {e}")


# LLM backend (Liara)

# Read Liara/OpenAI-compatible endpoint and model from environment.
LIARA_API_KEY = os.getenv("LIARA_API_KEY")
LIARA_BASE_URL = os.getenv(
    "LIARA_BASE_URL",
    "https://ai.liara.ir/api/6905efdecff1b902db902bda/v1",
)
LIARA_MODEL = os.getenv("LIARA_MODEL", "openai/gpt-4o-mini")


def _call_liara_chat(user_content: str) -> str:
    # call Liara chat endpoint
    if not LIARA_API_KEY:
        raise RuntimeError("LIARA_API_KEY not set in environment")

    url = f"{LIARA_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LIARA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LIARA_MODEL,
        "messages": [{"role": "user", "content": user_content}],
        "temperature": 0.0,
        "max_tokens": 512,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"LLM request failed {r.status_code}: {r.text}")

    data = r.json()

    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        try:
            return data["choices"][0]["text"]
        except Exception:
            raise RuntimeError(f"Unexpected LLM response shape: {data}")


# MCP completion handler
@server.completion()
def provide_completion(ref, argument, context):
    # provide completion; include market data if present
    # extract prompt
    try:
        if argument is None:
            prompt = ""
        elif isinstance(argument, str):
            prompt = argument
        else:
            # Try common attribute/property names
            prompt = getattr(argument, "text", None) or getattr(argument, "value", None) or str(argument)
    except Exception:
        prompt = str(argument)

    if not prompt:
        return None

    # detect tickers (up to 3)
    tickers = []
    for m in re.finditer(r"\b([A-Z]{1,5}(?::[A-Z]{3,6})?|[A-Z]{2,6}[:][A-Z]{3,6})\b", prompt):
        t = m.group(1)
        if t not in tickers:
            tickers.append(t)
        if len(tickers) >= 3:
            break

    market_context_lines = []
    for t in tickers:
        try:
            # fetch market data
            data = None
            if ":" in t or t.startswith("X:") or t.upper().endswith("USD"):
                # Use proxy style path for crypto pairs: X:BTCUSD
                try:
                    data = polygon_get(f"v1/last/crypto/{t}")
                except Exception:
                    data = polygon_get(f"v2/aggs/ticker/{t}/prev")
            else:
                try:
                    data = polygon_get(f"v1/last/crypto/{t}")
                except Exception:
                    data = polygon_get(f"v2/aggs/ticker/{t}/prev")

            market_context_lines.append(f"{t}: {data}")
        except Exception as e:
            market_context_lines.append(f"{t}: error fetching data ({e})")

    # build system message
    if market_context_lines:
        system_msg = (
            "The following market data was fetched and is provided for context:\n"
            + "\n".join(market_context_lines)
            + "\nUse this data to answer the user's query where relevant."
        )
    else:
        system_msg = "You are a helpful assistant."

    # compose chat input
    chat_input = system_msg + "\n\nUser prompt:\n" + prompt

    try:
        completion_text = _call_liara_chat(chat_input)
        return Completion(values=[completion_text], total=1, hasMore=False)
    except Exception:
        return None

if __name__ == "__main__":
    # Run an stdio-backed MCP server using anyio. This matches the installed
    # `mcp` package' expected API where Server.run requires read/write streams
    # and initialization options.
    import anyio
    from mcp.server.stdio import stdio_server
    from mcp.server.models import InitializationOptions

    init_options = server.create_initialization_options()

    async def _main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, init_options)

    anyio.run(_main)
