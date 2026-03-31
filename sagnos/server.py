"""
sagnos/server.py
Wraps FastAPI. Auto-registers all @expose routes.
Handles errors, auth, health, schema endpoints.
"""

import asyncio
from typing import Any, Optional, Callable

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import create_model
import uvicorn

from .core import (
    get_registry, get_models, get_streams,
    SagnosError, NotFoundError, AuthError,
    _validate_return,
)
from .schema import export_schema


# ─── Auth ─────────────────────────────────────────────────────────────────────

class SagnosAuth:
    """
    Plug in your own auth logic.

    Usage:
        auth = SagnosAuth()

        @auth.handler
        def verify(token: str) -> dict:
            # decode JWT, check API key, anything
            return {"user_id": 1}

        app = SagnosApp(auth=auth)
    """
    def __init__(self):
        self._handler: Optional[Callable] = None

    def handler(self, fn: Callable):
        self._handler = fn
        return fn

    async def verify(self, request: Request) -> Optional[dict]:
        # No auth configured — let everything through
        if self._handler is None:
            return None

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AuthError("Missing or invalid Authorization header")

        token = auth_header.removeprefix("Bearer ").strip()

        try:
            if asyncio.iscoroutinefunction(self._handler):
                return await self._handler(token)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, lambda: self._handler(token)
                )
        except SagnosError:
            raise
        except Exception as e:
            raise AuthError(f"Auth failed: {str(e)}")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _error_response(error: SagnosError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=error.to_dict(),
    )

def _unknown_error_response(e: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "status":     "error",
            "error_code": "INTERNAL_ERROR",
            "message":    str(e),
            "detail":     type(e).__name__,
        },
    )

def _build_request_model(fn_name: str, params: dict):
    """Dynamically build a Pydantic model for request body validation."""
    fields = {}
    for pname, pmeta in params.items():
        py_type = pmeta["type"]
        default = ... if pmeta["required"] else pmeta["default"]
        fields[pname] = (py_type, default)

    if not fields:
        return None

    return create_model(f"_{fn_name}_Request", **fields)


# ─── SagnosApp ────────────────────────────────────────────────────────────────

