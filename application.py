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
cors = (
    CORS(
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
    if app.config["DEBUG"]
    else None
)


def load_config(app: Flask) -> None:
    # load default config
    app.config.from_object("settings.DefaultConfig")
    # load instance config
    config_file = "development.py" if app.config["DEBUG"] else "production.py"
    app.config.from_pyfile(filename=os.path.join("config", config_file), silent=True)


def setup_cache(app: Flask) -> Cache:
    cache = Cache(
        config={
            "CACHE_TYPE": "SimpleCache",
            "DEBUG": app.config["DEBUG"],
            "CACHE_DEFAULT_TIMEOUT": 10,
        }
    )
    cache.init_app(app)
    return cache


load_config(app)
cache = setup_cache(app)


def fetch_gpu_status(
    hostname: str,
    username: str,
    password: str,
) -> tuple[str, str, bool]:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(policy=paramiko.AutoAddPolicy())
    try:
        ssh.connect(
            hostname=hostname,
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
        return hostname, str(e), False
    finally:
        ssh.close()

    return hostname, output, True


@dataclass
class GPUStatus:
    hostname: str
    status: list[dict[str, str]]
    success: bool


def fetch_gpu_statuses(hostnames, username, password):
    futures: dict[str, concurrent.futures.Future[tuple[str, str, bool]]] = {}
    with ThreadPoolExecutor() as executor:
        for hostname in hostnames:
            futures[hostname] = executor.submit(
                fetch_gpu_status, hostname, username, password
            )

    results: dict[str, GPUStatus] = {}
    for future in concurrent.futures.as_completed(futures.values()):
        hostname, status, success = future.result()
        reader = csv.DictReader(status.splitlines())
        results[hostname] = GPUStatus(
            hostname=hostname, status=list(reader) if success else [], success=success
        )

    return results


@app.route("/")
@cache.cached(timeout=10)
def gpu_status():
    hostnames = cast(str, config("HOSTNAMES")).split(sep=",")
    username = cast(str, config("GPUSER_NAME"))
    password = cast(str, config("GPUSER_PASSWORD"))

    results = fetch_gpu_statuses(hostnames, username, password)

    # Sort by hostname
    data: list[GPUStatus] = [results[hostname] for hostname in hostnames]

    return jsonify(data)
