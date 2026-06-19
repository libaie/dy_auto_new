"""Device operations domain package.

This package owns the future `/api/device/*` and `/api/devices/*` migration
boundary. Route behavior still lives in the legacy routers until facade gates
are satisfied.
"""

DOMAIN_NAME = "device_operations"
PUBLIC_ROUTE_PREFIXES = ("/api/device", "/api/devices")

__all__ = ["DOMAIN_NAME", "PUBLIC_ROUTE_PREFIXES"]
