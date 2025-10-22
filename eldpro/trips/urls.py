from django.urls import path
from .views import simulate_trip

urlpatterns = [
    path('simulate/', simulate_trip, name='simulate_trip'),
]
