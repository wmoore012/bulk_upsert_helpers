# SPDX - License - Identifier: MIT
# Copyright (c) 2025 Perday CatalogLAB™

"""
Custom exceptions for bulk - upsert - helpers module.

This module provides comprehensive error handling with specific exception types
for different failure scenarios, enabling precise error handling and debugging.
"""

from __future__ import annotations

from typing import Any


class BulkUpsertHelpersError(Exception):
    """Base exception for all bulk - upsert - helpers errors."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ) -> None:
        """
        Initialize the exception with detailed error information.

        Args:
            message: Human - readable error message
            details: Additional error context and debugging information
            suggestion: Suggested solution or next steps
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.suggestion = suggestion

    def __str__(self) -> str:
        """Return formatted error message with details and suggestions."""
        result = self.message

        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            result += f" (Details: {details_str})"

        if self.suggestion:
            result += f" Suggestion: {self.suggestion}"

        return result


class ValidationError(BulkUpsertHelpersError):
    """Raised when input validation fails."""

    def __init__(
        self, field: str, value: Any, expected: str, suggestion: str | None = None
    ) -> None:
        """
        Initialize validation error with field - specific information.

        Args:
            field: Name of the field that failed validation
            value: The invalid value that was provided
            expected: Description of what was expected
            suggestion: How to fix the validation error
        """
        message = f"Invalid {field}: got {type(value).__name__} '{value}', expected {expected}"
        details = {"field": field, "value": value, "expected": expected}
        super().__init__(message, details, suggestion)
        self.field = field
        self.value = value
        self.expected = expected


class ConfigurationError(BulkUpsertHelpersError):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self, config_key: str, issue: str, suggestion: str | None = None
    ) -> None:
        """
        Initialize configuration error.

        Args:
            config_key: The configuration key that has an issue
            issue: Description of the configuration problem
            suggestion: How to fix the configuration
        """
        message = f"Configuration error for '{config_key}': {issue}"
        details = {"config_key": config_key, "issue": issue}
        super().__init__(message, details, suggestion)
        self.config_key = config_key
        self.issue = issue


class ResourceError(BulkUpsertHelpersError):
    """Raised when system resources are unavailable or exhausted."""

    def __init__(
        self,
        resource: str,
        issue: str,
        current_usage: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        """
        Initialize resource error.

        Args:
            resource: The resource that is unavailable (memory, disk, network, etc.)
            issue: Description of the resource problem
            current_usage: Current resource usage information
            suggestion: How to resolve the resource issue
        """
        message = f"Resource error ({resource}): {issue}"
        details = {"resource": resource, "issue": issue}
        if current_usage:
            details["current_usage"] = current_usage
        super().__init__(message, details, suggestion)
        self.resource = resource
        self.issue = issue
        self.current_usage = current_usage


class OperationError(BulkUpsertHelpersError):
    """Raised when an operation fails due to business logic or external factors."""

    def __init__(
        self,
        operation: str,
        reason: str,
        retry_possible: bool = False,
        suggestion: str | None = None,
    ) -> None:
        """
        Initialize operation error.

        Args:
            operation: The operation that failed
            reason: Why the operation failed
            retry_possible: Whether retrying the operation might succeed
            suggestion: How to resolve the operation failure
        """
        message = f"Operation '{operation}' failed: {reason}"
        details = {
            "operation": operation,
            "reason": reason,
            "retry_possible": retry_possible,
        }
        super().__init__(message, details, suggestion)
        self.operation = operation
        self.reason = reason
        self.retry_possible = retry_possible
