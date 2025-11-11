"""Helpers for managing run-specific storage and pipeline artifacts."""
from __future__ import annotations

import json
import logging
import shutil
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional


def _now_utc() -> str:
    """Return an ISO 8601 timestamp (UTC)."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def normalize_for_filename(value: str, *, fallback: str = "artifact") -> str:
    """Return a filesystem-safe representation for *value*."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(char if char.isalnum() else "_" for char in ascii_only).strip("_")
    return cleaned or fallback


# Backwards-compatibility alias for internal usage
_normalize_filename = normalize_for_filename


def format_log_reference(base_dir: Path, path: Path, *, prefix: str = "pipeline") -> str:
    """Return a readable path reference for log output."""
    try:
        relative = path.relative_to(base_dir)
        return f"{prefix}/{relative}"
    except ValueError:
        return str(path)


@dataclass
class RunInfo:
    """Persisted metadata about a pipeline run."""

    run_id: str
    recipe_name: str
    started_at: str
    status: str = "running"
    completed_at: Optional[str] = None
    source_pdf: Optional[str] = None
    log_file: Optional[str] = None
    analysis_log_file: Optional[str] = None
    transfer_log_file: Optional[str] = None

    def mark_completed(self, *, status: str = "completed") -> None:
        self.status = status
        self.completed_at = _now_utc()


