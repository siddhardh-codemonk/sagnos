import tempfile
from pathlib import Path
from sagnos.core import expose, model
from sagnos.schema import export_schema
from sagnos.codegen import generate_from_schema
from datetime import datetime
from typing import Optional

@model
class TestUser:
    id:   int
    name: str

@expose(method="GET")
async def get_test_user(id: int) -> TestUser:
    return TestUser(id=id, name="Test")

def test_codegen_creates_files():
    schema = export_schema()

    with tempfile.TemporaryDirectory() as tmpdir:
        generate_from_schema(schema, tmpdir)
        files = [f.name for f in Path(tmpdir).iterdir()]
        assert "models.dart"           in files
        assert "sagnos_client.dart"    in files
        assert "sagnos_exception.dart" in files
        assert "sagnos_stream.dart"    in files

def test_schema_has_models():
    schema = export_schema()
    names  = [m["name"] for m in schema["models"]]
    assert "TestUser" in names

def test_schema_has_endpoints():
    schema = export_schema()
    names  = [e["name"] for e in schema["endpoints"]]
    assert "get_test_user" in names