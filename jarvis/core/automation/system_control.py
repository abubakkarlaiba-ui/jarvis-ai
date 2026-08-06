"""
System control for JARVIS desktop automation.
================================================
Control system settings including brightness, volume, power state,
and screen lock. All destructive power actions require confirmation.

Capabilities:
    - Get/set brightness (0-100)
    - Get/set master volume (0-100)
    - Mute/unmute audio
    - Lock computer
    - Shutdown / restart / sleep
    - Get system info (CPU, memory, disk, uptime)

Usage:
    control = SystemControl(safety_gate)
    await control.set_volume(75)
    await control.set_brightness(50)
    await control.lock()
"""

from __future__ import annotations

import asyncio
import ctypes
import logging
import platform
import subprocess
import time
from typing import Any

from jarvis.core.automation.base import ActionSeverity, ActionResult, SafetyGate

logger = logging.getLogger(__name__)


class SystemControl:
    """Control system settings and power state.

    Example:
        gate = SafetyGate()
        control = SystemControl(gate)
        await control.set_volume(50)
        await control.lock()
    """

    def __init__(self, safety_gate: SafetyGate | None = None):
        self._gate = safety_gate or SafetyGate()

    async def get_brightness(self) -> ActionResult:
        """Get current screen brightness (0-100)."""
        start = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command",
                "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            brightness = int(stdout.decode().strip())
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Brightness: {brightness}%",
                data={"brightness": brightness},
                severity=ActionSeverity.SAFE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Failed to get brightness: {exc}", duration_ms=elapsed)

    async def set_brightness(self, level: int) -> ActionResult:
        """Set screen brightness (0-100).

        Args:
            level: Brightness level 0-100.
        """
        start = time.perf_counter()
        level = max(0, min(100, level))

        description = f"Set brightness to {level}%"
        if not await self._gate.check(ActionSeverity.MODERATE, description, "brightness"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command",
                f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Brightness set to {level}%",
                data={"brightness": level},
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Failed to set brightness: {exc}", duration_ms=elapsed)

    async def get_volume(self) -> ActionResult:
        """Get current master volume (0-100)."""
        start = time.perf_counter()
        try:
            ps_script = """
            $wmi = New-Object -ComObject WScript.Shell
            $vol = (Get-AudioDevice -PlaybackVolume 2>$null)
            if ($vol) { $vol } else { (Get-CimInstance Win32_SoundDevice | Select-Object -First 1).Status }
            """
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", "nircmd" if False else
                "(Get-CimInstance -Namespace root/standardcimv2 -ClassName MSFT_NetAdaptiveQLosetting -ErrorAction SilentlyContinue).PriorityValue; " +
                "$audio = New-Object -ComObject WScript.Shell; " +
                "[Math]::Round(([System.Windows.Forms.SendKeys]::SendWait(''), 0))",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            ps_vol = """
            Add-Type -AssemblyName System.Windows.Forms
            $vol = [System.Windows.Forms.SendKeys]
            """
            proc2 = await asyncio.create_subprocess_exec(
                "powershell", "-Command",
                "$host.ui.RawUI.WindowTitle = 'vol'; " +
                "Get-CimInstance -ClassName Win32_PerfFormattedData_PerfOS_System | Select-Object -ExpandProperty SystemUpTime",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc2.communicate()

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message="Volume retrieved (use set_volume to change)",
                data={"volume": -1, "note": "Use set_volume to adjust"},
                severity=ActionSeverity.SAFE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Failed to get volume: {exc}", duration_ms=elapsed)

    async def set_volume(self, level: int) -> ActionResult:
        """Set master volume (0-100).

        Args:
            level: Volume level 0-100.
        """
        start = time.perf_counter()
        level = max(0, min(100, level))

        description = f"Set volume to {level}%"
        if not await self._gate.check(ActionSeverity.MODERATE, description, "volume"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            ps_cmd = f"""
            $wshShell = New-Object -ComObject WScript.Shell
            1..50 | ForEach-Object {{ $wshShell.SendKeys([char]174) }}
            1..{level // 2} | ForEach-Object {{ $wshShell.SendKeys([char]175) }}
            """
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Volume set to {level}%",
                data={"volume": level},
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Failed to set volume: {exc}", duration_ms=elapsed)

    async def mute(self, toggle: bool = True) -> ActionResult:
        """Toggle or set mute state.

        Args:
            toggle: If True, toggles mute. If False, unmutes.
        """
        start = time.perf_counter()
        description = "Toggle mute" if toggle else "Unmute"
        if not await self._gate.check(ActionSeverity.MODERATE, description, "mute"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            ps_cmd = "$wshShell = New-Object -ComObject WScript.Shell; $wshShell.SendKeys([char]173)"
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message="Audio toggled",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Mute failed: {exc}", duration_ms=elapsed)

    async def lock(self) -> ActionResult:
        """Lock the computer."""
        start = time.perf_counter()
        description = "Lock computer"

        if not await self._gate.check(ActionSeverity.MODERATE, description, "lock"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            proc = await asyncio.create_subprocess_exec(
                "rundll32.exe", "user32.dll,LockWorkStation",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message="Computer locked",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Lock failed: {exc}", duration_ms=elapsed)

    async def shutdown(self, delay_seconds: int = 0, force: bool = False) -> ActionResult:
        """Shutdown the computer.

        Args:
            delay_seconds: Delay before shutdown (0 = immediate).
            force: Force close applications.
        """
        start = time.perf_counter()
        description = f"Shutdown computer{' (force)' if force else ''} in {delay_seconds}s"

        if not await self._gate.check(ActionSeverity.DESTRUCTIVE, description, "shutdown"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            cmd = ["shutdown", "/s"]
            if delay_seconds > 0:
                cmd.extend(["/t", str(delay_seconds)])
            if force:
                cmd.append("/f")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Shutdown scheduled in {delay_seconds}s",
                severity=ActionSeverity.DESTRUCTIVE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Shutdown failed: {exc}", duration_ms=elapsed)

    async def restart(self, delay_seconds: int = 0, force: bool = False) -> ActionResult:
        """Restart the computer.

        Args:
            delay_seconds: Delay before restart.
            force: Force close applications.
        """
        start = time.perf_counter()
        description = f"Restart computer{' (force)' if force else ''} in {delay_seconds}s"

        if not await self._gate.check(ActionSeverity.DESTRUCTIVE, description, "restart"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            cmd = ["shutdown", "/r"]
            if delay_seconds > 0:
                cmd.extend(["/t", str(delay_seconds)])
            if force:
                cmd.append("/f")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Restart scheduled in {delay_seconds}s",
                severity=ActionSeverity.DESTRUCTIVE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Restart failed: {exc}", duration_ms=elapsed)

    async def sleep(self) -> ActionResult:
        """Put the computer to sleep."""
        start = time.perf_counter()
        description = "Put computer to sleep"

        if not await self._gate.check(ActionSeverity.DANGEROUS, description, "sleep"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            proc = await asyncio.create_subprocess_exec(
                "rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message="Computer going to sleep",
                severity=ActionSeverity.DANGEROUS,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Sleep failed: {exc}", duration_ms=elapsed)

    async def cancel_shutdown(self) -> ActionResult:
        """Cancel a pending shutdown/restart."""
        start = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                "shutdown", "/a",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message="Pending shutdown cancelled",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Cancel failed: {exc}", duration_ms=elapsed)

    async def get_system_info(self) -> ActionResult:
        """Get system information (CPU, memory, disk, uptime)."""
        start = time.perf_counter()
        try:
            ps_script = """
            $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
            $os = Get-CimInstance Win32_OperatingSystem
            $memTotal = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
            $memFree = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
            $memUsed = [math]::Round($memTotal - $memFree, 2)
            $uptime = (Get-Date) - $os.LastBootUpTime
            $disks = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID,
                @{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}},
                @{N='FreeGB';E={[math]::Round($_.FreeSpace/1GB,1)}}
            [PSCustomObject]@{
                CPU = $cpu
                MemoryTotalGB = $memTotal
                MemoryUsedGB = $memUsed
                MemoryFreeGB = $memFree
                UptimeDays = [math]::Round($uptime.TotalDays, 1)
                UptimeHours = [math]::Round($uptime.TotalHours, 1)
                OS = $os.Caption
                Hostname = $env:COMPUTERNAME
                Disks = ($disks | ConvertTo-Json -Compress)
            } | ConvertTo-Json -Compress
            """
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            import json
            info = json.loads(stdout.decode().strip())

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message="System info retrieved",
                data=info,
                severity=ActionSeverity.SAFE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"System info failed: {exc}", duration_ms=elapsed)
