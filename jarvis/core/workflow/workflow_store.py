"""
Workflow Engine — persistence and resumption.
==============================================
Provides WorkflowStore for saving, loading, and managing workflow state on disk.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from jarvis.core.workflow.base import StepResult, Workflow, WorkflowStatus


class WorkflowStore:
    """Persist and resume workflows via atomic JSON files.

    Directory layout::

        store_dir/
            active/        # running or paused workflows
            completed/     # successfully finished
            failed/        # workflows that terminated with an error
            archived/      # old / cleaned-up workflows
    """

    def __init__(self, store_dir: str = "./data/workflows") -> None:
        self.store_dir = Path(store_dir)
        self._ensure_dirs()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, workflow: Workflow) -> None:
        """Persist a workflow to its active JSON file (atomic write)."""
        path = self._workflow_path(workflow.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = workflow.__dict__.copy()
        # serialise enums and datetimes
        data["status"] = workflow.status.name
        data["created_at"] = workflow.created_at.isoformat()
        data["started_at"] = (
            workflow.started_at.isoformat() if workflow.started_at else None
        )
        data["completed_at"] = (
            workflow.completed_at.isoformat()
            if workflow.completed_at
            else None
        )
        for step in data.get("steps", []):
            if isinstance(step, dict):
                step["step_type"] = step.get("step_type", "")
                step["risk"] = step.get("risk", "")
                step["status"] = step.get("status", "")
        for res in data.get("results", []):
            if isinstance(res, dict):
                res["status"] = res.get("status", "")

        self._atomic_write(path, data)

    def load(self, workflow_id: str) -> Workflow | None:
        """Load a workflow from disk. Returns None if not found."""
        path = self._workflow_path(workflow_id)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        return self._deserialise(raw)

    def delete(self, workflow_id: str) -> bool:
        """Delete a workflow file. Returns True if the file existed."""
        path = self._workflow_path(workflow_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_workflows(
        self,
        status: WorkflowStatus | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List workflows with basic metadata.

        If *status* is provided only workflows in that status are returned.
        """
        results: list[dict] = []
        for folder in ("active", "completed", "failed", "archived"):
            directory = self.store_dir / folder
            if not directory.exists():
                continue
            for p in sorted(directory.glob("*.json"), reverse=True):
                if len(results) >= limit:
                    break
                try:
                    with open(p, encoding="utf-8") as fh:
                        raw = json.load(fh)
                except (json.JSONDecodeError, OSError):
                    continue
                wf_status = raw.get("status", "")
                if status and wf_status != status.name:
                    continue
                results.append(
                    {
                        "workflow_id": raw.get("id", p.stem),
                        "name": raw.get("name", ""),
                        "status": wf_status,
                        "created_at": raw.get("created_at", ""),
                        "folder": folder,
                    }
                )
        return results[:limit]

    # ------------------------------------------------------------------
    # Step results
    # ------------------------------------------------------------------

    def save_step_result(
        self, workflow_id: str, result: StepResult
    ) -> None:
        """Append a step result to an existing workflow file."""
        wf = self.load(workflow_id)
        if wf is None:
            return
        wf.results.append(result)
        self.save(wf)

    # ------------------------------------------------------------------
    # Resumption & archival
    # ------------------------------------------------------------------

    def get_resumable(self) -> list[dict]:
        """Find workflows that were interrupted and can be resumed."""
        resumable: list[dict] = []
        for wf_data in self.list_workflows(status=WorkflowStatus.INTERRUPTED):
            resumable.append(wf_data)
        # Also include paused workflows
        for wf_data in self.list_workflows(status=WorkflowStatus.PAUSED):
            resumable.append(wf_data)
        return resumable

    def archive(self, workflow_id: str) -> None:
        """Move a completed workflow into the archive directory."""
        src = self.store_dir / "completed" / f"{workflow_id}.json"
        dst = self.store_dir / "archived" / f"{workflow_id}.json"
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return summary statistics for stored workflows."""
        counts: dict[str, int] = {
            "total": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "paused": 0,
            "interrupted": 0,
            "archived": 0,
        }
        for folder in ("active", "completed", "failed", "archived"):
            directory = self.store_dir / folder
            if not directory.exists():
                continue
            for p in directory.glob("*.json"):
                counts["total"] += 1
                try:
                    with open(p, encoding="utf-8") as fh:
                        raw = json.load(fh)
                    st = raw.get("status", "")
                    key = st.lower()
                    if key in counts:
                        counts[key] += 1
                    if folder == "archived":
                        counts["archived"] += 1
                except (json.JSONDecodeError, OSError):
                    continue
        return counts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _workflow_path(self, workflow_id: str) -> Path:
        """Return the expected file path for a workflow.

        If the file already exists under a status folder, return that path.
        Otherwise default to ``active/``.
        """
        for folder in ("active", "completed", "failed", "archived"):
            candidate = self.store_dir / folder / f"{workflow_id}.json"
            if candidate.exists():
                return candidate
        return self.store_dir / "active" / f"{workflow_id}.json"

    def _ensure_dirs(self) -> None:
        """Create the store directory tree if it does not exist."""
        for sub in ("active", "completed", "failed", "archived"):
            (self.store_dir / sub).mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, path: Path, data: dict) -> None:
        """Write *data* as JSON to *path* atomically via a temp file."""
        dir_ = path.parent
        fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp, path)
        except BaseException:
            # clean up temp file on failure
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @staticmethod
    def _deserialise(raw: dict) -> Workflow:
        """Reconstruct a Workflow object from a plain dict."""
        from jarvis.core.workflow.base import Step, StepType, StepRisk, StepStatus

        def _enum(val: str, enum_cls):
            try:
                return enum_cls[val]
            except KeyError:
                return list(enum_cls)[0]

        steps = []
        for s in raw.get("steps", []):
            steps.append(
                Step(
                    id=s.get("id", ""),
                    name=s.get("name", ""),
                    description=s.get("description", ""),
                    step_type=_enum(s.get("step_type", "CODE"), StepType),
                    risk=_enum(s.get("risk", "LOW"), StepRisk),
                    command=s.get("command", ""),
                    params=s.get("params", {}),
                    timeout=s.get("timeout", 300.0),
                    depends_on=s.get("depends_on", []),
                    max_retries=s.get("max_retries", 0),
                    retry_delay=s.get("retry_delay", 1.0),
                    retry_backoff=s.get("retry_backoff", 2.0),
                    status=_enum(s.get("status", "PENDING"), StepStatus),
                    started_at=_parse_dt(s.get("started_at")),
                    completed_at=_parse_dt(s.get("completed_at")),
                    metadata=s.get("metadata", {}),
                    tags=s.get("tags", []),
                )
            )

        results = []
        for r in raw.get("results", []):
            results.append(
                StepResult(
                    step_id=r.get("step_id", ""),
                    status=_enum(r.get("status", "SUCCESS"), StepStatus),
                    output=r.get("output"),
                    error=r.get("error", ""),
                    duration=r.get("duration", 0.0),
                    retries=r.get("retries", 0),
                    metadata=r.get("metadata", {}),
                )
            )

        return Workflow(
            id=raw.get("id", ""),
            name=raw.get("name", ""),
            description=raw.get("description", ""),
            steps=steps,
            status=_enum(raw.get("status", "CREATED"), WorkflowStatus),
            created_at=_parse_dt(raw.get("created_at")) or datetime.now(),
            started_at=_parse_dt(raw.get("started_at")),
            completed_at=_parse_dt(raw.get("completed_at")),
            variables=raw.get("variables", {}),
            tags=raw.get("tags", []),
            auto_retry=raw.get("auto_retry", True),
            pause_on_error=raw.get("pause_on_error", False),
            current_step_index=raw.get("current_step_index", 0),
            results=results,
            metadata=raw.get("metadata", {}),
            error=raw.get("error", ""),
        )


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO datetime string, returning None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
