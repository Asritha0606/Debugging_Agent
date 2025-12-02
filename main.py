import argparse, json
from agents import Orchestrator
from langsmith_mock import list_failures, get_trace
from fastapi import FastAPI
import uvicorn

app = FastAPI()
orch = Orchestrator()

@app.post("/run_task")
def run_task(payload: dict):
    task = payload.get("task")
    if not task:
        return {"error":"no_task_provided"}
    res = orch.run_task(task)
    return res

@app.get("/failures")
def failures():
    return list_failures()

@app.get("/trace/{run_id}")
def trace(run_id: str):
    return get_trace(run_id)

def cli_run():
    print("Agentic demo (Ollama). Type your task (non-biomedical). Example: 'Summarize the following text and produce a 3-row CSV of counts.'")
    while True:
        t = input("TASK> ").strip()
        if not t:
            continue
        res = orch.run_task(t)
        print("=== RUN RESULT ===")
        print(json.dumps(res, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="run FastAPI server")
    args = parser.parse_args()
    if args.serve:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        cli_run()
