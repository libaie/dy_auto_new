"""Adapter handles for external account-operations dependencies."""

from app.services.chain_service import chain_service
from app.services.channel_service import channel_service

__all__ = ["chain_service", "channel_service"]
