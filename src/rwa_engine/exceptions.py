"""Public exception hierarchy for the RWA library.

Copyright (C) 2026 RiskDataScience GmbH.
SPDX-License-Identifier: GPL-3.0-only
"""

from __future__ import annotations

from typing import Any, Iterable


class RwaError(Exception):
    """Base class for controlled library failures."""


class ConfigurationError(RwaError, ValueError):
    """Configuration or a packaged reference profile is invalid."""


class ResourceError(RwaError):
    """A packaged resource cannot be found, verified, or exported."""


class ValidationError(RwaError):
    """Canonical input data failed closed validation."""

    def __init__(self, message: str, issues: Iterable[Any] = ()) -> None:
        super().__init__(message)
        self.issues = tuple(issues)


class CalculationError(RwaError):
    """A calculation could not be completed."""
