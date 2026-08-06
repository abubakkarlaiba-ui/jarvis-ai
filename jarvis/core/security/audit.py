from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from jarvis.core.security.base import AuditAction, AuditEntry


class AuditLogger:
    """Comprehensive audit logging for all security-relevant actions."""

    def __init__(self, log_dir: str = "./data/security/audits", max_entries: int = 10000) -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._max_entries = max_entries

    def log(
        self,
        action: AuditAction,
        user_id: str = "",
        username: str = "",
        resource: str = "",
        details: dict | None = None,
        ip_address: str = "",
        success: bool = True,
        error: str = "",
    ) -> AuditEntry:
        entry = AuditEntry(
            action=action,
            user_id=user_id,
            username=username,
            resource=resource,
            details=details or {},
            ip_address=ip_address,
            success=success,
            error=error,
        )
        self._write_entry(entry)
        return entry

    def log_login(self, user_id: str, username: str, success: bool, ip: str = "", error: str = "") -> AuditEntry:
        return self.log(AuditAction.LOGIN, user_id=user_id, username=username, ip_address=ip, success=success, error=error)

    def log_logout(self, user_id: str, username: str) -> AuditEntry:
        return self.log(AuditAction.LOGOUT, user_id=user_id, username=username)

    def log_permission_change(self, user_id: str, username: str, target: str, action: str, permission: str) -> AuditEntry:
        return self.log(
            AuditAction.PERMISSION_GRANT if "grant" in action.lower() else AuditAction.PERMISSION_REVOKE,
            user_id=user_id,
            username=username,
            resource=target,
            details={"action": action, "permission": permission},
        )

    def log_skill_execution(self, user_id: str, skill_name: str, success: bool) -> AuditEntry:
        return self.log(AuditAction.SKILL_EXECUTE, user_id=user_id, resource=skill_name, success=success)

    def log_workflow_execution(self, user_id: str, workflow_id: str, success: bool) -> AuditEntry:
        return self.log(AuditAction.WORKFLOW_EXECUTE, user_id=user_id, resource=workflow_id, success=success)

    def log_file_access(self, user_id: str, file_path: str, action: str) -> AuditEntry:
        return self.log(AuditAction.FILE_ACCESS, user_id=user_id, resource=file_path, details={"action": action})

    def log_api_key(self, user_id: str, action: str, key_name: str) -> AuditEntry:
        audit_action = AuditAction.API_KEY_CREATE if "create" in action.lower() else AuditAction.API_KEY_REVOKE
        return self.log(audit_action, user_id=user_id, resource=key_name, details={"action": action})

    def log_security_violation(self, user_id: str, details: dict) -> AuditEntry:
        return self.log(AuditAction.SECURITY_VIOLATION, user_id=user_id, details=details, success=False)

    def log_rate_limit(self, user_id: str, ip: str, endpoint: str) -> AuditEntry:
        return self.log(AuditAction.RATE_LIMIT_HIT, user_id=user_id, ip_address=ip, resource=endpoint, success=False)

    def query(
        self,
        user_id: str | None = None,
        action: AuditAction | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        results: list[AuditEntry] = []
        dates_to_scan: list[datetime] = []

        if start_time and end_time:
            current = start_time.date()
            end = end_time.date()
            while current <= end:
                dates_to_scan.append(datetime.combine(current, datetime.min.time()))
                current += timedelta(days=1)
        elif start_time:
            dates_to_scan.append(start_time)
        else:
            dates_to_scan.append(datetime.now())

        for date in dates_to_scan:
            for entry in self._load_entries(date):
                if user_id and entry.user_id != user_id:
                    continue
                if action and entry.action != action:
                    continue
                if start_time and entry.timestamp < start_time:
                    continue
                if end_time and entry.timestamp > end_time:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    return results

        return results

    def get_recent(self, count: int = 50) -> list[AuditEntry]:
        entries: list[AuditEntry] = []
        today = datetime.now()
        for i in range(7):
            date = today - timedelta(days=i)
            entries.extend(self._load_entries(date))
            if len(entries) >= count:
                break
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:count]

    def get_user_history(self, user_id: str, count: int = 50) -> list[AuditEntry]:
        entries = self.query(user_id=user_id, limit=count * 2)
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:count]

    def get_summary(self, start_time: datetime | None = None, end_time: datetime | None = None) -> dict:
        entries = self.query(start_time=start_time, end_time=end_time, limit=self._max_entries)
        summary: dict[str, int] = {}
        for entry in entries:
            key = entry.action.value
            summary[key] = summary.get(key, 0) + 1
        return {"total": len(entries), "by_action": summary}

    def export_logs(self, format: str = "json", start_time: datetime | None = None, end_time: datetime | None = None) -> str:
        entries = self.query(start_time=start_time, end_time=end_time, limit=self._max_entries)
        if format == "json":
            data = [
                {
                    "id": e.id,
                    "timestamp": e.timestamp.isoformat(),
                    "user_id": e.user_id,
                    "username": e.username,
                    "action": e.action.value,
                    "resource": e.resource,
                    "details": e.details,
                    "ip_address": e.ip_address,
                    "success": e.success,
                    "error": e.error,
                }
                for e in entries
            ]
            return json.dumps(data, indent=2)
        elif format == "csv":
            lines = ["id,timestamp,user_id,username,action,resource,ip_address,success,error"]
            for e in entries:
                lines.append(f"{e.id},{e.timestamp.isoformat()},{e.user_id},{e.username},{e.action.value},{e.resource},{e.ip_address},{e.success},{e.error}")
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _write_entry(self, entry: AuditEntry) -> None:
        date_str = entry.timestamp.strftime("%Y-%m-%d")
        file_path = self._log_dir / f"{date_str}.jsonl"
        record = {
            "id": entry.id,
            "timestamp": entry.timestamp.isoformat(),
            "user_id": entry.user_id,
            "username": entry.username,
            "action": entry.action.value,
            "resource": entry.resource,
            "details": entry.details,
            "ip_address": entry.ip_address,
            "success": entry.success,
            "error": entry.error,
        }
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def _load_entries(self, date: datetime | None = None) -> list[AuditEntry]:
        if date is None:
            date = datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        file_path = self._log_dir / f"{date_str}.jsonl"
        if not file_path.exists():
            return []
        entries: list[AuditEntry] = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(
                        AuditEntry(
                            id=data.get("id", ""),
                            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
                            user_id=data.get("user_id", ""),
                            username=data.get("username", ""),
                            action=AuditAction(data.get("action", "login")),
                            resource=data.get("resource", ""),
                            details=data.get("details", {}),
                            ip_address=data.get("ip_address", ""),
                            success=data.get("success", True),
                            error=data.get("error", ""),
                        )
                    )
                except (json.JSONDecodeError, ValueError):
                    continue
        return entries
