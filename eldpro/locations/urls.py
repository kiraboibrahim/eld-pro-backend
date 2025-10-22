from django.urls import path
from .views import autocomplete

urlpatterns = [
    path('autocomplete/', autocomplete, name='autocomplete'),
]
