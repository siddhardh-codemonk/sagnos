"""
sagnos/schema.py
Converts Python types to Dart types.
Exports the full schema JSON for the Dart code generator.
"""

from typing import Any, get_origin, get_args, Union
from enum import Enum
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal

from .core import get_registry, get_models, get_streams, compute_schema_hash, SPECIAL_TYPES


# ─── Python → Dart Type Map ───────────────────────────────────────────────────

PRIMITIVE_MAP = {
    int:        "int",
    float:      "double",
    str:        "String",
    bool:       "bool",
    Any:        "dynamic",
    type(None): "void",
}


def python_type_to_dart(py_type, nullable: bool = False) -> str:
    """
    Converts any Python type annotation to its Dart equivalent.

    Examples:
        int            → int
        Optional[str]  → String?
        list[User]     → List<User>
        dict[str, int] → Map<String, int>
        datetime       → DateTime
        Optional[User] → User?
    """
    suffix = "?" if nullable else ""

    if py_type is None or py_type is type(None):
        return "void"

    # Primitives
    if py_type in PRIMITIVE_MAP:
        return PRIMITIVE_MAP[py_type] + suffix

    # Special types (datetime, UUID, Decimal)
    if py_type in SPECIAL_TYPES:
        return SPECIAL_TYPES[py_type]["dart_type"] + suffix

    origin = get_origin(py_type)
    args   = get_args(py_type)

    # Optional[X] → X?
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if type(None) in args and non_none:
            return python_type_to_dart(non_none[0], nullable=True)

    # list[X] → List<X>
    if origin is list:
        inner = python_type_to_dart(args[0]) if args else "dynamic"
        return f"List<{inner}>{suffix}"

    # dict[K, V] → Map<K, V>
    if origin is dict:
        key = python_type_to_dart(args[0]) if args else "String"
        val = python_type_to_dart(args[1]) if len(args) > 1 else "dynamic"
        return f"Map<{key}, {val}>{suffix}"

    # Enum → String
    if isinstance(py_type, type) and issubclass(py_type, Enum):
        return f"String{suffix}"

    # @model class → use the class name directly
    if hasattr(py_type, "__name__"):
        return py_type.__name__ + suffix

    return f"dynamic{suffix}"


# ─── fromJson expression per field ───────────────────────────────────────────

def dart_from_json(field_name: str, py_type, nullable: bool = False) -> str:
    null_guard = f"json['{field_name}'] == null ? null : " if nullable else ""

    # Special types
    if py_type in (datetime, date):
        return f"{null_guard}DateTime.parse(json['{field_name}'] as String)"
    if py_type is UUID:
        return f"{null_guard}json['{field_name}'] as String"
    if py_type is Decimal:
        return f"{null_guard}(json['{field_name}'] as num).toDouble()"

    # Primitives
    if py_type is int:
        return f"{null_guard}json['{field_name}'] as int"
    if py_type is float:
        return f"{null_guard}(json['{field_name}'] as num).toDouble()"
    if py_type is str:
        return f"{null_guard}json['{field_name}'] as String"
    if py_type is bool:
        return f"{null_guard}json['{field_name}'] as bool"

    # Enum
    if isinstance(py_type, type) and issubclass(py_type, Enum):
        return f"{null_guard}json['{field_name}'] as String"

    origin = get_origin(py_type)
    args   = get_args(py_type)

    # Optional[X]
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return dart_from_json(field_name, non_none[0], nullable=True)

    # list[X]
    if origin is list and args:
        inner = args[0]
        if hasattr(inner, "__name__") and inner not in PRIMITIVE_MAP:
            return (
                f"{null_guard}(json['{field_name}'] as List)"
                f".map((e) => {inner.__name__}.fromJson(e as Map<String, dynamic>)).toList()"
            )
        dart_inner = python_type_to_dart(inner)
        return f"{null_guard}(json['{field_name}'] as List).cast<{dart_inner}>()"

    # @model
    if hasattr(py_type, "__name__"):
        return f"{null_guard}{py_type.__name__}.fromJson(json['{field_name}'] as Map<String, dynamic>)"

    return f"json['{field_name}']"


# ─── toJson expression per field ─────────────────────────────────────────────

def dart_to_json(field_name: str, py_type, nullable: bool = False) -> str:
    dart_name = snake_to_camel(field_name)

    # Special types need serialization
    if py_type in (datetime, date):
        return f"{dart_name}{'?' if nullable else ''}.toIso8601String()"

    origin = get_origin(py_type)
    args   = get_args(py_type)

    # Optional[X]
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return dart_to_json(field_name, non_none[0], nullable=True)

    # list of @model
    if origin is list and args:
        inner = args[0]
        if hasattr(inner, "_sagnos_model"):
            return f"{dart_name}.map((e) => e.toJson()).toList()"

    # @model
    if hasattr(py_type, "_sagnos_model"):
        return f"{dart_name}{'?' if nullable else ''}.toJson()"

    return dart_name


# ─── snake_case → camelCase ───────────────────────────────────────────────────

def snake_to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


# ─── Full Schema Export ───────────────────────────────────────────────────────

def export_schema() -> dict:
    """
    Exports the full registry as a JSON-serializable dict.
    This is what the Dart code generator reads.
    """
    registry = get_registry()
    models   = get_models()
    streams  = get_streams()

    # ── Endpoints ──
    endpoints = []
    for fn_name, meta in registry.items():
        params_out = []
        for pname, pmeta in meta["params"].items():
            params_out.append({
                "name":      pname,
                "dart_type": python_type_to_dart(pmeta["type"]),
                "required":  pmeta["required"],
                "optional":  pmeta["optional"],
                "default":   str(pmeta["default"]) if pmeta["default"] is not None else None,
            })

        ret_dart = python_type_to_dart(meta["return_type"]) if meta["return_type"] else "void"

        endpoints.append({
            "name":            fn_name,
            "dart_method":     snake_to_camel(fn_name),
            "method":          meta["method"],
            "path":            meta["path"],
            "params":          params_out,
            "return_dart":     ret_dart,
            "return_optional": meta["return_optional"],
            "auth_required":   meta["auth_required"],
            "deprecated":      meta["deprecated"],
            "docstring":       meta["docstring"],
        })

    # ── Models ──
    models_out = []
    for model_name, model_cls in models.items():
        fields_out = []
        for field_meta in model_cls._sagnos_schema:
            fname    = field_meta["name"]
            ftype    = field_meta["type"]
            optional = field_meta["optional"]
            inner    = field_meta["inner"]
            actual   = inner if optional else ftype

            fields_out.append({
                "name":      fname,
                "dart_name": snake_to_camel(fname),
                "dart_type": python_type_to_dart(ftype),
                "from_json": dart_from_json(fname, actual, nullable=optional),
                "to_json":   dart_to_json(fname, actual, nullable=optional),
                "optional":  optional,
            })

        models_out.append({
            "name":   model_name,
            "fields": fields_out,
        })

    # ── Streams ──
    streams_out = []
    for fn_name, meta in streams.items():
        streams_out.append({
            "name":        fn_name,
            "dart_method": snake_to_camel(fn_name),
            "path":        meta["path"],
            "yield_dart":  python_type_to_dart(meta["yield_type"]) if meta["yield_type"] else "dynamic",
            "docstring":   meta["docstring"],
        })

    schema = {
        "version":   "0.1.0",
        "framework": "Sagnos",
        "endpoints": endpoints,
        "models":    models_out,
        "streams":   streams_out,
    }

    schema["schema_hash"] = compute_schema_hash(schema)
    return schema