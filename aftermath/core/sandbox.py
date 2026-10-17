from pathlib import Path
import tempfile
import shutil
import os
import difflib
import subprocess
from typing import Dict, List, Optional, Tuple, Any
from aftermath.config import settings

class SecurityViolationError(Exception):
    """Raised when an agent tries to access paths outside the sandbox."""
    pass

class Sandbox:
    """
    Controlled execution environment with isolated filesystem.
    Supports either a local temporary directory or a remote E2B cloud micro-VM.
    Prevents directory traversal, captures file changes, and executes safe commands.
    """
    def __init__(
        self,
        fixture_path: Optional[str | Path] = None,
        base_dir: Optional[str | Path] = None,
        backend: str = "local",
        e2b_api_key: Optional[str] = None,
        e2b_template: Optional[str] = None
    ):
        self.backend = backend.lower()
        self.fixture_path = Path(fixture_path).resolve() if fixture_path else None
        self._temp_dir = None
        self._e2b_vm = None
        self.root = None
        self.e2b_workspace = "/home/user/workspace"
        self.initial_snapshot: Dict[str, str] = {}

        if self.backend == "e2b":
            self._init_e2b(e2b_api_key=e2b_api_key, e2b_template=e2b_template)
        else:
            self._init_local(base_dir=base_dir)

        self.initial_snapshot = self.take_snapshot()

    def _init_local(self, base_dir: Optional[str | Path] = None):
        if base_dir:
            self.root = Path(base_dir).resolve()
            self.root.mkdir(parents=True, exist_ok=True)
        else:
            self._temp_dir = tempfile.TemporaryDirectory(prefix="aftermath_sandbox_")
            self.root = Path(self._temp_dir.name).resolve()

        if self.fixture_path:
            self._seed_local_fixture(self.fixture_path)

    def _seed_local_fixture(self, fixture: Path):
        if not fixture.exists():
            return
        if fixture.is_dir():
            for item in fixture.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(fixture)
                    dest = self.root / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)
        elif fixture.is_file():
            dest = self.root / fixture.name
            shutil.copy2(fixture, dest)

    def _init_e2b(self, e2b_api_key: Optional[str] = None, e2b_template: Optional[str] = None):
        from e2b import Sandbox as E2BVM
        api_key = e2b_api_key or settings.get_e2b_key()
        if not api_key:
            raise ValueError("No E2B API key provided. Set E2B_API_KEY in environment or .env.")

        opts: Dict[str, Any] = {"api_key": api_key}
        if e2b_template:
            opts["template"] = e2b_template

        self._e2b_vm = E2BVM.create(**opts)
        self._e2b_vm.commands.run(f"mkdir -p {self.e2b_workspace}")
        # Ensure pytest is available in the micro-VM
        try:
            self._e2b_vm.commands.run("which pytest")
        except Exception:
            self._e2b_vm.commands.run("pip install pytest --quiet")

        if self.fixture_path:
            self._seed_e2b_fixture(self.fixture_path)

    def _seed_e2b_fixture(self, fixture: Path):
        if not fixture.exists():
            return
        if fixture.is_dir():
            for item in fixture.rglob("*"):
                if item.is_file():
                    rel = str(item.relative_to(fixture)).replace("\\", "/")
                    content = item.read_text(encoding="utf-8", errors="replace")
                    self.write_file(rel, content)
        elif fixture.is_file():
            content = fixture.read_text(encoding="utf-8", errors="replace")
            self.write_file(fixture.name, content)

    def _resolve_safe(self, rel_path: str) -> Path:
        """Resolve path and verify it stays strictly inside the local sandbox root."""
        clean = Path(rel_path)
        if clean.is_absolute():
            try:
                rel = clean.relative_to(clean.anchor)
            except Exception:
                rel = clean.name
            clean = rel

        target = (self.root / clean).resolve()
        if not target.is_relative_to(self.root):
            raise SecurityViolationError(f"Access denied: path '{rel_path}' attempts to escape sandbox {self.root}")

        return target

    def _normalize_path(self, path: str) -> str:
        return path.replace("\\", "/").lstrip("/")

    def read_file(self, path: str) -> str:
        """Read content of a file within the sandbox."""
        clean = self._normalize_path(path)
        if self.backend == "e2b":
            try:
                return self._e2b_vm.files.read(f"{self.e2b_workspace}/{clean}")
            except Exception as e:
                raise FileNotFoundError(f"File not found in E2B sandbox: {path} ({e})")

        p = self._resolve_safe(clean)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return p.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        """Write content to a file, creating parent directories if needed."""
        clean = self._normalize_path(path)
        if self.backend == "e2b":
            target = f"{self.e2b_workspace}/{clean}"
            parent = "/".join(target.split("/")[:-1])
            if parent:
                self._e2b_vm.commands.run(f"mkdir -p '{parent}'")
            self._e2b_vm.files.write(target, content)
            return f"Successfully wrote {len(content)} characters to {clean}"

        p = self._resolve_safe(clean)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {clean}"

    def edit_file(self, path: str, find: str, replace: str) -> str:
        """Find and replace substring in a file."""
        content = self.read_file(path)
        if find not in content:
            raise ValueError(f"Substring to replace not found in {path}")
        new_content = content.replace(find, replace, 1)
        self.write_file(path, new_content)
        return f"Successfully replaced occurrences in {path}"

    @staticmethod
    def _is_ignored(path_str: str) -> bool:
        parts = path_str.replace("\\", "/").split("/")
        if any(p in {"__pycache__", ".pytest_cache", ".git", ".DS_Store"} for p in parts):
            return True
        if path_str.endswith((".pyc", ".pyo", ".pyd")):
            return True
        return False

    def list_files(self, directory: str = ".") -> List[str]:
        """List relative paths of all files in directory."""
        if self.backend == "e2b":
            clean_dir = self._normalize_path(directory)
            target = f"{self.e2b_workspace}/{clean_dir}".rstrip("/")
            res = self._e2b_vm.commands.run(f"cd '{target}' && find . -type f")
            results: List[str] = []
            for line in res.stdout.strip().splitlines():
                f = line.strip().replace("./", "", 1)
                if f and not self._is_ignored(f):
                    results.append(f)
            return sorted(results)

        dir_path = self._resolve_safe(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return []

        results = []
        for item in dir_path.rglob("*"):
            if item.is_file():
                rel = str(item.relative_to(self.root)).replace("\\", "/")
                if not self._is_ignored(rel):
                    results.append(rel)
        return sorted(results)

    def file_exists(self, path: str) -> bool:
        clean = self._normalize_path(path)
        if self.backend == "e2b":
            target = f"{self.e2b_workspace}/{clean}"
            res = self._e2b_vm.commands.run(f"test -f '{target}'")
            return res.exit_code == 0

        try:
            p = self._resolve_safe(clean)
            return p.exists() and p.is_file()
        except SecurityViolationError:
            return False

    def run_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a terminal/shell command inside the sandbox workspace."""
        if self.backend == "e2b":
            try:
                res = self._e2b_vm.commands.run(f"cd {self.e2b_workspace} && {command}", timeout=timeout)
                return {
                    "exit_code": res.exit_code,
                    "stdout": res.stdout,
                    "stderr": res.stderr
                }
            except Exception as e:
                # E2B raises CommandExitException when exit_code != 0
                return {
                    "exit_code": getattr(e, "exit_code", 1),
                    "stdout": getattr(e, "stdout", ""),
                    "stderr": getattr(e, "stderr", str(e))
                }

        # Local Windows compatibility: map python3 to python if running on Windows
        local_cmd = command
        if os.name == "nt" and local_cmd.startswith("python3 "):
            local_cmd = "python " + local_cmd[8:]

        proc = subprocess.run(
            local_cmd,
            shell=True,
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr
        }

    def take_snapshot(self) -> Dict[str, str]:
        """Snapshot all text files currently in the sandbox."""
        snapshot: Dict[str, str] = {}
        for path_str in self.list_files("."):
            try:
                snapshot[path_str] = self.read_file(path_str)
            except Exception:
                pass
        return snapshot

    def compute_diff(self) -> str:
        """Compute unified git-like diff between initial and current state."""
        current = self.take_snapshot()
        all_paths = sorted(set(self.initial_snapshot.keys()) | set(current.keys()))
        diff_lines: List[str] = []

        for p in all_paths:
            old_lines = self.initial_snapshot.get(p, "").splitlines(keepends=True)
            new_lines = current.get(p, "").splitlines(keepends=True)
            if old_lines != new_lines:
                diff = difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{p}",
                    tofile=f"b/{p}",
                    lineterm=""
                )
                diff_lines.extend(diff)

        return "\n".join(diff_lines)

    def cleanup(self):
        if self.backend == "e2b" and self._e2b_vm:
            try:
                self._e2b_vm.kill()
            except Exception:
                pass
            self._e2b_vm = None

        if self._temp_dir:
            try:
                self._temp_dir.cleanup()
            except Exception:
                pass
            self._temp_dir = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

