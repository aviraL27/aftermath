import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import glob

from aftermath.core.task import TaskDefinition
from aftermath.core.runner import ExecutionRunner
from aftermath.core.trace import RunTrace
from aftermath.core.generator import RegressionTestGenerator
from aftermath.adapters.mock import MockAdapter
from aftermath.adapters.gemma import GemmaAdapter
from aftermath.adapters.mistral import MistralAdapter
from aftermath.config import settings

app = FastAPI(title="Aftermath AI Regression Testing Harness")

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

class RunRequest(BaseModel):
    task_file: str
    model: str = "mock-buggy"
    provider: Optional[str] = None
    backend: Optional[str] = None

class CompareRequest(BaseModel):
    task_file: str
    models: List[str] = ["gemma4", "mistral"]
    backend: Optional[str] = None

class GenerateTestRequest(BaseModel):
    trace_data: Dict[str, Any]

def _resolve_adapter(model_name: str, provider: Optional[str] = None):
    m = model_name.lower()
    if m.startswith("mock"):
        mode = "buggy" if "buggy" in m else "fixed"
        return MockAdapter(mode=mode)
    elif "mistral" in m:
        return MistralAdapter()
    elif "gemma" in m or "gemini" in m:
        pref = provider or ("google" if settings.get_google_key() else "ollama")
        return GemmaAdapter(primary_provider=pref)
    else:
        return MockAdapter(mode="fixed")

@app.get("/api/system-status")
def get_system_status():
    """Returns connectivity and availability of configured models and providers."""
    return {
        "e2b_configured": bool(settings.get_e2b_key()),
        "google_api_configured": bool(settings.get_google_key()),
        "mistral_api_configured": bool(settings.mistral_api_key),
        "ollama_base_url": settings.ollama_base_url,
        "ollama_gemma_model": settings.ollama_gemma_model,
        "mistral_model": settings.mistral_model,
        "gemma_primary": "google (2.4s benchmarked)",
        "gemma_fallback": "ollama local (7.5s benchmarked)",
        "e2b_runtime": "Firecracker Linux Micro-VM (Active)" if settings.get_e2b_key() else "Inactive"
    }

@app.get("/api/tasks")
def list_tasks():
    """List available tasks and regression test suites."""
    tasks = []
    task_files = glob.glob("fixtures/tasks/*.yaml") + glob.glob("aftermath/generated_tests/*.yaml")
    for tf in task_files:
        try:
            td = TaskDefinition.load(tf)
            tasks.append({
                "id": td.id,
                "name": td.name,
                "description": td.description,
                "instruction": td.instruction,
                "sandbox_backend": td.sandbox_backend,
                "file_path": tf.replace("\\", "/"),
                "is_regression_test": td.is_regression_test,
                "validated": td.validated,
                "tools": td.tools,
                "assertions_count": len(td.expected_outcomes.assertions),
                "invariants_count": len(td.expected_outcomes.invariants)
            })
        except Exception as e:
            continue
    return tasks

@app.post("/api/run")
def run_task(req: RunRequest):
    """Execute a task and return full trace."""
    p = Path(req.task_file)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Task file not found: {req.task_file}")
    
    task = TaskDefinition.load(p)
    if req.backend:
        task.sandbox_backend = req.backend.lower()

    adapter = _resolve_adapter(req.model, req.provider)
    runner = ExecutionRunner(task, adapter)
    trace = runner.run()

    # Save to traces dir
    trace_dir = Path(".aftermath_traces")
    trace_dir.mkdir(exist_ok=True)
    out_path = trace_dir / f"trace_{trace.task_id}_{int(trace.start_time)}.json"
    trace.save(out_path)

    return trace.model_dump()

@app.post("/api/compare")
def compare_task(req: CompareRequest):
    """Execute task on multiple models and return comparison."""
    p = Path(req.task_file)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Task file not found: {req.task_file}")
    
    task = TaskDefinition.load(p)
    if req.backend:
        task.sandbox_backend = req.backend.lower()

    traces = []
    for m in req.models:
        adapter = _resolve_adapter(m)
        runner = ExecutionRunner(task, adapter)
        trace = runner.run()
        traces.append(trace.model_dump())
    
    return {"traces": traces}

@app.post("/api/generate-test")
def generate_regression_test(req: GenerateTestRequest):
    """Synthesize and double-validate regression test from a failure trace."""
    try:
        trace = RunTrace(**req.trace_data)
        generator = RegressionTestGenerator()
        reg_task, validated, message = generator.generate(trace)
        return {
            "validated": validated,
            "message": message,
            "task": reg_task.model_dump() if reg_task else None
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/traces")
def list_traces():
    """List recent trace files."""
    trace_files = glob.glob(".aftermath_traces/*.json")
    results = []
    for tf in sorted(trace_files, key=os.path.getmtime, reverse=True)[:20]:
        try:
            tr = RunTrace.load(tf)
            results.append({
                "file_path": tf.replace("\\", "/"),
                "task_id": tr.task_id,
                "task_name": tr.task_name,
                "status": tr.status,
                "model_name": tr.model_name,
                "provider": tr.provider,
                "duration_seconds": tr.duration_seconds,
                "timestamp": tr.start_time
            })
        except Exception:
            continue
    return results

# Static Files & Dashboard UI
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def get_dashboard():
    return FileResponse(STATIC_DIR / "index.html")

