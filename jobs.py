import uuid
import threading
from dataclasses import dataclass, field
from typing import Optional
from fastapi import HTTPException

_jobs: dict[str, "Job"] = {}
_jobs_lock = threading.Lock()

@dataclass
class Job:
    id: str
    status: str = "queued"
    progress: int = 0
    message: str = "В очереди…"
    log_lines: list[str] = field(default_factory=list)
    result: Optional[dict] = None
    error: Optional[str] = None

    def log(self, line: str, *, progress: Optional[int] = None, status: Optional[str] = None) -> None:
        line = line.strip()
        if not line:
            return
        with _jobs_lock:
            self.log_lines.append(line)
            if len(self.log_lines) > 120:
                self.log_lines = self.log_lines[-120:]
            self.message = line if len(line) < 200 else line[:197] + "…"
            if progress is not None:
                self.progress = max(0, min(100, progress))
            if status is not None:
                self.status = status
            
            # Вывод в консоль для .exe/терминала
            prog_str = f" [{self.progress}%]" if self.progress > 0 or progress is not None else ""
            print(f"[Задача {self.id}] [{self.status}]{prog_str} {line}", flush=True)

    def to_dict(self) -> dict:
        with _jobs_lock:
            return {
                "id": self.id,
                "status": self.status,
                "progress": self.progress,
                "message": self.message,
                "log_lines": list(self.log_lines[-30:]),
                "result": self.result,
                "error": self.error,
            }

def _create_job() -> Job:
    job = Job(id=uuid.uuid4().hex[:12])
    with _jobs_lock:
        _jobs[job.id] = job
    return job

def _get_job(job_id: str) -> Job:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return job
