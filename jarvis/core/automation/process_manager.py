"""
Process manager for JARVIS desktop automation.
================================================
View, monitor, and manage running processes.

Capabilities:
    - List all processes with details
    - Find processes by name or PID
    - Kill processes (with safety checks)
    - Monitor CPU/memory usage
    - Start processes with arguments
    - Get process tree

Usage:
    pm = ProcessManager(safety_gate)
    result = await pm.list_processes()
    result = await pm.find("python")
    result = await pm.kill(pid=1234)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from jarvis.core.automation.base import ActionSeverity, ActionResult, SafetyGate

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Information about a running process."""
    pid: int
    name: str
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    threads: int = 0
    started_at: str = ""
    command: str = ""
    parent_pid: int = 0

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "name": self.name,
            "cpu_percent": self.cpu_percent,
            "memory_mb": round(self.memory_mb, 1),
            "threads": self.threads,
            "started_at": self.started_at,
            "command": self.command[:200],
            "parent_pid": self.parent_pid,
        }


class ProcessManager:
    """Monitor and manage system processes.

    Example:
        gate = SafetyGate()
        pm = ProcessManager(gate)
        result = await pm.list_processes()
        result = await pm.find("chrome")
        await pm.kill(name="notepad.exe")
    """

    def __init__(self, safety_gate: SafetyGate | None = None):
        self._gate = safety_gate or SafetyGate()

    async def list_processes(
        self,
        sort_by: str = "memory",
        limit: int = 50,
        filter_name: str = "",
    ) -> ActionResult:
        """List running processes.

        Args:
            sort_by: Sort by "cpu", "memory", "pid", or "name".
            limit: Max processes to return.
            filter_name: Filter by process name substring.

        Returns:
            ActionResult with list of ProcessInfo objects.
        """
        start = time.perf_counter()
        try:
            ps_script = f"""
            $procs = Get-Process | Select-Object Id, ProcessName, CPU,
                @{{'N'='MemoryMB';E'{{[math]::Round($_.WorkingSet64/1MB, 1)}}}},
                Threads, StartTime, Path
            if ('{filter_name}') {{
                $procs = $procs | Where-Object {{$_.ProcessName -like '*{filter_name}*'}}
            }}
            switch ('{sort_by}') {{
                'cpu' {{ $procs = $procs | Sort-Object CPU -Descending }}
                'memory' {{ $procs = $procs | Sort-Object MemoryMB -Descending }}
                'pid' {{ $procs = $procs | Sort-Object Id }}
                'name' {{ $procs = $procs | Sort-Object ProcessName }}
            }}
            $procs | Select-Object -First {limit} | ConvertTo-Json -Compress
            """

            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            raw = stdout.decode(errors="ignore").strip()

            if not raw:
                return ActionResult(success=True, message="No processes found", data=[])

            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]

            processes = []
            for p in data:
                processes.append(ProcessInfo(
                    pid=p.get("Id", 0),
                    name=p.get("ProcessName", ""),
                    cpu_percent=p.get("CPU", 0) or 0,
                    memory_mb=p.get("MemoryMB", 0) or 0,
                    threads=p.get("Threads", 0) or 0,
                    started_at=str(p.get("StartTime", "")),
                    command=str(p.get("Path", "")),
                ))

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Found {len(processes)} processes",
                data=[p.to_dict() for p in processes],
                severity=ActionSeverity.SAFE,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"List processes failed: {exc}", duration_ms=elapsed)

    async def find(self, name: str | None = None, pid: int | None = None) -> ActionResult:
        """Find processes by name or PID.

        Args:
            name: Process name to search for.
            pid: Process ID to find.

        Returns:
            ActionResult with matching processes.
        """
        start = time.perf_counter()
        try:
            if pid:
                ps_cmd = f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, CPU, @{{'N'='MemoryMB';E'{{[math]::Round($_.WorkingSet64/1MB, 1)}}}}, Threads, Path | ConvertTo-Json -Compress"
            elif name:
                ps_cmd = f"Get-Process -Name '*{name}*' -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, CPU, @{{'N'='MemoryMB';E'{{[math]::Round($_.WorkingSet64/1MB, 1)}}}}, Threads, Path | ConvertTo-Json -Compress"
            else:
                return ActionResult(success=False, message="Specify name or pid")

            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            raw = stdout.decode(errors="ignore").strip()

            if not raw:
                return ActionResult(success=False, message=f"No process found for '{name or pid}'")

            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]

            processes = [ProcessInfo(
                pid=p.get("Id", 0),
                name=p.get("ProcessName", ""),
                cpu_percent=p.get("CPU", 0) or 0,
                memory_mb=p.get("MemoryMB", 0) or 0,
                threads=p.get("Threads", 0) or 0,
                command=str(p.get("Path", "")),
            ) for p in data]

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Found {len(processes)} process(es)",
                data=[p.to_dict() for p in processes],
                severity=ActionSeverity.SAFE,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Find failed: {exc}", duration_ms=elapsed)

    async def kill(
        self,
        name: str | None = None,
        pid: int | None = None,
        force: bool = False,
    ) -> ActionResult:
        """Kill a process by name or PID.

        Args:
            name: Process name to kill.
            pid: Process ID to kill.
            force: Force termination.

        Returns:
            ActionResult with success status.
        """
        start = time.perf_counter()
        target = name or str(pid)
        severity = ActionSeverity.DANGEROUS if force else ActionSeverity.MODERATE
        description = f"{'Force kill' if force else 'Stop'} process: {target}"

        if not await self._gate.check(severity, description, f"kill:{target}"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            if pid:
                flag = "/F" if force else ""
                proc = await asyncio.create_subprocess_exec(
                    "taskkill", flag, "/PID", str(pid),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            elif name:
                flag = "/F" if force else ""
                proc = await asyncio.create_subprocess_exec(
                    "taskkill", flag, "/IM", name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                return ActionResult(success=False, message="Specify name or pid")

            stdout, stderr = await proc.communicate()
            success = proc.returncode == 0
            msg = stdout.decode(errors="ignore").strip() or stderr.decode(errors="ignore").strip()

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=success,
                message=msg or f"Process {'killed' if force else 'stopped'}: {target}",
                severity=severity,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Kill failed: {exc}", duration_ms=elapsed)

    async def get_cpu_usage(self, name: str | None = None) -> ActionResult:
        """Get CPU usage for a process or system overall."""
        start = time.perf_counter()
        try:
            if name:
                ps_cmd = f"""
                $proc = Get-Process -Name '*{name}*' -ErrorAction SilentlyContinue |
                    Measure-Object CPU -Sum
                [PSCustomObject]@{{Name='{name}'; CPU=$proc.Sum}} | ConvertTo-Json -Compress
                """
            else:
                ps_cmd = """
                $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
                [PSCustomObject]@{Name='System'; CPU=$cpu} | ConvertTo-Json -Compress
                """

            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            data = json.loads(stdout.decode().strip())

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"CPU usage: {data.get('CPU', 0)}%",
                data=data,
                severity=ActionSeverity.SAFE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"CPU check failed: {exc}", duration_ms=elapsed)

    async def wait_for_exit(self, name: str, timeout_seconds: int = 30) -> ActionResult:
        """Wait for a process to exit.

        Args:
            name: Process name to wait for.
            timeout_seconds: Maximum wait time.
        """
        start = time.perf_counter()
        try:
            ps_cmd = f"""
            $timeout = {timeout_seconds}
            $elapsed = 0
            while ($elapsed -lt $timeout) {{
                $proc = Get-Process -Name '{name}' -ErrorAction SilentlyContinue
                if (-not $proc) {{ Write-Output 'exited'; break }}
                Start-Sleep -Seconds 1
                $elapsed++
            }}
            if ($elapsed -ge $timeout) {{ Write-Output 'timeout' }}
            """

            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            result = stdout.decode().strip()

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Process {result}",
                data={"status": result, "waited_seconds": elapsed / 1000},
                severity=ActionSeverity.SAFE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Wait failed: {exc}", duration_ms=elapsed)


import json
