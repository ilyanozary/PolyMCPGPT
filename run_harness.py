"""Run server tool functions directly (simple harness)."""
import sys
from typing import Optional

import importlib.util
import os
spec = importlib.util.spec_from_file_location("mcp_server_module", os.path.join(os.path.dirname(__file__), "server.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

symbol = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TEST_SYMBOL", "AAPL")

print("Using symbol:", symbol)

def print_content(res):
    try:
        print("->", getattr(res, "text", repr(res)))
    except Exception:
        print(repr(res))

try:
    print("Calling get_price...")
    r = mod.get_price(symbol)
    print_content(r)
except Exception as e:
    print("get_price error:", e)

try:
    print("Calling get_prev_close...")
    r = mod.get_prev_close(symbol)
    print_content(r)
except Exception as e:
    print("get_prev_close error:", e)

try:
    print("Calling proxy for BTCUSD prev...")
    r = mod.proxy("v2/aggs/ticker/X:BTCUSD/prev")
    print_content(r)
except Exception as e:
    print("proxy error:", e)

print("Done.")
