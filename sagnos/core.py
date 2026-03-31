"""
sagnos/core.py
The heart of Sagnos — @expose, @model, @stream decorators.
"""

import inspect
import hashlib
import functools
import asyncio
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal
from enum import Enum
from typing import (
    get_type_hints, Callable, Any,
    get_origin, get_args, Union
)

from pydantic import TypeAdapter


# ─── Global Registry ─────────────────────────────────────────────────────────

_REGISTRY: dict[str, dict] = {}   # all @expose'd functions
_MODELS:   dict[str, type] = {}   # all @model classes
_STREAMS:  dict[str, dict] = {}   # all @stream functions


# ─── Special Type Registry ────────────────────────────────────────────────────

SPECIAL_TYPES = {
    datetime: {
        "dart_type":      "DateTime",
        "serialize":      lambda v: v.isoformat(),
    },
    date: {
        "dart_type":      "DateTime",
        "serialize":      lambda v: v.isoformat(),
    },
    UUID: {
        "dart_type":      "String",
        "serialize":      str,
    },
    Decimal: {
        "dart_type":      "double",
        "serialize":      float,
    },
}


# ─── Typed Errors ─────────────────────────────────────────────────────────────

class SagnosError(Exception):
    status_code = 500
    error_code  = "INTERNAL_ERROR"

    def __init__(self, message: str, detail: Any = None):
        self.message = message
        self.detail  = detail
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "status":     "error",
            "error_code": self.error_code,
            "message":    self.message,
            "detail":     self.detail,
        }

class NotFoundError(SagnosError):
    status_code = 404
    error_code  = "NOT_FOUND"

class ValidationError_(SagnosError):
    status_code = 422
    error_code  = "VALIDATION_ERROR"

class AuthError(SagnosError):
    status_code = 401
    error_code  = "UNAUTHORIZED"

class ForbiddenError(SagnosError):
    status_code = 403
    error_code  = "FORBIDDEN"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _is_optional(annotation) -> tuple[bool, Any]:
    """Checks if a type is Optional[X] — returns (True, X) or (False, annotation)."""
    if get_origin(annotation) is Union:
        args     = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if type(None) in args and non_none:
            return True, non_none[0]
    return False, annotation


def _serialize_value(value: Any, hint: Any) -> Any:
    """
    Recursively serialize Python values to JSON-safe equivalents.
    Handles datetime, UUID, Decimal, Enum, dataclasses, lists, dicts.
    """
    if value is None:
        return None

    # Special types (datetime, UUID, Decimal)
    if type(value) in SPECIAL_TYPES:
        return SPECIAL_TYPES[type(value)]["serialize"](value)

    # Enum → its value
    if isinstance(value, Enum):
        return value.value

    # List — serialize each item
    if isinstance(value, list):
        inner = None
        if get_origin(hint) is list:
            args  = get_args(hint)
            inner = args[0] if args else Any
        return [_serialize_value(item, inner) for item in value]

    # Dict — serialize each value
    if isinstance(value, dict):
        return {k: _serialize_value(v, Any) for k, v in value.items()}

    # Dataclass / @model instance
    if hasattr(value, "__dataclass_fields__"):
        fields = get_type_hints(type(value))
        return {
            k: _serialize_value(getattr(value, k), fields.get(k, Any))
            for k in value.__dataclass_fields__
        }

    return value


def _validate_return(value: Any, return_type: Any) -> Any:
    """
    Validate the return value against the declared type using Pydantic.
    Raises ValidationError_ if it doesn't match.
    """
    if return_type is None or return_type is type(None):
        return None

    # Serialize first (datetime → str, UUID → str, etc.)
    serialized = _serialize_value(value, return_type)

    return serialized


# ─── @expose ──────────────────────────────────────────────────────────────────

