from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
import logging
import os
import re
import asyncio
from dataclasses import dataclass
import requests

# import the server module (our handlers)
import importlib.util
spec = importlib.util.spec_from_file_location("mcp_server_module", os.path.join(os.path.dirname(__file__), "server.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

logger = logging.getLogger("polymcp.webui")
logger.setLevel(logging.INFO)
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
fh = logging.FileHandler(os.path.join(log_dir, "webui.log"))
fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(fh)

app = FastAPI()

def _call_liara(prompt: str) -> str:
    """Call Liara AI API and return text response."""
    LIARA_API_KEY = os.getenv("LIARA_API_KEY")
    LIARA_BASE_URL = os.getenv("LIARA_BASE_URL")
    LIARA_MODEL = os.getenv("LIARA_MODEL", "openai/gpt-4o-mini")
    
    if not LIARA_API_KEY or not LIARA_BASE_URL:
        raise RuntimeError("Liara API credentials not configured")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LIARA_API_KEY}"
    }

    payload = {
        "model": LIARA_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 512
    }

    try:
        r = requests.post(f"{LIARA_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        
        return "No response from Liara AI"
    except Exception as e:
        logger.error("Liara AI request failed: %s", e)
        raise RuntimeError(f"Liara AI call failed: {e}")



@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(
        """
        <html>
          <body>
            <h3>PolyMCP Web UI</h3>
            <form action="/api/ask" method="post">
              <textarea name="prompt" rows="4" cols="60">قیمت AAPL رو بگو</textarea><br/>
              <button type="submit">Send</button>
            </form>
          </body>
        </html>
        """
    )


@dataclass
class MockArg:
    text: str


def _parse_mul(prompt: str):
    # look for patterns like 'ضرب 3 و 4' or '3*4' or 'multiply 3 4'
    m = re.search(r"(\d+(?:\.\d+)?)\s*[×x*]?\s*(\d+(?:\.\d+)?)", prompt)
    if m:
        a = float(m.group(1))
        b = float(m.group(2))
        return a, b
    m = re.search(r"ضرب\s*(\d+(?:\.\d+)?)\s*(?:و|,|\s)\s*(\d+(?:\.\d+)?)", prompt)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


@app.post("/api/ask")
async def api_ask(request: Request, prompt: str = Form(...)):
    # detect multiply intent (Persian 'ضرب' or pattern)
    logger.info("Prompt received: %s", prompt)

    if "ضرب" in prompt or "multiply" in prompt or _parse_mul(prompt):
        parsed = _parse_mul(prompt)
        if parsed:
            a, b = parsed
        else:
            nums = re.findall(r"\d+(?:\.\d+)?", prompt)
            if len(nums) >= 2:
                a, b = float(nums[0]), float(nums[1])
            else:
                logger.info("Multiply intent but numbers not found")
                return JSONResponse({"error": "numbers not found for multiply"}, status_code=400)

        logger.info("Calling math_op for multiply %s * %s", a, b)
        try:
            # call the async math_op
            res = await mod.math_op("math_op", {"operation": "mul", "a": a, "b": b})
            logger.info("math_op result: %s", res)
            return JSONResponse({"result": res})
        except Exception as e:
            logger.exception("math_op failed")
            return JSONResponse({"error": str(e)}, status_code=500)

    # otherwise use Liara AI if configured, else fallback to server completion
    try:
        try:
            logger.info("Forwarding prompt to Liara AI")
            text = _call_liara(prompt)
            logger.info("Liara AI returned: %s", text)
            return JSONResponse({"completion": [text]})
        except Exception as e:
            logger.exception("Liara AI call failed, falling back to internal completion: %s", e)

        arg = MockArg(text=prompt)
        loop = asyncio.get_running_loop()
        def call_completion():
            return mod.provide_completion(None, arg, None)

        res = await loop.run_in_executor(None, call_completion)
        logger.info("Internal completion returned: %s", res)
        if not res:
            return JSONResponse({"result": None})
        return JSONResponse({"completion": res.values})
    except Exception as e:
        logger.exception("LLM call failed")
        return JSONResponse({"error": str(e)}, status_code=500)
