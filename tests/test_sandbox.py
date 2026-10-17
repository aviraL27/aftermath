import pytest
from pathlib import Path
from aftermath.core.sandbox import Sandbox, SecurityViolationError

def test_sandbox_file_operations(tmp_path):
    with Sandbox(base_dir=tmp_path) as sb:
        # Write
        sb.write_file("nested/config.json", '{"key": "value"}')
        assert sb.file_exists("nested/config.json")

        # Read
        content = sb.read_file("nested/config.json")
        assert '{"key": "value"}' in content

        # Edit
        sb.edit_file("nested/config.json", '"value"', '"updated"')
        assert '"updated"' in sb.read_file("nested/config.json")

        # List
        files = sb.list_files(".")
        assert "nested/config.json" in files

def test_sandbox_path_traversal_blocked(tmp_path):
    with Sandbox(base_dir=tmp_path) as sb:
        with pytest.raises(SecurityViolationError):
            sb.read_file("../../outside.txt")

        with pytest.raises(SecurityViolationError):
            sb.write_file("../forbidden.txt", "hack")

def test_sandbox_diff_calculation(tmp_path):
    with Sandbox(base_dir=tmp_path) as sb:
        sb.write_file("file.txt", "initial line\n")
        sb.initial_snapshot = sb.take_snapshot()

        sb.write_file("file.txt", "initial line\nadded line\n")
        diff = sb.compute_diff()
        assert "+added line" in diff

