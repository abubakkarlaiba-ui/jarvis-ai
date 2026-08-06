"""
Example skill: System Info Skill
==================================
Reports system information like CPU usage, memory, and disk space.
"""

from __future__ import annotations

import platform

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult


class SystemInfoSkill(BaseSkill):
    """Provides system information on demand.

    Example:
        User: "What's my system status?"
        JARVIS: "CPU: 45% | Memory: 8.2/16GB | Disk: 256GB free"
    """

    metadata = SkillMetadata(
        name="system_info",
        version="1.0.0",
        description="Reports CPU, memory, disk, and OS information",
        author="JARVIS Team",
        tags=["system", "info", "diagnostics"],
        required_features=["automation.desktop_enabled"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        """Gather and return system information.

        Returns:
            SkillResult with system stats.
        """
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            info = {
                "os": platform.system(),
                "os_version": platform.version(),
                "python": platform.python_version(),
                "hostname": platform.node(),
                "cpu_percent": cpu_percent,
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": round(memory.total / (1024**3), 1),
                "memory_used_gb": round(memory.used / (1024**3), 1),
                "memory_percent": memory.percent,
                "disk_total_gb": round(disk.total / (1024**3), 1),
                "disk_free_gb": round(disk.free / (1024**3), 1),
            }

            summary = (
                f"System: {info['os']} {info['os_version']}\n"
                f"CPU: {info['cpu_percent']}% ({info['cpu_count']} cores)\n"
                f"Memory: {info['memory_used_gb']}/{info['memory_total_gb']} GB ({info['memory_percent']}%)\n"
                f"Disk: {info['disk_free_gb']}/{info['disk_total_gb']} GB free"
            )

            return SkillResult(success=True, output=summary, metadata=info)

        except ImportError:
            return SkillResult(
                success=False,
                error="psutil not installed. Run: pip install psutil",
            )