def expose(
    func:         Callable = None,
    *,
    method:       str  = "POST",
    path:         str  = None,
    version:      int  = 1,
    auth_required: bool = False,
    deprecated:   bool = False,
):
    """
    Registers a Python function as a Sagnos endpoint.
    Auto-generates a REST route AND a Dart method.

    Usage:
        @expose
        def get_user(id: int) -> User: ...

        @expose(method="GET", auth_required=True)
        async def list_users() -> list[User]: ...
    """
    def decorator(fn: Callable):
        hints = get_type_hints(fn)
        sig   = inspect.signature(fn)

        # Build param schema
        params = {}
        for param_name, param in sig.parameters.items():
            annotation    = hints.get(param_name, Any)
            is_opt, inner = _is_optional(annotation)
            params[param_name] = {
                "type":     annotation,
                "inner":    inner,
                "optional": is_opt,
                "required": param.default is inspect.Parameter.empty and not is_opt,
                "default":  None if param.default is inspect.Parameter.empty else param.default,
            }

        return_type       = hints.get("return", None)
        is_ret_opt, _     = _is_optional(return_type) if return_type else (False, None)
        route_path        = path or f"/{fn.__name__.replace('_', '-')}"
        is_sync           = not asyncio.iscoroutinefunction(fn)

        meta = {
            "fn":           fn,
            "method":       method.upper(),
            "path":         route_path,
            "version":      version,
            "params":       params,
            "return_type":  return_type,
            "return_optional": is_ret_opt,
            "auth_required": auth_required,
            "deprecated":   deprecated,
            "docstring":    inspect.getdoc(fn) or "",
            "is_sync":      is_sync,
        }

        _REGISTRY[fn.__name__] = meta

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            # Run sync functions in thread pool — never block the event loop
            if is_sync:
                loop   = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
            else:
                result = await fn(*args, **kwargs)

            # Validate + serialize the return value
            return _validate_return(result, return_type)

        wrapper._sagnos_exposed = True
        wrapper._sagnos_meta   = meta
        return wrapper

    # Called as @expose (no args)
    if func is not None:
        return decorator(func)

    # Called as @expose(...) with args
    return decorator


# ─── @model ───────────────────────────────────────────────────────────────────

def model(cls):
    """
    Registers a class as a Sagnos data model.
    Auto-generates Dart class with fromJson / toJson / copyWith.

    Usage:
        @model
        class User:
            id: int
            name: str
            email: str
    """
    from dataclasses import dataclass

    # Make it a dataclass automatically
    if not hasattr(cls, "__dataclass_fields__"):
        cls = dataclass(cls)

    hints  = get_type_hints(cls)
    schema = []

    for field_name, field_type in hints.items():
        if field_name.startswith("_"):
            continue

        is_opt, inner = _is_optional(field_type)
        is_special    = (inner if is_opt else field_type) in SPECIAL_TYPES
        is_enum       = isinstance((inner if is_opt else field_type), type) and \
                        issubclass((inner if is_opt else field_type), Enum)

        schema.append({
            "name":       field_name,
            "type":       field_type,
            "optional":   is_opt,
            "inner":      inner,
            "is_special": is_special,
            "is_enum":    is_enum,
        })

    cls._sagnos_model  = True
    cls._sagnos_schema = schema
    _MODELS[cls.__name__] = cls
    return cls


# ─── @stream ──────────────────────────────────────────────────────────────────

def stream(
    func: Callable = None,
    *,
    path: str  = None,
    auth_required: bool = False,
):
    """
    Registers an async generator as a WebSocket stream.
    Flutter uses SagnosStream<T> to subscribe to it.

    Usage:
        @stream
        async def live_feed() -> AsyncGenerator[User, None]:
            while True:
                yield get_latest_user()
                await asyncio.sleep(1)
    """
    def decorator(fn: Callable):
        hints      = get_type_hints(fn)
        route_path = path or f"/ws/{fn.__name__.replace('_', '-')}"

        return_hint = hints.get("return", None)
        yield_type  = None
        if return_hint is not None:
            args = getattr(return_hint, "__args__", ())
            if args:
                yield_type = args[0]

        _STREAMS[fn.__name__] = {
            "fn":           fn,
            "path":         route_path,
            "yield_type":   yield_type,
            "auth_required": auth_required,
            "docstring":    inspect.getdoc(fn) or "",
        }

        fn._sagnos_stream = True
        return fn

    if func is not None:
        return decorator(func)
    return decorator


# ─── Schema Hash ──────────────────────────────────────────────────────────────

def compute_schema_hash(schema: dict) -> str:
    """Stable hash of the schema — used for drift detection."""
    import json
    raw = json.dumps(
        {"endpoints": schema.get("endpoints", []), "models": schema.get("models", [])},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─── Registry Accessors ───────────────────────────────────────────────────────

def get_registry() -> dict:
    return _REGISTRY

def get_models() -> dict:
    return _MODELS

def get_streams() -> dict:
    return _STREAMS