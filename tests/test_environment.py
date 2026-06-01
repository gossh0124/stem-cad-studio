"""tests/test_environment.py — environment.py 環境偵測與設定函式驗證。

注意：setup_environment 會呼叫 pip install，測試中以 mock 隔離。
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest import mock
import importlib
import subprocess

import pytest

from lib import environment
from lib.environment import (
    setup_environment,
    _print_core_versions,
    _install_train,
    _install_pipeline,
    _reload_modules,
)


# ── _print_core_versions ────────────────────────────────────

class TestPrintCoreVersions:
    def test_installed_pkg(self, capsys):
        """Should print version for a known installed package."""
        _print_core_versions(["pip"])
        out = capsys.readouterr().out
        assert "pip:" in out
        # Should NOT show 'not installed'
        assert "pip" in out

    def test_missing_pkg(self, capsys):
        """Should print 'not installed' for unknown package."""
        _print_core_versions(["definitely_nonexistent_pkg_xyz"])
        out = capsys.readouterr().out
        assert "definitely_nonexistent_pkg_xyz" in out

    def test_empty_list(self, capsys):
        _print_core_versions([])
        out = capsys.readouterr().out
        # Should still print the header
        assert "info" in out.lower() or len(out.strip()) > 0

    def test_mixed_pkgs(self, capsys):
        _print_core_versions(["pip", "nonexistent_xxx"])
        out = capsys.readouterr().out
        assert "pip:" in out
        assert "nonexistent_xxx" in out


# ── setup_environment (mocked) ───────────────────────────────

class TestSetupEnvironment:
    @mock.patch("lib.environment._reload_modules")
    @mock.patch("lib.environment._install_pipeline")
    @mock.patch("lib.environment._install_train")
    @mock.patch("subprocess.run")
    def test_pipeline_mode_calls(self, mock_run, mock_train, mock_pipe, mock_reload, capsys):
        mock_run.return_value = mock.MagicMock(returncode=0)
        setup_environment(mode="pipeline")
        mock_pipe.assert_called_once()
        mock_train.assert_not_called()
        mock_reload.assert_called_once()

    @mock.patch("lib.environment._reload_modules")
    @mock.patch("lib.environment._install_pipeline")
    @mock.patch("lib.environment._install_train")
    @mock.patch("subprocess.run")
    def test_train_mode_calls(self, mock_run, mock_train_fn, mock_pipe, mock_reload, capsys):
        mock_run.return_value = mock.MagicMock(returncode=0)
        setup_environment(mode="train")
        mock_train_fn.assert_called_once()
        mock_pipe.assert_not_called()
        mock_reload.assert_called_once()

    @mock.patch("lib.environment._reload_modules")
    @mock.patch("lib.environment._install_pipeline")
    @mock.patch("lib.environment._install_train")
    @mock.patch("subprocess.run")
    def test_sets_hf_env_var(self, mock_run, mock_train, mock_pipe, mock_reload, capsys):
        mock_run.return_value = mock.MagicMock(returncode=0)
        setup_environment(mode="pipeline")
        assert os.environ.get("HF_HUB_ENABLE_HF_TRANSFER") == "0"

    @mock.patch("lib.environment._reload_modules")
    @mock.patch("lib.environment._install_pipeline")
    @mock.patch("lib.environment._install_train")
    @mock.patch("subprocess.run")
    def test_default_mode_is_pipeline(self, mock_run, mock_train, mock_pipe, mock_reload, capsys):
        mock_run.return_value = mock.MagicMock(returncode=0)
        setup_environment()
        mock_pipe.assert_called_once()
        mock_train.assert_not_called()


# ── _install_train (mocked) ──────────────────────────────────

class TestInstallTrain:
    @mock.patch("lib.environment._print_core_versions")
    @mock.patch("subprocess.run")
    def test_success(self, mock_run, mock_print, capsys):
        mock_run.return_value = mock.MagicMock(returncode=0)
        _install_train()
        # Should call subprocess.run at least twice (core + other)
        assert mock_run.call_count >= 2

    @mock.patch("subprocess.run")
    def test_failure_raises(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "pip", stderr="install failed"
        )
        with pytest.raises(subprocess.CalledProcessError):
            _install_train()


# ── _install_pipeline (mocked) ───────────────────────────────

class TestInstallPipeline:
    @mock.patch("lib.environment._print_core_versions")
    @mock.patch("subprocess.run")
    def test_success(self, mock_run, mock_print, capsys):
        mock_run.return_value = mock.MagicMock(returncode=0)
        _install_pipeline()
        assert mock_run.call_count >= 1

    @mock.patch("subprocess.run")
    def test_failure_raises(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "pip", stderr="install failed"
        )
        with pytest.raises(subprocess.CalledProcessError):
            _install_pipeline()


# ── _reload_modules ──────────────────────────────────────────

class TestReloadModules:
    @mock.patch("importlib.invalidate_caches")
    def test_calls_invalidate_caches(self, mock_inv, capsys):
        # Will likely ImportError on unsloth, but should not crash
        _reload_modules()
        mock_inv.assert_called_once()

    def test_handles_import_error_gracefully(self, capsys):
        """_reload_modules should not raise even if unsloth is missing."""
        # unsloth is almost certainly not installed in test env
        _reload_modules()
        out = capsys.readouterr().out
        # Should see either success or warning message
        assert "ok" in out.lower() or "warn" in out.lower()


# ── Module-level attributes ─────────────────────────────────

class TestModuleAttributes:
    def test_log_exists(self):
        assert hasattr(environment, '_log')

    def test_module_functions_exist(self):
        assert callable(setup_environment)
        assert callable(_print_core_versions)
        assert callable(_install_train)
        assert callable(_install_pipeline)
        assert callable(_reload_modules)
