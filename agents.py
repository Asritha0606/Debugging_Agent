# import json, uuid, time
# from utils import call_ollama_generate, validate_json_schema
# from langsmith_mock import create_run, emit_trace, list_failures, get_trace
# from typing import Dict, Any

# # Default models (you can change to any local Ollama model you have)
# SUPERVISOR_MODEL = "llama3"
# PLANNER_MODEL = "llama3"
# EXECUTOR_MODEL = "llama3"
# VALIDATOR_MODEL = "llama3"
# DEBUGGER_MODEL = "llama3"

# # Helper to call model with a prompt read from file
# def load_prompt(path: str) -> str:
#     with open(path, "r", encoding="utf-8") as f:
#         return f.read()

# SUPERVISOR_PROMPT = load_prompt("prompts/supervisor.txt")
# PLANNER_PROMPT = load_prompt("prompts/planner.txt")
# EXECUTOR_PROMPT = load_prompt("prompts/executor.txt")
# VALIDATOR_PROMPT = load_prompt("prompts/validator.txt")
# DEBUGGER_PROMPT = load_prompt("prompts/debugger.txt")

# class SupervisorAgent:
#     def __init__(self, model=SUPERVISOR_MODEL):
#         self.model = model

#     def run(self, user_task: str) -> Dict[str,Any]:
#         prompt = SUPERVISOR_PROMPT + "\n\nUSER_TASK:\n" + user_task
#         res = call_ollama_generate(self.model, prompt, stream=False, format_json=False)
#         # try parse JSON from response
#         body = res.get("response") if isinstance(res, dict) else None
#         if not body:
#             return {"error":"no_response", "raw":res}
#         # Attempt to extract JSON
#         try:
#             # some models wrap text directly; try to parse
#             parsed = json.loads(body.strip())
#             run = {"node":"supervisor","ok":True,"output":parsed}
#             return run
#         except Exception as e:
#             return {"node":"supervisor","ok":False,"error":"json_parse_failed","raw":body}

# class PlannerAgent:
#     def __init__(self, model=PLANNER_MODEL):
#         self.model = model

#     def run(self, supervisor_output: dict) -> Dict[str,Any]:
#         prompt = PLANNER_PROMPT + "\n\nSUPERVISOR_OUTPUT:\n" + json.dumps(supervisor_output)
#         res = call_ollama_generate(self.model, prompt)
#         body = res.get("response")
#         try:
#             parsed = json.loads(body.strip())
#             return {"node":"planner","ok":True,"output":parsed}
#         except Exception:
#             return {"node":"planner","ok":False,"error":"json_parse_failed","raw":body}

# class ExecutorAgent:
#     def __init__(self, model=EXECUTOR_MODEL):
#         self.model = model

#     def run(self, step: Dict[str,Any]) -> Dict[str,Any]:
#         # step contains: step_id, summary, expected_output etc.
#         prompt = EXECUTOR_PROMPT + "\n\nSTEP:\n" + json.dumps(step)
#         res = call_ollama_generate(self.model, prompt)
#         body = res.get("response")
#         # Expect JSON result
#         try:
#             parsed = json.loads(body.strip())
#             return {"node":"executor","ok":True,"output":parsed}
#         except Exception:
#             return {"node":"executor","ok":False,"error":"json_parse_failed","raw":body}

# class ValidatorAgent:
#     def __init__(self, model=VALIDATOR_MODEL):
#         self.model = model

#     def run(self, output: Dict[str,Any], schema: Dict[str,Any]) -> Dict[str,Any]:
#         # Run deterministic checks using small functions
#         ok, errs = validate_json_schema(output, schema)
#         if ok:
#             return {"node":"validator","ok":True,"output":output,"errors":[]}
#         else:
#             return {"node":"validator","ok":False,"output":output,"errors":errs,"fix_suggestion":"fix fields: " + ", ".join(errs)}

# class DebuggerAgent:
#     def __init__(self, model=DEBUGGER_MODEL):
#         self.model = model