class SagnosApp:
    """
    The main Sagnos application.

    Usage:
        app = SagnosApp()
        app.run()

    With auth:
        auth = SagnosAuth()

        @auth.handler
        def verify(token: str) -> dict:
            return jwt.decode(token, SECRET)

        app = SagnosApp(auth=auth)
        app.run()
    """

    def __init__(
        self,
        title:       str  = "Sagnos App",
        version:     str  = "0.1.0",
        cors_origins: list = ["*"],
        auth:        Optional[SagnosAuth] = None,
    ):
        self.fastapi = FastAPI(title=title, version=version)
        self.auth    = auth
        self._schema = None

        # ── CORS — Flutter needs this to talk to Python ──
        self.fastapi.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # ── Global error handlers ──
        @self.fastapi.exception_handler(SagnosError)
        async def sagnos_error_handler(request: Request, exc: SagnosError):
            return _error_response(exc)

        @self.fastapi.exception_handler(Exception)
        async def generic_error_handler(request: Request, exc: Exception):
            if isinstance(exc, SagnosError):
                return _error_response(exc)
            return _unknown_error_response(exc)

        self._register_routes()
        self._register_stream_routes()
        self._register_system_endpoints()

    # ─── Route Registration ───────────────────────────────────────────────────

    def _register_routes(self):
        for fn_name, meta in get_registry().items():
            RequestModel = _build_request_model(fn_name, meta["params"])
            self._add_route(fn_name, meta, RequestModel)

    def _add_route(self, fn_name: str, meta: dict, RequestModel):
        fn         = meta["fn"]
        method     = meta["method"]
        path       = meta["path"]
        params     = meta["params"]
        auth_req   = meta["auth_required"]
        deprecated = meta["deprecated"]
        auth       = self.auth

        async def _run(request: Request, kwargs: dict) -> Any:
            """Auth check then run the function."""
            if auth_req and auth:
                user_ctx = await auth.verify(request)
                if "current_user" in params:
                    kwargs["current_user"] = user_ctx
            return await fn(**kwargs)

        # ── GET route ──
        if method == "GET" or not params:
            async def get_handler(request: Request):
                try:
                    # Pull params from query string
                    coerced = {}
                    for pname, pmeta in params.items():
                        raw = request.query_params.get(pname)
                        if raw is None:
                            if pmeta["required"]:
                                raise SagnosError(
                                    f"Missing required param: {pname}"
                                )
                            coerced[pname] = pmeta["default"]
                        else:
                            # Coerce string → actual type
                            py_type = pmeta["inner"] if pmeta["optional"] else pmeta["type"]
                            try:
                                coerced[pname] = py_type(raw)
                            except Exception:
                                coerced[pname] = raw

                    result = await _run(request, coerced)
                    return {"status": "ok", "data": result}

                except SagnosError as e:
                    return _error_response(e)
                except Exception as e:
                    return _unknown_error_response(e)

            self.fastapi.get(
                path,
                summary=fn_name,
                deprecated=deprecated,
                tags=["Endpoints"],
            )(get_handler)

        # ── POST route ──
        else:
            if RequestModel:
                async def post_handler(request: Request, body: RequestModel):
                    try:
                        result = await _run(request, body.model_dump())
                        return {"status": "ok", "data": result}
                    except SagnosError as e:
                        return _error_response(e)
                    except Exception as e:
                        return _unknown_error_response(e)
            else:
                async def post_handler(request: Request):
                    try:
                        result = await _run(request, {})
                        return {"status": "ok", "data": result}
                    except SagnosError as e:
                        return _error_response(e)
                    except Exception as e:
                        return _unknown_error_response(e)

            self.fastapi.post(
                path,
                summary=fn_name,
                deprecated=deprecated,
                tags=["Endpoints"],
            )(post_handler)

    # ─── WebSocket Stream Routes ──────────────────────────────────────────────

    def _register_stream_routes(self):
        streams = get_streams()
        if not streams:
            return

        for fn_name, meta in streams.items():
            self._add_stream_route(fn_name, meta)

    def _add_stream_route(self, fn_name: str, meta: dict):
        fn         = meta["fn"]
        path       = meta["path"]
        yield_type = meta["yield_type"]
        auth_req   = meta["auth_required"]
        auth       = self.auth

        async def ws_handler(websocket: WebSocket):
            await websocket.accept()

            # Auth check for WebSocket
            if auth_req and auth:
                token = websocket.headers.get(
                    "Authorization", ""
                ).removeprefix("Bearer ").strip()
                if not token:
                    import json
                    await websocket.send_text(json.dumps({
                        "status":     "error",
                        "error_code": "UNAUTHORIZED",
                        "message":    "Missing auth token",
                    }))
                    await websocket.close()
                    return

            # Read initial params from first message
            params = {}
            try:
                import json
                raw    = await asyncio.wait_for(
                    websocket.receive_text(), timeout=3.0
                )
                params = json.loads(raw)
            except Exception:
                pass

            try:
                import json
                async for value in fn(**params):
                    serialized = _validate_return(value, yield_type)
                    await websocket.send_text(json.dumps({
                        "status": "ok",
                        "data":   serialized,
                    }))

            except Exception as e:
                try:
                    import json
                    await websocket.send_text(json.dumps({
                        "status":     "error",
                        "error_code": "STREAM_ERROR",
                        "message":    str(e),
                    }))
                except Exception:
                    pass
            finally:
                try:
                    await websocket.close()
                except Exception:
                    pass

        self.fastapi.websocket(path)(ws_handler)

    # ─── System Endpoints ─────────────────────────────────────────────────────

    def _register_system_endpoints(self):

        @self.fastapi.get("/sagnos/health", tags=["Sagnos"])
        def health():
            """Flutter checks this on startup to know Python is ready."""
            return {
                "status":    "alive",
                "framework": "Sagnos",
                "endpoints": len(get_registry()),
                "models":    len(get_models()),
                "streams":   len(get_streams()),
            }

        @self.fastapi.get("/sagnos/schema", tags=["Sagnos"])
        def schema():
            """The code generator reads this to generate Dart files."""
            if self._schema is None:
                self._schema = export_schema()
            return self._schema

        @self.fastapi.get("/sagnos/schema-version", tags=["Sagnos"])
        def schema_version():
            """Flutter checks this hash to detect schema drift."""
            if self._schema is None:
                self._schema = export_schema()
            return {
                "schema_hash": self._schema["schema_hash"],
                "version":     self._schema["version"],
            }

    # ─── Run ──────────────────────────────────────────────────────────────────

    def run(
        self,
        host:    str = "127.0.0.1",
        port:    int = 8000,
        reload:  bool = False,
    ):
        schema = export_schema()

        print(f"""
╔══════════════════════════════════════════════╗
║            🐍  Sagnos v0.1.0                 ║
╠══════════════════════════════════════════════╣
║  Server  →  http://{host}:{port}
║  Docs    →  http://{host}:{port}/docs
║  Schema  →  http://{host}:{port}/sagnos/schema
║  Hash    →  {schema['schema_hash']}
║  Routes  →  {len(get_registry())} endpoints
║  Models  →  {len(get_models())} models
║  Streams →  {len(get_streams())} streams
╚══════════════════════════════════════════════╝
        """)

        uvicorn.run(
            self.fastapi,
            host=host,
            port=port,
            reload=reload,
        )