"""
Workflow Engine — step executors.
=================================
Execute different types of workflow steps: code, shell, HTTP, file, etc.
"""

from __future__ import annotations

import asyncio
import io
import os
import shutil
import time
import uuid
from typing import Any

import httpx

from jarvis.core.workflow.base import Step, StepResult, StepStatus, StepType


class StepExecutors:
    """Routes and executes workflow steps by type."""

    async def execute(self, step: Step, context: dict) -> StepResult:
        """Route to the correct executor based on step type."""
        start = time.time()
        try:
            executor_map = {
                StepType.CODE: self.execute_code,
                StepType.SHELL: self.execute_shell,
                StepType.HTTP: self.execute_http,
                StepType.FILE: self.execute_file,
                StepType.SKILL: self.execute_skill,
                StepType.WORKFLOW: self.execute_workflow,
                StepType.CONDITION: self.execute_condition,
                StepType.LOOP: self.execute_loop,
                StepType.WAIT: self.execute_wait,
                StepType.MANUAL: self.execute_manual,
                StepType.CALLBACK: self.execute_callback,
            }
            executor = executor_map.get(step.step_type)
            if executor is None:
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error=f"Unknown step type: {step.step_type}",
                    duration=time.time() - start,
                )
            return await executor(step, context)
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                duration=time.time() - start,
            )

    async def execute_code(self, step: Step, context: dict) -> StepResult:
        """Run Python code via exec(). Captures stdout/stderr."""
        start = time.time()
        code = self._substitute_vars(step.command, context.get("variables", {}))
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        local_ns: dict[str, Any] = {"context": context, "variables": context.get("variables", {})}
        try:
            async def _run():
                import sys
                _orig_stdout, _orig_stderr = sys.stdout, sys.stderr
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture
                try:
                    exec(code, {"__builtins__": __builtins__}, local_ns)
                finally:
                    sys.stdout, sys.stderr = _orig_stdout, _orig_stderr

            await asyncio.wait_for(_run(), timeout=step.timeout)
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                output={
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue(),
                    "namespace": {k: v for k, v in local_ns.items() if not k.startswith("_")},
                },
                duration=time.time() - start,
            )
        except asyncio.TimeoutError:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error="Code execution timed out",
                duration=time.time() - start,
            )
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                output={"stdout": stdout_capture.getvalue(), "stderr": stderr_capture.getvalue()},
                duration=time.time() - start,
            )

    async def execute_shell(self, step: Step, context: dict) -> StepResult:
        """Run a shell command via asyncio.create_subprocess_shell."""
        start = time.time()
        command = self._substitute_vars(step.command, context.get("variables", {}))
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=step.timeout)
            stdout = stdout_bytes.decode(errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode(errors="replace") if stderr_bytes else ""
            status = StepStatus.SUCCESS if proc.returncode == 0 else StepStatus.FAILED
            return StepResult(
                step_id=step.id,
                status=status,
                output={"stdout": stdout, "stderr": stderr, "returncode": proc.returncode},
                error=stderr if proc.returncode != 0 else "",
                duration=time.time() - start,
            )
        except asyncio.TimeoutError:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error="Shell command timed out",
                duration=time.time() - start,
            )
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                duration=time.time() - start,
            )

    async def execute_http(self, step: Step, context: dict) -> StepResult:
        """Make an HTTP request via httpx. Supports GET/POST/PUT/DELETE."""
        start = time.time()
        url = self._substitute_vars(step.command, context.get("variables", {}))
        params = step.params
        method = params.get("method", "GET").upper()
        headers = params.get("headers", {})
        body = params.get("body")
        timeout_val = params.get("timeout", step.timeout)
        try:
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                response = await client.request(method, url, headers=headers, json=body)
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                output={
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                },
                duration=time.time() - start,
            )
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                duration=time.time() - start,
            )

    async def execute_file(self, step: Step, context: dict) -> StepResult:
        """File operations: read, write, copy, move, delete, exists, mkdir."""
        start = time.time()
        params = step.params
        operation = params.get("operation", "")
        path = self._substitute_vars(params.get("path", ""), context.get("variables", {}))
        try:
            if operation == "read":
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                result = {"content": content}
            elif operation == "write":
                content = params.get("content", "")
                content = self._substitute_vars(content, context.get("variables", {}))
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                result = {"written": True, "path": path}
            elif operation == "copy":
                dest = self._substitute_vars(params.get("dest", ""), context.get("variables", {}))
                shutil.copy2(path, dest)
                result = {"copied": True, "source": path, "dest": dest}
            elif operation == "move":
                dest = self._substitute_vars(params.get("dest", ""), context.get("variables", {}))
                shutil.move(path, dest)
                result = {"moved": True, "source": path, "dest": dest}
            elif operation == "delete":
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                result = {"deleted": True, "path": path}
            elif operation == "exists":
                result = {"exists": os.path.exists(path)}
            elif operation == "mkdir":
                os.makedirs(path, exist_ok=True)
                result = {"created": True, "path": path}
            else:
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error=f"Unknown file operation: {operation}",
                    duration=time.time() - start,
                )
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                output=result,
                duration=time.time() - start,
            )
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                duration=time.time() - start,
            )

    async def execute_skill(self, step: Step, context: dict) -> StepResult:
        """Invoke a JARVIS skill by name."""
        start = time.time()
        params = step.params
        skill_name = params.get("skill_name", step.command)
        skill_params = params.get("skill_params", {})
        try:
            from jarvis.core.skill_manager import SkillManager
            manager = SkillManager()
            result = await asyncio.wait_for(
                manager.execute(skill_name, skill_params), timeout=step.timeout
            )
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                output=result,
                duration=time.time() - start,
            )
        except asyncio.TimeoutError:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=f"Skill '{skill_name}' timed out",
                duration=time.time() - start,
            )
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                duration=time.time() - start,
            )

    async def execute_workflow(self, step: Step, context: dict) -> StepResult:
        """Execute a nested sub-workflow."""
        start = time.time()
        params = step.params
        workflow_id = params.get("workflow_id", "")
        try:
            from jarvis.core.workflow.engine import WorkflowEngine
            engine = WorkflowEngine()
            result = await asyncio.wait_for(
                engine.execute(workflow_id, context), timeout=step.timeout
            )
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                output=result,
                duration=time.time() - start,
            )
        except asyncio.TimeoutError:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=f"Sub-workflow '{workflow_id}' timed out",
                duration=time.time() - start,
            )
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                duration=time.time() - start,
            )

    async def execute_condition(self, step: Step, context: dict) -> StepResult:
        """Evaluate a Python expression. Returns True/False."""
        start = time.time()
        expression = self._substitute_vars(step.params.get("expression", step.command), context.get("variables", {}))
        try:
            result = eval(expression, {"__builtins__": {}}, context.get("variables", {}))
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                output=bool(result),
                duration=time.time() - start,
            )
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=f"Condition evaluation failed: {exc}",
                duration=time.time() - start,
            )

    async def execute_loop(self, step: Step, context: dict) -> StepResult:
        """Repeat steps N times."""
        start = time.time()
        params = step.params
        count = params.get("count", 1)
        steps = params.get("steps", [])
        results = []
        try:
            for i in range(count):
                loop_context = {**context, "loop_index": i}
                for step_def in steps:
                    sub_step = Step(
                        id=f"{step.id}_loop{i}_{uuid.uuid4().hex[:6]}",
                        name=step_def.get("name", f"Loop {i} step"),
                        step_type=StepType(step_def.get("type", "code")),
                        command=step_def.get("command", ""),
                        params=step_def.get("params", {}),
                        timeout=step_def.get("timeout", step.timeout),
                    )
                    result = await self.execute(sub_step, loop_context)
                    results.append(result)
                    if result.status == StepStatus.FAILED:
                        return StepResult(
                            step_id=step.id,
                            status=StepStatus.FAILED,
                            error=f"Loop iteration {i} failed: {result.error}",
                            output=results,
                            duration=time.time() - start,
                        )
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                output=results,
                duration=time.time() - start,
            )
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                output=results,
                duration=time.time() - start,
            )

    async def execute_wait(self, step: Step, context: dict) -> StepResult:
        """Wait for a duration specified in seconds."""
        start = time.time()
        seconds = step.params.get("seconds", 1.0)
        try:
            await asyncio.wait_for(asyncio.sleep(seconds), timeout=seconds + 1)
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                output={"waited": seconds},
                duration=time.time() - start,
            )
        except asyncio.TimeoutError:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error="Wait timed out",
                duration=time.time() - start,
            )

    async def execute_manual(self, step: Step, context: dict) -> StepResult:
        """Mark step as waiting for human input."""
        start = time.time()
        instruction = self._substitute_vars(
            step.params.get("instruction", step.command), context.get("variables", {})
        )
        return StepResult(
            step_id=step.id,
            status=StepStatus.WAITING,
            output={"instruction": instruction, "awaiting_human_input": True},
            duration=time.time() - start,
        )

    async def execute_callback(self, step: Step, context: dict) -> StepResult:
        """Call a registered callback function."""
        start = time.time()
        params = step.params
        callback_name = params.get("callback_name", step.command)
        callback_args = params.get("args", [])
        callback_kwargs = params.get("kwargs", {})
        callbacks = context.get("callbacks", {})
        try:
            if callback_name not in callbacks:
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error=f"Callback '{callback_name}' not registered",
                    duration=time.time() - start,
                )
            callback = callbacks[callback_name]
            result = callback(*callback_args, **callback_kwargs)
            if asyncio.iscoroutine(result):
                result = await asyncio.wait_for(result, timeout=step.timeout)
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                output=result,
                duration=time.time() - start,
            )
        except asyncio.TimeoutError:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=f"Callback '{callback_name}' timed out",
                duration=time.time() - start,
            )
        except Exception as exc:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                duration=time.time() - start,
            )

    @staticmethod
    def _substitute_vars(text: str, variables: dict) -> str:
        """Replace {var_name} placeholders in text with context variables."""
        if not isinstance(text, str):
            return text
        for key, value in variables.items():
            text = text.replace(f"{{{key}}}", str(value))
        return text
