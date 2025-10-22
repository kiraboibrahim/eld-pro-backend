from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .serializers import TripSimulationRequestSerializer
from .services.hos_simulator import HOSCompliantTripSimulator

@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def simulate_trip(request):
    """
    Simulate an FMCSA HOS-compliant truck trip
    """
    serializer = TripSimulationRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    simulator = HOSCompliantTripSimulator(settings.ORS_API_KEY)

    try:
        trip = simulator.simulate_trip(
            current_location=tuple(data['current_location']),
            pickup_location=tuple(data['pickup_location']),
            dropoff_location=tuple(data['dropoff_location']),
            current_cycle_hours=data['current_cycle_hours'],
            start_time=data.get('start_time')
        )
        return Response(trip)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
