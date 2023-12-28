from decouple import config
from django.shortcuts import render

from .ssh_gpu import get_gpu_status


def gpu_status(request):
    server_ip = config("SERVER_IP")
    username = config("GPUSER_NAME")
    password = config("GPUSER_PASSWORD")
    usage = get_gpu_status(server_ip, username, password)
    return render(request, "gpuser/index.html", {"usage": usage})
