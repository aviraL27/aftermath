from pathlib import Path
import tempfile
import shutil
import os
import difflib
from typing import Dict, List, Optional, Tuple

class SecurityViolationError(Exception):
    """Raised when an agent tries to access paths outside the sandbox."""
    pass

class Sandbox:
    """
    Controlled execution environment with isolated filesystem.
    Prevents directory traversal and captures file changes.
    """
    def __init__(self, fixture_path: Optional[str | Path] = None, base_dir: Optional[str | Path] = None):
        if base_dir:
            self._temp_dir = None
            self.root = Path(base_dir).resolve()
            self.root.mkdir(parents=True, exist_ok=True)
        else:
            self._temp_dir = tempfile.TemporaryDirectory(prefix="aftermath_sandbox_")
            self.root = Path(self._temp_dir.name).resolve()
            
        self.initial_snapshot: Dict[str, str] = {}
        
        if fixture_path:
            self._seed_fixture(Path(fixture_path).resolve())
            
        self.initial_snapshot = self.take_snapshot()

    def _seed_fixture(self, fixture: Path):
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

    def _resolve_safe(self, rel_path: str) -> Path:
        """Resolve path and verify it stays strictly inside the sandbox root."""
        clean = Path(rel_path)
        # Avoid absolute paths bypassing root
        if clean.is_absolute():
            # If user provides /config.json, treat it as relative to root
            try:
                rel = clean.relative_to(clean.anchor)
            except Exception:
                rel = clean.name
            clean = rel
            
        target = (self.root / clean).resolve()
        
        # Security check: must be inside self.root
        if not target.is_relative_to(self.root):
            raise SecurityViolationError(f"Access denied: path '{rel_path}' attempts to escape sandbox {self.root}")
            
        return target

    def read_file(self, path: str) -> str:
        """Read content of a file within the sandbox."""
        p = self._resolve_safe(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return p.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        """Write content to a file, creating parent directories if needed."""
        p = self._resolve_safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {path}"

    def edit_file(self, path: str, find: str, replace: str) -> str:
        """Find and replace substring in a file."""
        content = self.read_file(path)
        if find not in content:
            raise ValueError(f"Substring to replace not found in {path}")
        new_content = content.replace(find, replace, 1)
        self.write_file(path, new_content)
        return f"Successfully replaced occurrences in {path}"

    def list_files(self, directory: str = ".") -> List[str]:
        """List relative paths of all files in directory."""
        dir_path = self._resolve_safe(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return []
        
        results: List[str] = []
        for item in dir_path.rglob("*"):
            if item.is_file():
                results.append(str(item.relative_to(self.root)).replace("\\", "/"))
        return sorted(results)

    def file_exists(self, path: str) -> bool:
        try:
            p = self._resolve_safe(path)
            return p.exists() and p.is_file()
        except SecurityViolationError:
            return False

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
        if self._temp_dir:
            try:
                self._temp_dir.cleanup()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

