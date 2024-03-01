import time
from logging import INFO, Formatter, getLogger
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import paramiko


class SSHConnectionNotEstablished(Exception):
    pass


class SSHConnectionManager:
    def __init__(self):
        self.connections: dict[str, tuple[paramiko.SSHClient, float]] = {}
        self.timeout = 30  # seconds
        self.logger = self.setup_logger()

    def setup_logger(self):
        """Set up the logger for the SSHManager class"""
        logger = getLogger("SSHManager")
        log_dir = Path(__file__).resolve().parent / "log"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "ssh_manager"
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
        )
        formatter = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.setLevel(INFO)
        return logger

    def _is_connection_expired(self, hostname: str) -> bool:
        """Check if the connection with the given hostname has expired"""
        _, create_at = self.connections[hostname]
        return time.time() - create_at > self.timeout

    def connect(self, hostname: str, username: str, password: str) -> None:
        """Establish a new connection with the given hostname"""
        if hostname in self.connections:
            if self._is_connection_expired(hostname):
                self.close(hostname)
            else:
                self.logger.info(f"Reusing existing connection with {hostname}")
                return

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=hostname,
            username=username,
            password=password,
            allow_agent=False,
            look_for_keys=False,
        )
        self.logger.info(f"New connection established with {hostname}")
        create_at = time.time()
        self.connections[hostname] = (ssh, create_at)

    def execute_script(self, hostname: str, script_path: Path) -> str:
        """Execute the given script on the remote host"""
        if hostname not in self.connections:
            raise SSHConnectionNotEstablished(f"No connection with {hostname}")

        ssh, _ = self.connections[hostname]

        if not script_path.exists():
            raise FileNotFoundError(f"Script not found at {script_path}")

        script = script_path.read_text()
        stdin, stdout, stderr = ssh.exec_command(script)
        self.logger.info(f"Script executed on {hostname}")
        error = stderr.read().decode()
        if error:
            raise Exception(f"Script error: {error}")
        return stdout.read().decode()

    def close(self, hostname: str) -> None:
        """Close the connection with the given hostname"""
        if hostname in self.connections:
            ssh, _ = self.connections[hostname]
            ssh.close()
            self.logger.info(f"Connection closed with {hostname}")
            del self.connections[hostname]

    def cleanup(self) -> None:
        """Close all connections that have expired"""
        self.logger.info("Running cleanup")
        current_time = time.time()
        expired_hosts = [
            hostname
            for hostname, (_, last_used_time) in self.connections.items()
            if current_time - last_used_time > self.timeout
        ]
        for hostname in expired_hosts:
            self.close(hostname)
            self.logger.info(f"Connection closed with {hostname}")

    def __del__(self):
        """Close all connections when the object is deleted"""
        # use list() to avoid RuntimeError: dictionary changed size during iteration
        for hostname in list(self.connections):
            self.close(hostname)
