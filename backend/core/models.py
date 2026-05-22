from django.db import models


class FlightLog(models.Model):
    icao24 = models.CharField(max_length=24, db_index=True)
    callsign = models.CharField(max_length=16, db_index=True)
    origin_country = models.CharField(max_length=100, blank=True, null=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_updated']
        unique_together = ('icao24', 'callsign')

    def __str__(self):
        return f"{self.callsign} ({self.icao24})"


class LandingArchive(models.Model):
    flight_log = models.ForeignKey(FlightLog, on_delete=models.CASCADE, related_name='landings')
    landing_time = models.DateTimeField(auto_now_add=True)
    max_velocity = models.FloatField(help_text="Maximum recorded speed in m/s")
    max_altitude = models.FloatField(help_text="Maximum recorded altitude in meters")
    squawk_at_landing = models.CharField(max_length=8, blank=True, null=True)

    class Meta:
        ordering = ['-landing_time']

    def __str__(self):
        return f"Landing: {self.flight_log.callsign} at {self.landing_time}"
