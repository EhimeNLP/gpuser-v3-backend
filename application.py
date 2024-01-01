import concurrent.futures
import csv
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import paramiko
from decouple import config
from flask import Flask, jsonify
from flask_caching import Cache

app = Flask(__name__, instance_relative_config=True)

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
if app.config["ENV"] == "development":
    app.config.from_pyfile(os.path.join("config", "development.py"))
else:
    app.config.from_pyfile(os.path.join("config", "production.py"), silent=True)


def get_gpu_status(server_ip, username, password) -> tuple[str, str, bool]:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(
            server_ip,
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


@app.route("/")
@cache.cached(timeout=10)
def gpu_status():
    server_ips = config("SERVER_IPS").split(",")
    username = config("GPUSER_NAME")
    password = config("GPUSER_PASSWORD")

    data = []
    futures = {}
    with ThreadPoolExecutor() as executor:
        for server_ip in server_ips:
            futures[server_ip] = executor.submit(
                get_gpu_status, server_ip, username, password
            )

    results = {}
    for future in concurrent.futures.as_completed(futures.values()):
        server_ip, status, success = future.result()

        # Convert CSV to dictionary
        reader = csv.DictReader(status.splitlines())
        results[server_ip] = {
            "server_ip": server_ip,
            "status": list(reader),
            "success": success,
        }

    # Sort by server_ip
    for server_ip in server_ips:
        data.append(results[server_ip])

    return jsonify(data)
