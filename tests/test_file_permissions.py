"""Client data files and folders are readable by their owner only.

Evidence from a consultation sits on a shared laptop. Other accounts on the
machine must not be able to read it.
"""

import os
import stat

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config


@pytest.fixture
def restore_umask():
    old = os.umask(0o022)
    yield
    os.umask(old)


@pytest.fixture
def data_dirs(tmp_path, monkeypatch):
    dirs = {}
    for name in ("DUMP_DIR", "SCREENSHOT_DIR", "REPORT_DIR"):
        dirs[name] = tmp_path / name
        monkeypatch.setattr(config, name, dirs[name])
    monkeypatch.setattr(config, "REPORT_PATH", dirs["REPORT_DIR"])
    monkeypatch.setattr(config, "CONSULT_DATA_DIR", tmp_path / "consult")
    monkeypatch.setattr(config, "DB_DIR", tmp_path / "data")
    return tmp_path


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def test_new_files_are_owner_only(restore_umask, data_dirs):
    config.ensure_dirs()
    f = data_dirs / "new.txt"
    f.write_text("x")
    assert _mode(f) & 0o077 == 0


def test_client_data_folders_are_owner_only(restore_umask, data_dirs):
    config.ensure_dirs()
    for d in config.client_data_dirs():
        assert d.is_dir(), d
        assert _mode(d) == 0o700, d


def test_folders_that_already_exist_are_tightened(restore_umask, data_dirs):
    loose = data_dirs / "DUMP_DIR"
    loose.mkdir()
    os.chmod(loose, 0o755)
    config.ensure_dirs()
    assert _mode(loose) == 0o700


def test_an_existing_database_file_is_tightened(restore_umask, data_dirs):
    db = data_dirs / "data"
    db.mkdir()
    f = db / "fieldstudy.db"
    f.write_text("")
    os.chmod(f, 0o644)
    config.ensure_dirs()
    assert _mode(f) == 0o600


def test_folders_recreated_by_delete_stay_owner_only(restore_umask, data_dirs, monkeypatch):
    import evidence_collection as ec

    config.ensure_dirs()
    for name in ("DUMP_DIR", "SCREENSHOT_DIR", "REPORT_DIR"):
        monkeypatch.setattr(ec, name, getattr(config, name))
    monkeypatch.setattr(ec, "TMP_CONSULT_DATA_DIR", str(config.CONSULT_DATA_DIR))
    monkeypatch.setattr(config, "SQL_DB_PATH", f"sqlite:///{data_dirs / 'none.db'}")
    ec.delete_client_data()
    for d in (config.DUMP_DIR, config.SCREENSHOT_DIR, config.REPORT_DIR):
        assert _mode(d) == 0o700, d
