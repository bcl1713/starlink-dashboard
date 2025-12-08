import pytest
import check_filename_convention
from check_filename_convention import is_compliant

class TestFilenameConvention:
    @pytest.mark.parametrize("filename,expected", [
        ("valid-file.md", True),
        ("also-valid-123.md", True),
        ("123-numbers.md", True),
        ("justname", True),  # Extension removal is handled before regex in checker
        ("Invalid-Caps.md", False),
        ("invalid_underscores.md", False),
        ("invalid spaces.md", False),
        ("InvalidExtension.TXT", False), # Extension check is separate, but function checks name part
    ])
    def test_is_compliant_filenames(self, filename, expected):
        """Test the regex-based compliance checker function."""
        assert is_compliant(filename) == expected

    def test_excluded_files_list(self):
        """Ensure critical documentation files are excluded."""
        defaults = {
            "README.md", "CONTRIBUTING.md", "LICENSE.md", 
            "AGENTS.md", "CLAUDE.md"
        }
        for filename in defaults:
            assert filename in check_filename_convention.EXCLUDED_FILES

    def test_main_functionality_no_docs(self, monkeypatch, capsys, tmp_path):
        """Test main function when docs dir is missing."""
        import sys
        import pytest
        
        # Mocking os.getcwd to return a temp dir that has no 'docs' folder
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))
        
        # We don't mock sys.exit to a MagicMock that suppresses exit. 
        # We want SystemExit to be raised so execution stops.
        # But to check the code, we wrap in pytest.raises.

        with pytest.raises(SystemExit) as excinfo:
            check_filename_convention.main()
        
        assert excinfo.value.code == 1
        
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_main_success(self, monkeypatch, capsys, tmp_path):
        """Test main flow with compliant files."""
        import sys
        from unittest.mock import MagicMock

        # Create a temporary structure
        d = tmp_path / "docs"
        d.mkdir()
        (d / "valid-file.md").touch()
        (d / "README.md").touch() # Excluded

        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))
        
        # Mocking sys.exit
        mock_exit = MagicMock()
        monkeypatch.setattr("sys.exit", mock_exit)
        
        check_filename_convention.main()
        
        captured = capsys.readouterr()
        assert "All markdown files follow the naming convention" in captured.out
        mock_exit.assert_called_with(0)

    def test_main_failure(self, monkeypatch, capsys, tmp_path):
        """Test main flow with non-compliant files."""
        import sys
        from unittest.mock import MagicMock

        d = tmp_path / "docs"
        d.mkdir()
        (d / "Bad_Name.md").touch()

        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))
        
        mock_exit = MagicMock()
        monkeypatch.setattr("sys.exit", mock_exit)
        
        check_filename_convention.main()
        
        captured = capsys.readouterr()
        assert "Found the following files violating" in captured.out
        assert "Bad_Name.md" in captured.out
        mock_exit.assert_called_with(1)

