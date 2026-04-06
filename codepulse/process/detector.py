"""ProjectDetector — scan project root for runnable commands."""
from __future__ import annotations

import json
import re
from pathlib import Path

from codepulse.process.models import ProcessRecord


# Scripts from package.json that are worth exposing
PACKAGE_JSON_TARGETS = {"dev", "start", "test", "build", "watch", "serve", "preview", "lint"}

# Makefile targets to include (beyond purely phony utility targets)
MAKEFILE_SKIP = {"all", "clean", "install", "uninstall", "help", ".PHONY"}


class ProjectDetector:
    def __init__(self, project_root: Path) -> None:
        self._root = project_root

    def detect(self) -> list[ProcessRecord]:
        records: list[ProcessRecord] = []
        seen: set[str] = set()

        def add(r: ProcessRecord) -> None:
            if r.name not in seen:
                seen.add(r.name)
                records.append(r)

        for r in self._from_package_json():
            add(r)
        for r in self._from_procfile():
            add(r)
        for r in self._from_makefile():
            add(r)
        for r in self._from_python():
            add(r)
        for r in self._from_flutter():
            add(r)

        return records

    # ── package.json ─────────────────────────────────────────────────────────

    def _from_package_json(self) -> list[ProcessRecord]:
        pj = self._root / "package.json"
        if not pj.exists():
            return []
        try:
            data = json.loads(pj.read_text())
            scripts = data.get("scripts", {})
            result = []
            for key, cmd in scripts.items():
                if key.lower() in PACKAGE_JSON_TARGETS:
                    result.append(ProcessRecord(
                        name=key,
                        command=f"npm run {key}",
                    ))
            return result
        except Exception:
            return []

    # ── Procfile ─────────────────────────────────────────────────────────────

    def _from_procfile(self) -> list[ProcessRecord]:
        pf = self._root / "Procfile"
        if not pf.exists():
            return []
        result = []
        for line in pf.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([a-zA-Z0-9_-]+)\s*:\s*(.+)$", line)
            if match:
                name, cmd = match.group(1), match.group(2)
                result.append(ProcessRecord(name=name, command=cmd))
        return result

    # ── Makefile ─────────────────────────────────────────────────────────────

    def _from_makefile(self) -> list[ProcessRecord]:
        mf = self._root / "Makefile"
        if not mf.exists():
            return []
        result = []
        seen_targets: set[str] = set()
        for line in mf.read_text().splitlines():
            match = re.match(r"^([a-zA-Z][a-zA-Z0-9_-]*)\s*:", line)
            if match:
                target = match.group(1)
                if target not in MAKEFILE_SKIP and target not in seen_targets:
                    seen_targets.add(target)
                    result.append(ProcessRecord(name=target, command=f"make {target}"))
        return result[:6]  # Limit to first 6 Makefile targets

    # ── Python projects ───────────────────────────────────────────────────────

    def _from_python(self) -> list[ProcessRecord]:
        result = []
        # pytest
        if (self._root / "pytest.ini").exists() or (self._root / "pyproject.toml").exists():
            result.append(ProcessRecord(name="test", command="python -m pytest -v"))
        # Flask / FastAPI / Django
        if (self._root / "manage.py").exists():
            result.append(ProcessRecord(name="django-dev", command="python manage.py runserver"))
        if (self._root / "app.py").exists() or (self._root / "main.py").exists():
            result.append(ProcessRecord(name="run", command="python main.py"))
        return result

    # ── Flutter ───────────────────────────────────────────────────────────────

    def _from_flutter(self) -> list[ProcessRecord]:
        if not (self._root / "pubspec.yaml").exists():
            return []
        return [
            ProcessRecord(name="flutter-run", command="flutter run"),
            ProcessRecord(name="flutter-test", command="flutter test"),
            ProcessRecord(name="flutter-build", command="flutter build apk --debug"),
        ]
