from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .services import get_autocomplete_suggestions

@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def autocomplete(request):
    
    query = request.query_params.get('query')
    if not query:
        return Response({"detail": "Missing 'query' parameter"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        data = get_autocomplete_suggestions(query)
        features = data.get("features", [])

        # Simplify response to frontend-friendly format
        results = [
            {
                "label": f["properties"].get("label"),
                "coordinates": f["geometry"].get("coordinates"),
                "name": f["properties"].get("name"),
                "country": f["properties"].get("country"),
                "region": f["properties"].get("region"),
                "locality": f["properties"].get("locality"),
            }
            for f in features
        ]

        return Response(results)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
