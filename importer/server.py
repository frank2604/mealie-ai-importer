"""FastAPI service exposing the Mealie importer pipeline."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .cli import _create_openai_client  # pylint: disable=protected-access
from .config import AppConfig, ConfigError, load_config
from .exceptions import UserAbort
from .modules import CachePaths, PipelineContext, PipelineRunner
from .modules.ai_analyser import AiAnalyserModule
from .modules.input import PdfInputModule
from .services.run_workspace import PipelineRecorder, RunInfo, RunWorkspace

logger = logging.getLogger(__name__)

UPLOAD_ROOT = Path("data/uploads")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

RUN_STATE_LOCK = Lock()
ACTIVE_RUNS: Dict[str, "RunState"] = {}
PENDING_UPLOADS: Dict[str, "PendingUpload"] = {}

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"\[(?P<level>[A-Z]+)\] "
    r"(?P<logger>[^:]+): "
    r"(?P<message>.*)$"
)


class UploadResponse(BaseModel):
    uploadId: str
    fileName: str
    recipeName: str


class StartAnalysisResponse(BaseModel):
    runId: str
    status: str
    recipeName: str
    startedAt: str


class RunStatusResponse(BaseModel):
    runId: str
    status: str
    recipeName: str
    startedAt: str
    completedAt: Optional[str] = None
    error: Optional[str] = None


class LogEntryModel(BaseModel):
    id: str
    level: str
    message: str
    timestamp: str


class LogResponse(BaseModel):
    runId: str
    entries: List[LogEntryModel]
    nextCursor: int


@dataclass
class PendingUpload:
    upload_id: str
    file_path: Path
    original_name: str
    recipe_name: str
    created_at: str


@dataclass
class RunState:
    run_id: str
    upload_id: str
    recipe_name: str
    status: str
    started_at: str
    log_file: Path
    pipeline_dir: Path
    error: Optional[str] = None
    completed_at: Optional[str] = None


app = FastAPI(title="Mealie Importer API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _now_utc() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _load_app_config() -> AppConfig:
    try:
        return load_config()
    except ConfigError as exc:
        logger.exception("Konfiguration konnte nicht geladen werden")
        raise HTTPException(status_code=500, detail=f"Konfiguration ungültig: {exc}") from exc


def _assert_no_running_job() -> None:
    with RUN_STATE_LOCK:
        busy = any(state.status in {"starting", "running"} for state in ACTIVE_RUNS.values())
    if busy:
        raise HTTPException(status_code=409, detail="Ein anderer Importlauf ist noch aktiv.")


def _store_pending_upload(path: Path, original_name: str) -> PendingUpload:
    upload_id = uuid4().hex
    pending = PendingUpload(
        upload_id=upload_id,
        file_path=path,
        original_name=original_name,
        recipe_name=Path(original_name).stem or "import",
        created_at=_now_utc(),
    )
    with RUN_STATE_LOCK:
        PENDING_UPLOADS[upload_id] = pending
    return pending


def _pop_pending_upload(upload_id: str) -> PendingUpload:
    with RUN_STATE_LOCK:
        pending = PENDING_UPLOADS.pop(upload_id, None)
    if not pending:
        raise HTTPException(status_code=404, detail="Upload nicht gefunden oder bereits gestartet.")
    return pending


def _register_run_state(pending: PendingUpload, run_info: RunInfo, pipeline_dir: Path) -> RunState:
    state = RunState(
        run_id=run_info.run_id,
        upload_id=pending.upload_id,
        recipe_name=pending.recipe_name,
        status="starting",
        started_at=run_info.started_at,
        log_file=Path(run_info.log_file or pipeline_dir / f"{run_info.run_id}_run.log"),
        pipeline_dir=pipeline_dir,
    )
    with RUN_STATE_LOCK:
        ACTIVE_RUNS[state.run_id] = state
    return state


def _update_run_state(run_id: str, *, status: Optional[str] = None, error: Optional[str] = None, completed_at: Optional[str] = None) -> None:
    with RUN_STATE_LOCK:
        state = ACTIVE_RUNS.get(run_id)
        if not state:
            return
        if status:
            state.status = status
        if error:
            state.error = error
        if completed_at:
            state.completed_at = completed_at


def _read_run_state(run_id: str) -> RunState:
    with RUN_STATE_LOCK:
        state = ACTIVE_RUNS.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Importlauf nicht gefunden.")
    return state


def _build_workspace(config: AppConfig) -> RunWorkspace:
    pipeline_dir = Path(config.processing.output_folder)
    cache_dir = Path(config.ingredients.cache_dir)
    data_root = pipeline_dir.parent if pipeline_dir.parent != pipeline_dir else Path("data")
    return RunWorkspace(
        pipeline_dir=pipeline_dir,
        cache_dir=cache_dir,
        log_dir=data_root / "log",
        archive_dir=data_root / "archive",
    )


def _run_analysis(run_state: RunState, pending: PendingUpload, config: AppConfig, workspace: RunWorkspace, run_info: RunInfo) -> None:
    logger.info("Starte Analyse für Lauf %s (%s)", run_state.run_id, run_state.recipe_name)
    try:
        llm_client = _create_openai_client(config.llm)
    except ValueError as exc:
        logger.error("LLM-Konfiguration fehlerhaft: %s", exc)
        _update_run_state(run_state.run_id, status="failed", error=str(exc), completed_at=_now_utc())
        return

    log_file = Path(run_info.log_file) if run_info.log_file else run_state.log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))

    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    try:
        _update_run_state(run_state.run_id, status="running")

        recorder = PipelineRecorder(workspace.pipeline_dir)
        recorder.copy_file(pending.file_path, label=run_state.recipe_name)

        cache_paths = CachePaths(Path(config.ingredients.cache_dir))
        context = PipelineContext(
            source_pdf=pending.file_path,
            output_dir=workspace.pipeline_dir,
            config=config,
            cache_paths=cache_paths,
            pipeline_recorder=recorder,
            run_id=run_state.run_id,
            log_file=log_file,
        )

        modules = [
            PdfInputModule(),
            AiAnalyserModule(
                llm_client=llm_client,
                llm_config=config.llm,
                image_output_dir=workspace.pipeline_dir,
            ),
        ]

        runner = PipelineRunner(modules)
        try:
            runner.run(context)
        except UserAbort as exc:
            logger.warning("Pipeline vom Benutzer abgebrochen: %s", exc)
            run_info.mark_completed(status="aborted")
            workspace.save_run_info(run_info)
            _update_run_state(run_state.run_id, status="aborted", completed_at=_now_utc(), error=str(exc))
            return

        run_info.mark_completed(status="completed")
        workspace.save_run_info(run_info)
        _update_run_state(run_state.run_id, status="completed", completed_at=run_info.completed_at or _now_utc())
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Analyse fehlgeschlagen: %s", exc)
        _update_run_state(run_state.run_id, status="failed", error=str(exc), completed_at=_now_utc())
    finally:
        root_logger.removeHandler(file_handler)
        file_handler.close()
        try:
            pending.file_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Hochgeladene Datei konnte nicht gelöscht werden: %s", pending.file_path)


def _parse_log_entries(run_state: RunState, after: int) -> LogResponse:
    log_file = run_state.log_file
    if not log_file.exists():
        return LogResponse(runId=run_state.run_id, entries=[], nextCursor=after)

    entries: List[LogEntryModel] = []
    total = 0
    with log_file.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            total = index + 1
            if index < after:
                continue
            text = line.strip()
            if not text:
                continue
            match = LOG_PATTERN.match(text)
            if match:
                raw_level = match.group("level")
                message = match.group("message")
                timestamp = match.group("timestamp") + "Z"
            else:
                raw_level = "INFO"
                message = text
                timestamp = run_state.started_at
            level = _normalize_level(raw_level)
            entries.append(
                LogEntryModel(
                    id=f"{run_state.run_id}-{index}",
                    level=level,
                    message=message,
                    timestamp=timestamp,
                )
            )
    return LogResponse(runId=run_state.run_id, entries=entries, nextCursor=total)


def _normalize_level(level_name: str) -> str:
    normalized = level_name.upper()
    if normalized in {"INFO", "WARN", "ERROR"}:
        return "WARN" if normalized == "WARN" else normalized
    if normalized == "WARNING":
        return "WARN"
    if normalized in {"CRITICAL", "EXCEPTION"}:
        return "ERROR"
    if normalized == "DEBUG":
        return "INFO"
    return "INFO"


@app.post("/api/imports/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    if file.content_type not in {"application/pdf", "application/x-pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Es werden nur PDF-Dateien unterstützt.")

    file_suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    pending_path = UPLOAD_ROOT / f"{uuid4().hex}{file_suffix}"

    try:
        with pending_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
    finally:
        await file.close()

    pending = _store_pending_upload(pending_path, file.filename or pending_path.name)
    logger.info("PDF %s unter %s gespeichert (Upload-ID %s)", pending.original_name, pending.file_path, pending.upload_id)
    return UploadResponse(uploadId=pending.upload_id, fileName=pending.original_name, recipeName=pending.recipe_name)


@app.post("/api/imports/{upload_id}/start", response_model=StartAnalysisResponse)
async def start_analysis(upload_id: str, background_tasks: BackgroundTasks) -> StartAnalysisResponse:
    pending = _pop_pending_upload(upload_id)
    _assert_no_running_job()
    config = _load_app_config()

    workspace = _build_workspace(config)
    run_info = workspace.start_run(recipe_name=pending.recipe_name, source_pdf=pending.file_path)
    run_state = _register_run_state(pending, run_info, workspace.pipeline_dir)

    background_tasks.add_task(_run_analysis, run_state, pending, config, workspace, run_info)

    return StartAnalysisResponse(
        runId=run_state.run_id,
        status=run_state.status,
        recipeName=run_state.recipe_name,
        startedAt=run_state.started_at,
    )


@app.get("/api/imports/{run_id}", response_model=RunStatusResponse)
async def get_run_status(run_id: str) -> RunStatusResponse:
    state = _read_run_state(run_id)
    return RunStatusResponse(
        runId=state.run_id,
        status=state.status,
        recipeName=state.recipe_name,
        startedAt=state.started_at,
        completedAt=state.completed_at,
        error=state.error,
    )


@app.get("/api/imports/{run_id}/logs", response_model=LogResponse)
async def get_run_logs(run_id: str, after: int = 0) -> LogResponse:
    state = _read_run_state(run_id)
    return _parse_log_entries(state, after)


@app.get("/api/health")
async def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


__all__ = ["app"]