class PipelineRecorder:
    """Create sequential, numbered artifacts within ``data/pipeline``."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)
        self._counter = 0

    @property
    def directory(self) -> Path:
        return self._directory

    def _next_path(self, label: str, suffix: str) -> Path:
        self._counter += 1
        filename = f"{self._counter:02d}_{_normalize_filename(label)}{suffix}"
        return self._directory / filename

    def write_json(self, label: str, payload: Any) -> Path:
        """Serialize *payload* to JSON and store it with an incremented prefix."""
        path = self._next_path(label, ".json")
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return path

    def write_text(self, label: str, content: str) -> Path:
        """Write textual content to a numbered artifact."""
        path = self._next_path(label, ".txt")
        path.write_text(content, encoding="utf-8")
        return path

    def write_bytes(self, label: str, data: bytes, *, suffix: str) -> Path:
        """Persist binary data with a custom suffix (e.g. ``.pdf`` or ``.jpg``)."""
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        path = self._next_path(label, suffix)
        path.write_bytes(data)
        return path

    def copy_file(self, source: Path, *, label: Optional[str] = None) -> Path:
        """Copy *source* into the pipeline directory with an incremented prefix."""
        label_text = label or source.stem
        suffix = source.suffix or ""
        path = self._next_path(label_text, suffix)
        shutil.copy2(source, path)
        return path

    def child(self, prefix: str) -> "PipelineRecorderProxy":
        """Return a proxy that prefixes all labels with *prefix*."""
        return PipelineRecorderProxy(self, prefix=prefix)


class PipelineRecorderProxy:
    """Adapter ensuring compatibility with existing ``.write`` usage."""

    def __init__(self, recorder: PipelineRecorder, *, prefix: str) -> None:
        self._recorder = recorder
        self._prefix = prefix

    def write(self, label: str, payload: Any) -> Path:
        combined = f"{self._prefix}_{label}" if label else self._prefix
        return self._recorder.write_json(combined, payload)


@dataclass(frozen=True)
class ApiLabel:
    """Describe how a recorder label translates to logging and filenames."""

    method: str
    endpoint: str
    suffix: str
    entity_field: Optional[str] = None
    include_entity: bool = True
    action_template: Optional[str] = None

    def render_action(self, *, entity: Optional[str]) -> Optional[str]:
        """Return a human-friendly action description if configured."""
        if not self.action_template:
            return None
        substitution = entity or "this item"
        try:
            return self.action_template.format(entity=substitution)
        except (KeyError, IndexError, ValueError):
            return self.action_template


class ApiPayloadRecorder:
    """Record API payloads via the pipeline recorder and emit log references."""

    def __init__(
        self,
        *,
        recorder: Optional[PipelineRecorder],
        logger: logging.Logger,
        label_prefix: str,
        mapping: Mapping[str, ApiLabel],
        fallback_dir: Path,
        reference_prefix: str = "pipeline",
    ) -> None:
        self._primary = recorder
        self._logger = logger
        self._mapping = dict(mapping)
        self._label_prefix = label_prefix
        self._reference_prefix = reference_prefix
        self._fallback = None if recorder else PipelineRecorder(fallback_dir)

    def write(self, label: str, payload: Any) -> Path:
        recorder = self._primary or self._fallback
        if recorder is None:
            raise RuntimeError("No recorder configured for API payloads")

        info = self._mapping.get(label)
        if info:
            file_label = self._build_file_label(info, payload)
        else:
            file_label = f"{self._label_prefix}_{label}"

        path = recorder.write_json(file_label, payload)
        if info:
            base_dir = self._primary.directory if self._primary else recorder.directory
            prefix = self._reference_prefix if self._primary else "debug"
            reference = format_log_reference(base_dir, path, prefix=prefix)
            entity = self._extract_entity(payload, info)
            action_text = info.render_action(entity=entity)
            if not action_text:
                action_text = self._default_action_text(info, entity)
            self._logger.info(
                "%s (%s %s) - payload file: %s",
                action_text,
                info.method.upper(),
                info.endpoint,
                reference,
            )
        return path

    def _extract_entity(self, payload: Any, info: ApiLabel) -> Optional[str]:
        field = info.entity_field
        if not field:
            return None
        parts = field.split(".")
        value: Any = payload
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        if isinstance(value, str):
            return value
        return None

    def _build_file_label(self, info: ApiLabel, payload: Any) -> str:
        endpoint_label = info.endpoint.strip("/").replace("/", "_")
        endpoint_label = endpoint_label.replace("{", "").replace("}", "")
        base = f"{self._label_prefix}_{info.method.upper()}_{endpoint_label}_{info.suffix}"
        entity = self._extract_entity(payload, info) if info.include_entity else None
        if entity:
            base = f"{base}_{normalize_for_filename(entity)}"
        return base

    @staticmethod
    def _default_action_text(info: ApiLabel, entity: Optional[str]) -> str:
        if entity:
            return f'Working with "{entity}" in Mealie'
        return f"Contacting Mealie ({info.method.upper()} {info.endpoint})"


class RunWorkspace:
    """Coordinate run directories (pipeline, cache, log, archive)."""

    def __init__(
        self,
        *,
        pipeline_dir: Path,
        cache_dir: Path,
        log_dir: Optional[Path],
        archive_dir: Path,
    ) -> None:
        self._pipeline_dir = pipeline_dir
        self._cache_dir = cache_dir
        self._log_dir = log_dir
        self._archive_dir = archive_dir

        self._pipeline_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        if self._log_dir is not None:
            self._log_dir.mkdir(parents=True, exist_ok=True)
        (self._archive_dir / "recipes").mkdir(parents=True, exist_ok=True)
        (self._archive_dir / "foods").mkdir(parents=True, exist_ok=True)
        (self._archive_dir / "units").mkdir(parents=True, exist_ok=True)

    @property
    def pipeline_dir(self) -> Path:
        return self._pipeline_dir

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    @property
    def log_dir(self) -> Optional[Path]:
        return self._log_dir

    @property
    def archive_dir(self) -> Path:
        return self._archive_dir

    @property
    def run_info_path(self) -> Path:
        return self._pipeline_dir / ".run_info.json"

    def load_run_info(self) -> Optional[RunInfo]:
        path = self.run_info_path
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return RunInfo(**data)

    def save_run_info(self, info: RunInfo) -> None:
        self.run_info_path.write_text(
            json.dumps(asdict(info), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def archive_previous_run(self) -> None:
        """Move leftover results from the previous run into the archive."""
        info = self.load_run_info()
        if not info:
            return
        self._archive_run(info)

    def archive_current_run(self, info: RunInfo) -> Path:
        """Archive the current run immediately and return the archive root."""
        return self._archive_run(info)

    def reset_current_run(self) -> None:
        """Remove any run artifacts without archiving them."""
        if self.run_info_path.exists():
            self.run_info_path.unlink()
        self._clear_directory(self._pipeline_dir)
        self._clear_directory(self._cache_dir)
        if self._log_dir is not None:
            self._clear_directory(self._log_dir)

    def _archive_run(self, info: RunInfo) -> Path:
        recipe_dir_name = _normalize_filename(info.recipe_name, fallback=info.run_id)
        archive_root = (
            self._archive_dir
            / "recipes"
            / recipe_dir_name
            / info.run_id
        )
        pipeline_target = archive_root / "pipeline"
        cache_target = archive_root / "cache"
        log_target = archive_root / "log"

        archive_root.mkdir(parents=True, exist_ok=True)
        pipeline_target.mkdir(parents=True, exist_ok=True)
        cache_target.mkdir(parents=True, exist_ok=True)
        log_target.mkdir(parents=True, exist_ok=True)

        self._move_contents(self._pipeline_dir, pipeline_target, ignore_files={self.run_info_path.name})
        self._move_contents(self._cache_dir, cache_target)
        if self._log_dir is not None:
            self._move_contents(self._log_dir, log_target)

        self._copy_api_payloads(
            pipeline_target.iterdir(),
            recipe_dir_name=recipe_dir_name,
            run_id=info.run_id,
        )

        if self.run_info_path.exists():
            self.run_info_path.unlink()

        self._clear_directory(self._pipeline_dir)
        self._clear_directory(self._cache_dir)
        if self._log_dir is not None:
            self._clear_directory(self._log_dir)

        return archive_root

    def _move_contents(self, source: Path, destination: Path, *, ignore_files: Optional[Iterable[str]] = None) -> None:
        if not source.exists():
            return
        ignore = set(ignore_files or [])
        for entry in source.iterdir():
            if entry.name in ignore:
                continue
            target = destination / entry.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            shutil.move(str(entry), str(target))

    def _copy_api_payloads(self, entries: Iterable[Path], *, recipe_dir_name: str, run_id: str) -> None:
        for entry in entries:
            if not entry.is_file():
                continue
            name = entry.name.lower()
            archive_base: Optional[Path] = None
            if "_api_foods_" in name:
                archive_base = self._archive_dir / "foods"
            elif "_api_units_" in name:
                archive_base = self._archive_dir / "units"
            if not archive_base:
                continue
            destination_name = entry.name
            target_path = archive_base / destination_name
            if target_path.exists():
                stem = target_path.stem
                suffix = target_path.suffix
                counter = 1
                while target_path.exists():
                    destination_name = f"{stem}_{counter}{suffix}"
                    target_path = archive_base / destination_name
                    counter += 1
            shutil.copy2(entry, target_path)

    def start_run(self, *, recipe_name: str, source_pdf: Optional[Path]) -> RunInfo:
        """Prepare directories and persist metadata for the incoming run."""
        self.archive_previous_run()
        self._clear_directory(self._pipeline_dir)
        self._clear_directory(self._cache_dir)
        if self._log_dir is not None:
            self._clear_directory(self._log_dir)

        run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        analysis_log = self._pipeline_dir / f"{run_id}_analysis.log"
        transfer_log = self._pipeline_dir / f"{run_id}_transfer.log"
        info = RunInfo(
            run_id=run_id,
            recipe_name=recipe_name,
            started_at=_now_utc(),
            source_pdf=str(source_pdf) if source_pdf else None,
            log_file=str(analysis_log),
            analysis_log_file=str(analysis_log),
            transfer_log_file=str(transfer_log),
        )
        self.save_run_info(info)

        return info

    def _clear_directory(self, path: Path) -> None:
        if not path.exists():
            return
        for entry in list(path.iterdir()):
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
