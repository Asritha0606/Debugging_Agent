import requests
import os
import json
from typing import Any, Dict, Tuple, List

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")

def call_ollama_generate(model: str, prompt: str, stream: bool=False, format_json: bool=False, options: Dict=None) -> Dict[str, Any]:
    """
    Simple wrapper for Ollama /api/generate endpoint.
    Returns the JSON-decoded output or a dict with 'error'.
    """
    url = f"{OLLAMA_BASE}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}
    if options:
        payload["options"] = options
    if format_json:
        payload["format"] = "json"
    try:
        r = requests.post(url, data=json.dumps(payload), headers={"Content-Type":"application/json"}, timeout=60)
        r.raise_for_status()
        # Ollama returns a JSON object containing 'response' (string) among others
        try:
            data = r.json()
            # many models put text in data["response"] or data["choices"] depending
            return data
        except Exception:
            return {"error": "invalid_json_response", "raw": r.text}
    except Exception as e:
        return {"error": str(e)}

def extract_json(text: str):
    """
    Extract the FIRST valid JSON object { ... } from a messy LLM response.
    Works with nested braces using a manual stack.
    """
    import json

    start = text.find("{")
    if start == -1:
        return None

    stack = []
    for i in range(start, len(text)):
        if text[i] == "{":
            stack.append("{")
        elif text[i] == "}":
            if stack:
                stack.pop()
            if not stack:
                candidate = text[start:i+1]
                try:
                    return json.loads(candidate)
                except:
                    return None
    return None



# simple schema validators (very small)
def validate_json_schema(obj: dict, schema: dict) -> Tuple[bool, List[str]]:
    # Minimal validator: check required fields in schema properties
    errs = []
    if not isinstance(obj, dict):
        return False, ["output_not_object"]
    props = schema.get("properties", {})
    required = schema.get("required", [])
    for key in required:
        if key not in obj:
            errs.append(f"missing_required_{key}")
    # type checks (very small)
    for key, spec in props.items():
        if key in obj:
            t = spec.get("type")
            if t == "string" and not isinstance(obj[key], str):
                errs.append(f"type_mismatch_{key}_not_string")
    return (len(errs) == 0, errs)
