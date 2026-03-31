from sagnos.schema import python_type_to_dart
from typing import Optional
from datetime import datetime

def test_int_to_dart():
    assert python_type_to_dart(int) == "int"

def test_str_to_dart():
    assert python_type_to_dart(str) == "String"

def test_optional_str_to_dart():
    assert python_type_to_dart(Optional[str]) == "String?"

def test_list_int_to_dart():
    assert python_type_to_dart(list[int]) == "List<int>"

def test_datetime_to_dart():
    assert python_type_to_dart(datetime) == "DateTime"

def test_optional_int_nullable():
    result = python_type_to_dart(Optional[int])
    assert result.endswith("?")