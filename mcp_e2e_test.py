"""E2E test (short)."""
import importlib.util
import os
import asyncio

spec = importlib.util.spec_from_file_location("mcp_server_module", os.path.join(os.path.dirname(__file__), "server.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print("Loaded server module")

if hasattr(mod, "list_tools_handler"):
    try:
        tools = mod.list_tools_handler(None)
        print("Tools listed:")
        for t in tools:
            print(f" - {t.name}: {t.description}")
    except Exception as e:
        print("list_tools handler error:", e)
else:
    print("No list_tools_handler; skipping")

async def run_math_tests():
    try:
        print("Calling math_op (mul 3*4)")
        res = await mod.math_op("math_op", {"operation": "mul", "a": 3, "b": 4})
        print("Result:", res)

        print("Calling math_op (div 10/2)")
        res = await mod.math_op("math_op", {"operation": "div", "a": 10, "b": 2})
        print("Result:", res)
    except Exception as e:
        print("math_op error:", e)

asyncio.run(run_math_tests())