#     def analyze_and_plan(self, run_trace: Dict[str,Any]) -> Dict[str,Any]:
#         # For demo: create a simple repair plan based on validator errors
#         # If validator failed, patch the executor prompt to enforce schema
#         repairs = []
#         # Find failing node
#         for node in run_trace.get("nodes", []):
#             if not node.get("ok", True):
#                 if node["node"] == "validator":
#                     repairs.append({"action":"modify_executor_prompt","patch":"Enforce strict JSON schema. Output must include required fields."})
#                     repairs.append({"action":"retry_node","node":"executor"})
#                 elif node["node"] == "executor":
#                     repairs.append({"action":"retry_node","node":"executor","params":{"reduce_temperature":True}})
#                 elif node["node"] == "planner":
#                     repairs.append({"action":"retry_node","node":"planner"})
#         if not repairs:
#             repairs.append({"action":"escalate","reason":"unknown_failure"})
#         return {"repair_actions":repairs, "explain":"Auto-generated repair plan"}

#     def apply_plan(self, plan: Dict[str,Any], orchestrator):
#         """
#         For demo, apply simple plan actions directly.
#         orchestrator: instance of Orchestrator to call retries.
#         """
#         for a in plan.get("repair_actions", []):
#             if a["action"] == "modify_executor_prompt":
#                 # append a strict instruction to executor prompt (in memory)
#                 orchestrator.executor_extra_patch = a["patch"]
#             elif a["action"] == "retry_node":
#                 node = a["node"]
#                 orchestrator.retry_node(node)
#             elif a["action"] == "escalate":
#                 orchestrator.escalate("Debugger escalation: " + a.get("reason",""))
#         return {"ok":True, "applied": True}

# # Orchestrator that ties everything
# class Orchestrator:
#     def __init__(self):
#         self.supervisor = SupervisorAgent()
#         self.planner = PlannerAgent()
#         self.executor = ExecutorAgent()
#         self.validator = ValidatorAgent()
#         self.debugger = DebuggerAgent()
#         self.executor_extra_patch = ""

#     def run_task(self, user_task: str, run_trace_store=True):
#         run_id = str(uuid.uuid4())[:8]
#         trace = {"user_task":user_task, "nodes":[]}
#         sup = self.supervisor.run(user_task)
#         trace["nodes"].append(sup)
#         if not sup.get("ok"):
#             sup["status"]="fail"
#             emit_trace(run_id, trace)
#             return {"status":"supervisor_failed","trace":trace}
#         plan = self.planner.run(sup["output"])
#         trace["nodes"].append(plan)
#         if not plan.get("ok"):
#             plan["status"]="fail"
#             emit_trace(run_id, trace)
#             return {"status":"planner_failed","trace":trace}
#         # iterate steps
#         for step in plan["output"].get("plan", []):
#             # apply patch if any to the executor prompt by attaching to step
#             if self.executor_extra_patch:
#                 step["executor_patch"] = self.executor_extra_patch
#             exe = self.executor.run(step)
#             trace["nodes"].append(exe)
#             if not exe.get("ok"):
#                 exe["status"]="fail"
#                 emit_trace(run_id, trace)
#                 # call debugger now
#                 plan = self.debugger.analyze_and_plan(trace)
#                 self.debugger.apply_plan(plan, self)
#                 # after apply, continue loop - retries may have run
#                 continue
#             # run validator (use step.schema if present)
#             schema = step.get("schema", {"type":"json","properties":{}})
#             val = self.validator.run(exe["output"], schema)
#             trace["nodes"].append(val)
#             if not val.get("ok"):
#                 val["status"]="fail"
#                 emit_trace(run_id, trace)
#                 # request debugger
#                 plan = self.debugger.analyze_and_plan(trace)
#                 self.debugger.apply_plan(plan, self)
#                 # retry logic: after debug apply, attempt to re-run executor for the step
#                 # If retry node has been executed in debugger.apply_plan, it will call orchestrator.retry_node
#                 continue
#         # final global validation (simple)
#         trace["status"]="ok"
#         emit_trace(run_id, trace)
#         return {"status":"ok","run_id":run_id,"trace":trace}

