from django.urls import path

from .views import gpu_status

urlpatterns = [
    path("", gpu_status, name="gpu_status"),
]
