from __future__ import annotations
import uuid


class TelemetryPlatformError(Exception):
    """Base exception for all domain errors."""


class RateLimitExceededError(TelemetryPlatformError):
    def __init__(self, fleet_id: uuid.UUID) -> None:
        self.fleet_id = fleet_id
        super().__init__(f"Rate limit exceeded for fleet {fleet_id}")


class VehicleNotFoundError(TelemetryPlatformError):
    def __init__(self, vehicle_id: uuid.UUID) -> None:
        self.vehicle_id = vehicle_id
        super().__init__(f"Vehicle {vehicle_id} not found")


class FleetNotFoundError(TelemetryPlatformError):
    def __init__(self, fleet_id: uuid.UUID) -> None:
        self.fleet_id = fleet_id
        super().__init__(f"Fleet {fleet_id} not found")


class CacheUnavailableError(TelemetryPlatformError):
    """Raised when Redis is unreachable — callers should fall back to DB."""
