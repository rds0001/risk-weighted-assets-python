"""Public interface of the institution-neutral RWA reference library."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("risk-weighted-assets")
except PackageNotFoundError:  # source-tree execution
    __version__ = "1.0.0"

from .api import calculate_dataset, calculate_tables, validate_dataset
from .exceptions import (
    CalculationError,
    ConfigurationError,
    ResourceError,
    RwaError,
    ValidationError,
)
from .models import CalculationResult, ValidationMessage, ValidationReport
from .workspace import (
    Workspace,
    create_workspace,
    default_workspace,
    list_reference_datasets,
    list_reference_profiles,
    regulatory_sources,
)

__all__ = [
    "CalculationError",
    "CalculationResult",
    "ConfigurationError",
    "ResourceError",
    "RwaError",
    "ValidationError",
    "ValidationMessage",
    "ValidationReport",
    "Workspace",
    "__version__",
    "calculate_dataset",
    "calculate_tables",
    "create_workspace",
    "default_workspace",
    "list_reference_datasets",
    "list_reference_profiles",
    "regulatory_sources",
    "validate_dataset",
]
