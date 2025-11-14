"""Test completion handler (short)."""
import sys
import importlib.util
import os
from dataclasses import dataclass

spec = importlib.util.spec_from_file_location("mcp_server_module", os.path.join(os.path.dirname(__file__), "server.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

@dataclass
class MockCompletionArgument:
    text: str

prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "معنای زندگی چیست؟"
print(f"Prompt: {prompt}\n")

try:
    arg = MockCompletionArgument(text=prompt)
    res = mod.provide_completion(None, arg, None)
    if not res:
        print("Handler returned None")
    else:
        print(f"Completion received ({len(res.values)}):")
        for i, v in enumerate(res.values, 1):
            print(f"  [{i}] {v}")
        print(f"Total: {res.total}, Has more: {res.hasMore}")
except Exception as e:
    print("Error:", e)
    import traceback
    traceback.print_exc()
