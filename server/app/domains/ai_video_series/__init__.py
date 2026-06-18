"""AI video series domain package.

This package will own the `/api/series/*` business flow once the migration
passes the compatibility gates documented in README.md.
"""

DOMAIN_NAME = "ai_video_series"
PUBLIC_ROUTE_PREFIX = "/api/series"

__all__ = ["DOMAIN_NAME", "PUBLIC_ROUTE_PREFIX"]
