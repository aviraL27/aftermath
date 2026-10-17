import time
from typing import Any, Dict, List, Optional
from aftermath.core.task import TaskDefinition
from aftermath.core.sandbox import Sandbox
from aftermath.core.assertions import evaluate_task, EvaluationSummary
from aftermath.core.trace import RunTrace, StepTrace
from aftermath.adapters.base import BaseModelAdapter, AgentAction

class ExecutionRunner:
    """
    Executes a task within a controlled sandbox, driving the agent
    and recording the complete execution trace and evaluation.
    """
    def __init__(self, task: TaskDefinition, adapter: BaseModelAdapter):
        self.task = task
        self.adapter = adapter

    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        all_tools = [
            {
                "name": "read_file",
                "description": "Read full text of a file in the workspace",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
            },
            {
                "name": "write_file",
                "description": "Create or overwrite a file with given content",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}
            },
            {
                "name": "edit_file",
                "description": "Replace a specific substring in an existing file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "find": {"type": "string"}, "replace": {"type": "string"}}, "required": ["path", "find", "replace"]}
            },
            {
                "name": "list_files",
                "description": "List files currently in the workspace",
                "parameters": {"type": "object", "properties": {"directory": {"type": "string", "default": "."}}}
            },
            {
                "name": "run_command",
                "description": "Execute a terminal shell command inside the workspace and get stdout, stderr, and exit code",
                "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}
            }
        ]
        return [t for t in all_tools if t["name"] in self.task.tools]

    def _execute_tool(self, sandbox: Sandbox, tool_name: str, tool_args: Dict[str, Any]) -> str:
        try:
            if tool_name == "read_file":
                return sandbox.read_file(tool_args.get("path", ""))
            elif tool_name == "write_file":
                return sandbox.write_file(tool_args.get("path", ""), tool_args.get("content", ""))
            elif tool_name == "edit_file":
                return sandbox.edit_file(
                    tool_args.get("path", ""),
                    tool_args.get("find", ""),
                    tool_args.get("replace", "")
                )
            elif tool_name == "list_files":
                files = sandbox.list_files(tool_args.get("directory", "."))
                return f"Files: {files}"
            elif tool_name == "run_command":
                cmd = tool_args.get("command", "")
                res = sandbox.run_command(cmd)
                return f"Exit code: {res['exit_code']}\nStdout: {res['stdout'].strip()}\nStderr: {res['stderr'].strip()}"
            else:
                return f"Error: Unknown tool '{tool_name}'"
        except Exception as e:
            return f"Error executing {tool_name}: {e}"

    def run(self) -> RunTrace:
        start_time = time.time()
        steps: List[StepTrace] = []
        history: List[Dict[str, Any]] = []

        with Sandbox(
            fixture_path=self.task.workspace_fixture,
            backend=self.task.sandbox_backend,
            e2b_template=self.task.e2b_template
        ) as sandbox:
            initial_snapshot = sandbox.initial_snapshot
            available_tools = self._get_tool_definitions()

            step_count = 0
            while step_count < self.task.max_steps:
                step_count += 1
                step_t0 = time.time()
                workspace_files = sandbox.list_files(".")

                action: AgentAction = self.adapter.step(
                    instruction=self.task.instruction,
                    history=history,
                    available_tools=available_tools,
                    workspace_files=workspace_files
                )

                step_duration = time.time() - step_t0
                
                # If finish or no tool
                if action.finish or not action.tool_name:
                    steps.append(StepTrace(
                        step_number=step_count,
                        agent_thought=action.thought,
                        tool_name=None,
                        tool_args=None,
                        tool_output=action.final_message or "Agent finished task.",
                        duration_seconds=step_duration
                    ))
                    break

                # Execute tool
                tool_output = self._execute_tool(sandbox, action.tool_name, action.tool_args or {})

                steps.append(StepTrace(
                    step_number=step_count,
                    agent_thought=action.thought,
                    tool_name=action.tool_name,
                    tool_args=action.tool_args,
                    tool_output=tool_output,
                    duration_seconds=step_duration
                ))

                # Update history for next iteration
                history.append({
                    "role": "assistant",
                    "content": f"Action: Call {action.tool_name} with {action.tool_args}. Thought: {action.thought}"
                })
                history.append({
                    "role": "system",
                    "content": f"Tool output: {tool_output}"
                })

            # Evaluate assertions
            evaluation: EvaluationSummary = evaluate_task(sandbox, self.task.expected_outcomes)
            final_snapshot = sandbox.take_snapshot()
            workspace_diff = sandbox.compute_diff()
            end_time = time.time()

            status = "PASSED" if evaluation.all_passed else "FAILED"

            return RunTrace(
                task_id=self.task.id,
                task_name=self.task.name,
                instruction=self.task.instruction,
                model_name=self.adapter.name,
                provider=self.adapter.provider,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=end_time - start_time,
                status=status,
                steps=steps,
                initial_snapshot=initial_snapshot,
                final_snapshot=final_snapshot,
                workspace_diff=workspace_diff,
                assertion_results=[r.model_dump() for r in evaluation.assertion_results],
                invariant_results=[r.model_dump() for r in evaluation.invariant_results]
            )

