"""Tests for cfg_store.py — config persistence and credentials resolution."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

import cfg_store
from cfg_store import _load_cfg, _save_cfg, _get_service_account_path_from_env_or_cfg


# ---------------------------------------------------------------- _load_cfg --

class TestLoadCfg:
    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        fake_cfg = tmp_path / "no_such_file.json"
        with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
            result = _load_cfg()
        assert result == {}

    def test_returns_parsed_json(self, tmp_path):
        fake_cfg = tmp_path / "cfg.json"
        data = {"sheet_id": "abc", "worksheet": "Sheet1"}
        fake_cfg.write_text(json.dumps(data), encoding="utf-8")
        with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
            result = _load_cfg()
        assert result == data

    def test_returns_empty_dict_on_corrupt_json(self, tmp_path):
        fake_cfg = tmp_path / "bad.json"
        fake_cfg.write_text("{not valid json", encoding="utf-8")
        with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
            result = _load_cfg()
        assert result == {}

    def test_returns_empty_dict_on_empty_file(self, tmp_path):
        fake_cfg = tmp_path / "empty.json"
        fake_cfg.write_text("", encoding="utf-8")
        with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
            result = _load_cfg()
        assert result == {}


# ---------------------------------------------------------------- _save_cfg --

class TestSaveCfg:
    def test_saves_and_reloads(self, tmp_path):
        fake_cfg = tmp_path / "cfg.json"
        data = {"sheet_id": "xyz", "worksheet": "MySheet"}
        with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
            _save_cfg(data)
            loaded = _load_cfg()
        assert loaded == data

    def test_overwrites_existing_file(self, tmp_path):
        fake_cfg = tmp_path / "cfg.json"
        with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
            _save_cfg({"sheet_id": "old"})
            _save_cfg({"sheet_id": "new"})
            loaded = _load_cfg()
        assert loaded["sheet_id"] == "new"

    def test_creates_parent_directories(self, tmp_path):
        deep_cfg = tmp_path / "a" / "b" / "cfg.json"
        assert not deep_cfg.parent.exists()
        with patch.object(cfg_store, "_CFG_FILE", deep_cfg):
            _save_cfg({"key": "value"})
        assert deep_cfg.exists()

    def test_persists_non_ascii_values(self, tmp_path):
        fake_cfg = tmp_path / "cfg.json"
        data = {"worksheet": "ورقة العمل"}
        with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
            _save_cfg(data)
            loaded = _load_cfg()
        assert loaded["worksheet"] == "ورقة العمل"

    def test_round_trip_all_keys(self, tmp_path):
        fake_cfg = tmp_path / "cfg.json"
        data = {
            "sheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
            "worksheet": "Tasks",
            "service_account_file": "/home/user/sa.json",
        }
        with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
            _save_cfg(data)
            loaded = _load_cfg()
        assert loaded == data


# ----------------------------------------- _get_service_account_path_from_env_or_cfg --

class TestGetServiceAccountPath:
    def test_returns_none_when_nothing_set(self, tmp_path):
        fake_cfg = tmp_path / "cfg.json"
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
                result = _get_service_account_path_from_env_or_cfg()
        assert result is None

    def test_returns_env_var_when_file_exists(self, tmp_path):
        sa_file = tmp_path / "sa.json"
        sa_file.write_text("{}", encoding="utf-8")
        fake_cfg = tmp_path / "cfg.json"
        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": str(sa_file)}):
            with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
                result = _get_service_account_path_from_env_or_cfg()
        assert result == str(sa_file)

    def test_ignores_env_var_when_file_missing(self, tmp_path):
        fake_cfg = tmp_path / "cfg.json"
        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/no/such/file.json"}):
            with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
                result = _get_service_account_path_from_env_or_cfg()
        assert result is None

    def test_falls_back_to_cfg_file_path(self, tmp_path):
        sa_file = tmp_path / "sa.json"
        sa_file.write_text("{}", encoding="utf-8")
        fake_cfg = tmp_path / "cfg.json"
        cfg_data = {"service_account_file": str(sa_file)}
        fake_cfg.write_text(json.dumps(cfg_data), encoding="utf-8")
        # No env var set
        env = {k: v for k, v in os.environ.items() if k != "GOOGLE_APPLICATION_CREDENTIALS"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
                result = _get_service_account_path_from_env_or_cfg()
        assert result == str(sa_file)

    def test_env_var_takes_priority_over_cfg(self, tmp_path):
        env_sa = tmp_path / "env_sa.json"
        env_sa.write_text("{}", encoding="utf-8")
        cfg_sa = tmp_path / "cfg_sa.json"
        cfg_sa.write_text("{}", encoding="utf-8")
        fake_cfg = tmp_path / "cfg.json"
        fake_cfg.write_text(json.dumps({"service_account_file": str(cfg_sa)}), encoding="utf-8")
        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": str(env_sa)}):
            with patch.object(cfg_store, "_CFG_FILE", fake_cfg):
                result = _get_service_account_path_from_env_or_cfg()
        assert result == str(env_sa)
