import concurrent.futures
import csv
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import paramiko
from decouple import config
from flask import Flask, jsonify
from flask_caching import Cache
from flask_cors import CORS

app = Flask(__name__, instance_relative_config=True)
if app.config["DEBUG"]:
    cors = CORS(
        app,
        resources={
            r"/*": {
                "origins": [
                    "http://localhost:*",
                    "https://127.0.0.1:*",
                ],
            },
        },
    )

# 標準設定ファイル読み込み
app.config.from_object("settings.DefaultConfig")

# キャッシュ設定
cache = Cache(
    config={
        "CACHE_TYPE": "SimpleCache",
        "DEBUG": True,
        "CACHE_DEFAULT_TIMEOUT": 10,
    }
)
cache.init_app(app)

# 非公開設定ファイル読み込み
if app.config["DEBUG"]:
    app.config.from_pyfile(
        filename=os.path.join("config", "development.py"),
        silent=True,
    )
else:
    app.config.from_pyfile(
        filename=os.path.join("config", "production.py"),
        silent=True,
    )


def get_gpu_status(
    server_ip: str,
    username: str,
    password: str,
) -> tuple[str, str, bool]:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(policy=paramiko.AutoAddPolicy())
    try:
        ssh.connect(
            hostname=server_ip,
            username=username,
            password=password,
            allow_agent=False,
            look_for_keys=False,
        )

        script_path = Path(__file__).resolve().parent / "scripts" / "gpu_status.sh"
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found at {script_path}")

        script = script_path.read_text()
        stdin, stdout, stderr = ssh.exec_command(script)
        error = stderr.read().decode()
        if error:
            raise Exception(f"Script error: {error}")
        output = stdout.read().decode()

    except Exception as e:
        return server_ip, str(e), False
    finally:
        ssh.close()

    return server_ip, output, True


@dataclass
class GPUStatus:
    server_ip: str
    status: list[dict[str, str]]
    success: bool


@app.route("/")
@cache.cached(timeout=10)
def gpu_status():
    server_ips = cast(str, config("SERVER_IPS")).split(sep=",")
    username = cast(str, config("GPUSER_NAME"))
    password = cast(str, config("GPUSER_PASSWORD"))

    data: list[GPUStatus] = []
    futures: dict[str, concurrent.futures.Future[tuple[str, str, bool]]] = {}
    with ThreadPoolExecutor() as executor:
        for server_ip in server_ips:
            futures[server_ip] = executor.submit(
                get_gpu_status,
                server_ip,
                username,
                password,
            )

    results: dict[str, GPUStatus] = {}
    for future in concurrent.futures.as_completed(futures.values()):
        server_ip, status, success = future.result()

        # Convert CSV to dictionary
        reader = csv.DictReader(status.splitlines())
        results[server_ip] = GPUStatus(
            server_ip=server_ip,
            status=list(reader) if success else [],
            success=success,
        )

    # Sort by server_ip
    for server_ip in server_ips:
        data.append(results[server_ip])

    return jsonify(data)
