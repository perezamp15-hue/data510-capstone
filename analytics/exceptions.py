"""Custom exceptions for the MLB analytics application."""
class AnalyticsError(Exception):
    """Base exception for analytics-related failures."""

class ConfigurationError(AnalyticsError):
    """Raised when required application configuration is missing or invalid."""

class DatabaseConnectionError(AnalyticsError):
    """Raised when a connection to PostgreSQL cannot be established."""

class DataNotFoundError(AnalyticsError):
    """Raised when a requested player, game, park, or team cannot be found."""

class ValidationError(AnalyticsError):
    """Raised when a function receives invalid input."""