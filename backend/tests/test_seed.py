import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def run_seed() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = os.environ["DATABASE_URL"]
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "scripts.seed_demo_user"],
        cwd=BACKEND_DIR,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_seed_demo_user_creates_loginable_account(client):
    result = run_seed()
    assert result.returncode == 0, result.stderr
    assert "已创建演示账号" in result.stdout
    response = client.post(
        "/api/auth/login", json={"username": "demo", "password": "demo123"}
    )
    assert response.status_code == 200
    user = response.json()["user"]
    assert user["nickname"] == "小鹿"
    assert user["role"] == "user"
    assert user["height_cm"] == 172
    assert user["weight_kg"] == 75
    assert user["usual_size"] == "M"


def test_seed_demo_user_is_idempotent(clean_users):
    first = run_seed()
    assert first.returncode == 0, first.stderr
    second = run_seed()
    assert second.returncode == 0, second.stderr
    assert "已存在" in second.stdout


def test_seed_demo_user_repairs_wrong_password(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "demo", "password": "other-password"},
    )
    assert response.status_code == 201

    result = run_seed()
    assert result.returncode == 0, result.stderr
    assert "已重置密码与资料" in result.stdout

    login = client.post(
        "/api/auth/login", json={"username": "demo", "password": "demo123"}
    )
    assert login.status_code == 200
    assert login.json()["user"]["nickname"] == "小鹿"