#     def retry_node(self, node_name: str):
#         # For demo: we simply print and let run_task continue; in real system, you'd re-run that node
#         print(f"[Orchestrator] retry requested for {node_name} - in this demo we re-run entire run manually.")
#         # In production you'd implement targeted replay; here, we keep it simple.

#     def escalate(self, reason):
#         print("[Orchestrator] Escalation: ", reason)


import json, uuid, time
from utils import call_ollama_generate, validate_json_schema, extract_json
from langsmith_mock import create_run, emit_trace, list_failures, get_trace
from typing import Dict, Any

# Default models (you can change to any local Ollama model you have)
SUPERVISOR_MODEL = "llama3"
PLANNER_MODEL = "llama3"
EXECUTOR_MODEL = "llama3"
VALIDATOR_MODEL = "llama3"
DEBUGGER_MODEL = "llama3"

# Helper to call model with a prompt read from file
def load_prompt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

SUPERVISOR_PROMPT = load_prompt("prompts/supervisor.txt")
PLANNER_PROMPT = load_prompt("prompts/planner.txt")
EXECUTOR_PROMPT = load_prompt("prompts/executor.txt")
VALIDATOR_PROMPT = load_prompt("prompts/validator.txt")
DEBUGGER_PROMPT = load_prompt("prompts/debugger.txt")


# =====================================================================
#  SUPERVISOR
# =====================================================================
class SupervisorAgent:
    def __init__(self, model=SUPERVISOR_MODEL):
        self.model = model

    def run(self, user_task: str) -> Dict[str,Any]:
        prompt = SUPERVISOR_PROMPT + "\n\nUSER_TASK:\n" + user_task
        res = call_ollama_generate(self.model, prompt, stream=False, format_json=False)

        body = res.get("response") if isinstance(res, dict) else None
        if not body:
            return {"node":"supervisor", "ok":False, "error":"no_response", "raw":res}

        parsed = extract_json(body)
        if parsed is None:
            return {"node":"supervisor","ok":False,"error":"json_parse_failed","raw":body}

        return {"node":"supervisor","ok":True,"output":parsed}



# =====================================================================
#  PLANNER
# =====================================================================
class PlannerAgent:
    def __init__(self, model=PLANNER_MODEL):
        self.model = model

    def run(self, supervisor_output: dict) -> Dict[str,Any]:
        prompt = PLANNER_PROMPT + "\n\nSUPERVISOR_OUTPUT:\n" + json.dumps(supervisor_output)
        res = call_ollama_generate(self.model, prompt)

        body = res.get("response")
        parsed = extract_json(body)

        if parsed is None:
            return {"node":"planner","ok":False,"error":"json_parse_failed","raw":body}

        return {"node":"planner","ok":True,"output":parsed}



# =====================================================================
#  EXECUTOR
# =====================================================================
class ExecutorAgent:
    def __init__(self, model=EXECUTOR_MODEL):
        self.model = model

    def run(self, step: Dict[str,Any]) -> Dict[str,Any]:
        prompt = EXECUTOR_PROMPT + "\n\nSTEP:\n" + json.dumps(step)
        res = call_ollama_generate(self.model, prompt)

        body = res.get("response")
        parsed = extract_json(body)

        if parsed is None:
            return {"node":"executor","ok":False,"error":"json_parse_failed","raw":body}

        return {"node":"executor","ok":True,"output":parsed}



# =====================================================================
#  VALIDATOR
# =====================================================================
class ValidatorAgent:
    def __init__(self, model=VALIDATOR_MODEL):
        self.model = model

    def run(self, output: Dict[str,Any], schema: Dict[str,Any]) -> Dict[str,Any]:
        ok, errs = validate_json_schema(output, schema)

        if ok:
            return {"node":"validator","ok":True,"output":output,"errors":[]}
        else:
            return {
                "node":"validator",
                "ok":False,
                "output":output,
                "errors":errs,
                "fix_suggestion":"fix fields: " + ", ".join(errs)
            }



