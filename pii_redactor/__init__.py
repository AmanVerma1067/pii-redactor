"""pii_redactor: consistent, format-preserving PII pseudonymization for .docx files."""
from .entities import EntityType, Span
from .pipeline import Redactor, RedactionConfig, RedactionResult

__all__ = ["EntityType", "Span", "Redactor", "RedactionConfig", "RedactionResult"]
__version__ = "1.0.0"
