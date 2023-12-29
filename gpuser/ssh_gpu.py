from pathlib import Path

import paramiko


def get_gpu_status(server_ip, username, password) -> str:
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

    except paramiko.AuthenticationException:
        return "Authentication failed, please verify your credentials"
    except paramiko.SSHException as sshException:
        return f"Unable to establish SSH connection: {sshException}"
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"An error occurred: {e}"
    finally:
        ssh.close()

    return output
