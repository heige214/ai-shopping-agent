import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def run_seed() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "scripts.seed_demo_user"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_seed_demo_user_creates_loginable_account(client):
    result = run_seed()
    assert "已创建演示账号" in result.stdout
    response = client.post(
        "/api/auth/login", json={"username": "demo", "password": "demo123"}
    )
    assert response.status_code == 200


def test_seed_demo_user_is_idempotent(client):
    run_seed()
    result = run_seed()
    assert "已存在" in result.stdout
