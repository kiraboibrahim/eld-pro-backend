import openrouteservice
from django.conf import settings

def get_autocomplete_suggestions(query: str):
    """
    Fetch autocomplete suggestions using OpenRouteService SDK.
    """
    client = openrouteservice.Client(key=settings.ORS_API_KEY)

    # Call the SDK's geocoding autocomplete method
    response = client.pelias_autocomplete(text=query)

    return response
