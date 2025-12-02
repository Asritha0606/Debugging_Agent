"""
A tiny in-memory LangSmith-like trace store for demo purposes.
Store traces, query failing runs, mark repairs, etc.
"""
from typing import List, Dict
import uuid
import time

_TRACES = {}

def emit_trace(run_id: str, trace: Dict):
    _TRACES[run_id] = {
        "trace": trace,
        "created_at": time.time(),
        "status": trace.get("status","ok")
    }

def list_failures(since_seconds: int=3600):
    now = time.time()
    out = []
    for rid, rec in _TRACES.items():
        if rec["status"] != "ok" and (now - rec["created_at"]) <= since_seconds:
            out.append({"run_id": rid, "trace": rec["trace"], "status": rec["status"]})
    return out

def get_trace(run_id: str):
    return _TRACES.get(run_id)

def create_run(trace: Dict):
    rid = str(uuid.uuid4())[:8]
    emit_trace(rid, trace)
    return rid
