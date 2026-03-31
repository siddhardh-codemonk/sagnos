from sagnos.core import expose, model, get_registry, get_models

def test_expose_registers_function():
    @expose
    def say_hello(name: str) -> str:
        return f"Hello {name}"

    assert "say_hello" in get_registry()

def test_expose_method_default_is_post():
    registry = get_registry()
    assert registry["say_hello"]["method"] == "POST"

def test_model_registers_class():
    @model
    class Item:
        id:    int
        title: str

    assert "Item" in get_models()

def test_model_schema_has_fields():
    models = get_models()
    fields = [f["name"] for f in models["Item"]._sagnos_schema]
    assert "id"    in fields
    assert "title" in fields