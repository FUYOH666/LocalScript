from __future__ import annotations

import json
import re


def extract_lua_code(message: str) -> str:
    """Take JSON `code`, first ```lua ... ``` or plain ``` ... ``` block; else stripped message."""
    text = message.strip()
    if text.startswith("{") and '"code"' in text:
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                code = obj.get("code")
                if isinstance(code, str) and code.strip():
                    return code.strip()
        except json.JSONDecodeError:
            pass
    patterns = [
        r"```lua\s*\n(.*?)```",
        r"```\s*\n(.*?)```",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return text
