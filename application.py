import atexit
import concurrent.futures
import csv
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import cast

import paramiko
from apscheduler.schedulers.background import BackgroundScheduler
from decouple import config
from flask import Flask, jsonify
from flask_caching import Cache
from flask_cors import CORS

from ssh_manager import SSHConnectionManager

app = Flask(__name__, instance_relative_config=True)
ssh_manager = SSHConnectionManager()
logger = getLogger(__name__)


def cleanup_ssh_connections():
    logger.info("Cleaning up SSH connections")
    ssh_manager.cleanup()


scheduler = BackgroundScheduler()
scheduler.add_job(func=cleanup_ssh_connections, trigger="interval", seconds=30)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())


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
    ssh_manager: SSHConnectionManager,
) -> tuple[str, str, bool]:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(policy=paramiko.AutoAddPolicy())
    try:
        ssh_manager.connect(hostname, username, password)

        script_path = Path(__file__).resolve().parent / "scripts" / "gpu_status.sh"
        output = ssh_manager.execute_script(hostname=hostname, script_path=script_path)
    except Exception as e:
        return hostname, str(e), False

    return hostname, output, True


@dataclass
class GPUStatus:
    hostname: str
    status: list[dict[str, str]]
    success: bool


def fetch_gpu_statuses(
    hostnames,
    username,
    password,
    ssh_manager: SSHConnectionManager,
):
    futures: dict[str, concurrent.futures.Future[tuple[str, str, bool]]] = {}
    with ThreadPoolExecutor() as executor:
        for hostname in hostnames:
            futures[hostname] = executor.submit(
                fetch_gpu_status,
                hostname,
                username,
                password,
                ssh_manager,
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
@cache.cached(timeout=3)
def gpu_status():
    hostnames = cast(str, config("HOSTNAMES")).split(sep=",")
    username = cast(str, config("GPUSER_NAME"))
    password = cast(str, config("GPUSER_PASSWORD"))

    results = fetch_gpu_statuses(hostnames, username, password, ssh_manager)

    # Sort by hostname
    data: list[GPUStatus] = [results[hostname] for hostname in hostnames]

    return jsonify(data)
