import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import main
from main import app


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    """将 config.json 重定向到临时文件，避免污染真实配置。"""
    tmp_config = tmp_path / "config.json"
    monkeypatch.setattr(main, "CONFIG_FILE", tmp_config)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def upload_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def test_get_config(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    assert "upload_dir" in res.json()


def test_set_config(client, upload_dir):
    res = client.post("/api/config", json={"upload_dir": str(upload_dir)})
    assert res.status_code == 200
    assert res.json()["ok"] is True

    res = client.get("/api/config")
    assert Path(res.json()["upload_dir"]).resolve() == upload_dir.resolve()


def test_upload_and_download(client, upload_dir):
    client.post("/api/config", json={"upload_dir": str(upload_dir)})

    res = client.post(
        "/api/upload",
        files=[("files", ("test.txt", b"hello world"))],
        data={"paths": '["test.txt"]'},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["uploaded"]) == 1
    assert data["uploaded"][0]["name"] == "test.txt"

    res = client.get("/api/download/test.txt")
    assert res.status_code == 200
    assert res.content == b"hello world"


def test_upload_subdir(client, upload_dir):
    client.post("/api/config", json={"upload_dir": str(upload_dir)})

    res = client.post(
        "/api/upload",
        files=[("files", ("hello.txt", b"subdir file"))],
        data={"paths": '["subdir/hello.txt"]'},
    )
    assert res.status_code == 200
    assert len(res.json()["uploaded"]) == 1
    assert (upload_dir / "subdir" / "hello.txt").read_text() == "subdir file"


def test_download_path_traversal(client, upload_dir):
    client.post("/api/config", json={"upload_dir": str(upload_dir)})

    # URL-encoded ../ to bypass HTTP-layer normalization
    traversal = "%2e%2e/" * 10 + "etc/passwd"
    res = client.get(f"/api/download/{traversal}")
    assert res.status_code == 403


def test_upload_path_traversal(client, upload_dir):
    client.post("/api/config", json={"upload_dir": str(upload_dir)})

    traversal = "../../" * 20 + "etc/evil.txt"
    res = client.post(
        "/api/upload",
        files=[("files", ("evil.txt", b"should not write"))],
        data={"paths": f'["{traversal}"]'},
    )
    assert res.status_code == 200
    assert len(res.json()["failed"]) == 1
    assert not Path("/etc/evil.txt").exists()


def test_upload_over_size_limit(client, upload_dir):
    client.post("/api/config", json={"upload_dir": str(upload_dir)})

    import main

    old_limit = main.MAX_UPLOAD_SIZE
    main.MAX_UPLOAD_SIZE = 10

    try:
        res = client.post(
            "/api/upload",
            files=[("files", ("big.txt", b"x" * 100))],
            data={"paths": '["big.txt"]'},
        )
        assert res.status_code == 200
        assert len(res.json()["failed"]) == 1
        assert "超过文件大小限制" in res.json()["failed"][0]["error"]
    finally:
        main.MAX_UPLOAD_SIZE = old_limit


def test_list_files(client, upload_dir):
    client.post("/api/config", json={"upload_dir": str(upload_dir)})
    (upload_dir / "a.txt").write_text("a")
    (upload_dir / "b.txt").write_text("b")

    res = client.get("/api/files")
    assert res.status_code == 200
    names = [f["name"] for f in res.json()["files"]]
    assert "a.txt" in names
    assert "b.txt" in names


def test_browse_restricted(client):
    res = client.get("/api/browse", params={"path": "/etc"})
    assert res.status_code == 403