# =====================================================================
#  DEBUGGER
# =====================================================================
class DebuggerAgent:
    def __init__(self, model=DEBUGGER_MODEL):
        self.model = model

    def analyze_and_plan(self, run_trace: Dict[str,Any]) -> Dict[str,Any]:
        repairs = []

        for node in run_trace.get("nodes", []):
            if not node.get("ok", True):

                if node["node"] == "validator":
                    repairs.append({
                        "action":"modify_executor_prompt",
                        "patch":"Enforce strict JSON schema. Output must include required fields."
                    })
                    repairs.append({"action":"retry_node","node":"executor"})

                elif node["node"] == "executor":
                    repairs.append({
                        "action":"retry_node",
                        "node":"executor",
                        "params":{"reduce_temperature":True}
                    })

                elif node["node"] == "planner":
                    repairs.append({"action":"retry_node","node":"planner"})

        if not repairs:
            repairs.append({"action":"escalate","reason":"unknown_failure"})

        return {
            "repair_actions": repairs,
            "explain": "Auto-generated repair plan"
        }

    def apply_plan(self, plan: Dict[str,Any], orchestrator):
        for a in plan.get("repair_actions", []):
            if a["action"] == "modify_executor_prompt":
                orchestrator.executor_extra_patch = a["patch"]

            elif a["action"] == "retry_node":
                node = a["node"]
                orchestrator.retry_node(node)

            elif a["action"] == "escalate":
                orchestrator.escalate("Debugger escalation: " + a.get("reason",""))

        return {"ok":True, "applied":True}



# =====================================================================
#  ORCHESTRATOR
# =====================================================================
class Orchestrator:
    def __init__(self):
        self.supervisor = SupervisorAgent()
        self.planner = PlannerAgent()
        self.executor = ExecutorAgent()
        self.validator = ValidatorAgent()
        self.debugger = DebuggerAgent()
        self.executor_extra_patch = ""

    def run_task(self, user_task: str, run_trace_store=True):
        run_id = str(uuid.uuid4())[:8]
        trace = {"user_task":user_task, "nodes":[]}

        # --------------------------
        # SUPER­VISOR
        # --------------------------
        sup = self.supervisor.run(user_task)
        trace["nodes"].append(sup)
        if not sup.get("ok"):
            sup["status"]="fail"
            emit_trace(run_id, trace)
            return {"status":"supervisor_failed","trace":trace}

        # --------------------------
        # PLANNER
        # --------------------------
        plan = self.planner.run(sup["output"])
        trace["nodes"].append(plan)
        if not plan.get("ok"):
            plan["status"]="fail"
            emit_trace(run_id, trace)
            return {"status":"planner_failed","trace":trace}

        # --------------------------
        # EXECUTION LOOP
        # --------------------------
        for step in plan["output"].get("plan", []):

            if self.executor_extra_patch:
                step["executor_patch"] = self.executor_extra_patch

            # Executor
            exe = self.executor.run(step)
            trace["nodes"].append(exe)

            if not exe.get("ok"):
                exe["status"]="fail"
                emit_trace(run_id, trace)

                repair = self.debugger.analyze_and_plan(trace)
                self.debugger.apply_plan(repair, self)
                continue

            # Validator
            schema = step.get("schema", {"type":"json","properties":{}})
            val = self.validator.run(exe["output"], schema)
            trace["nodes"].append(val)

            if not val.get("ok"):
                val["status"]="fail"
                emit_trace(run_id, trace)

                repair = self.debugger.analyze_and_plan(trace)
                self.debugger.apply_plan(repair, self)
                continue

        # --------------------------
        # SUCCESS
        # --------------------------
        trace["status"]="ok"
        emit_trace(run_id, trace)
        return {"status":"ok","run_id":run_id,"trace":trace}


    def retry_node(self, node_name: str):
        print(f"[Orchestrator] retry requested for {node_name} (demo only)")

    def escalate(self, reason):
        print("[Orchestrator] Escalation:", reason)
