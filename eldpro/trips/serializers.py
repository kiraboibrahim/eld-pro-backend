from rest_framework import serializers

class TripSimulationRequestSerializer(serializers.Serializer):
    current_location = serializers.ListField(
        child=serializers.FloatField(), min_length=2, max_length=2,
        help_text="Longitude, Latitude of current location"
    )
    pickup_location = serializers.ListField(
        child=serializers.FloatField(), min_length=2, max_length=2,
        help_text="Longitude, Latitude of pickup location"
    )
    dropoff_location = serializers.ListField(
        child=serializers.FloatField(), min_length=2, max_length=2,
        help_text="Longitude, Latitude of dropoff location"
    )
    current_cycle_hours = serializers.FloatField()
