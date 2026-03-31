# 🐍 Sagnos

> The Spring Boot of Python for Flutter.

Write Python. Get a Flutter app. Zero manual API code.

---

## What is Sagnos?

Building a Flutter app with a Python backend normally means:

- Manually writing HTTP calls in Dart
- Manually parsing JSON
- Manually keeping Python and Dart models in sync
- Silent runtime crashes when you rename a field

**Sagnos eliminates all of that.**

You write Python functions with type hints. Sagnos automatically generates the entire Dart client — models, HTTP calls, error handling, everything.

---

## The 30-Second Demo

**You write this Python:**

```python
from sagnos import expose, model, SagnosApp

@model
class User:
    id:    int
    name:  str
    email: str

@expose
async def get_user(id: int) -> User:
    return User(id=id, name="Ada Lovelace", email="ada@dev.com")

@expose
async def list_users() -> list[User]:
    return [User(id=1, name="Ada", email="ada@dev.com")]

app = SagnosApp()
app.run()
```

**Sagnos generates this Dart automatically:**

```dart
// You never write this — Sagnos generates it
class User {
  final int id;
  final String name;
  final String email;
  // fromJson, toJson, copyWith all included
}

class SagnosClient {
  Future<User> getUser(int id) async { ... }
  Future<List<User>> listUsers() async { ... }
}
```

**You use it in Flutter like this:**

```dart
final client = SagnosClient();

// That's it. No HTTP. No JSON. Full type safety.
final user = await client.getUser(1);
Text(user.name)
```

---

## Why Sagnos?

|                                 | Plain FastAPI + Flutter | Firebase | gRPC            | **Sagnos** |
| ------------------------------- | ----------------------- | -------- | --------------- | ---------- |
| Write Python backend            | ✅                      | ❌       | ✅              | ✅         |
| Keep real Flutter UI            | ✅                      | ✅       | ✅              | ✅         |
| Auto-generate Dart client       | ❌                      | ❌       | ✅ (via .proto) | ✅         |
| Python-native (just decorators) | ❌                      | ❌       | ❌              | ✅         |
| Works with Python ML/AI         | ✅                      | ❌       | ✅              | ✅         |
| Zero boilerplate both sides     | ❌                      | ❌       | ❌              | ✅         |

---

## Installation

```bash
pip install sagnos
```

Flutter side — add to `pubspec.yaml`:

```yaml
dependencies:
  http: ^1.2.0
```

---

## Quick Start

### 1. Write your Python backend

```python
# backend.py
from datetime import datetime
from typing import Optional
from sagnos import expose, model, SagnosApp, NotFoundError

@model
class Product:
    id:       int
    title:    str
    price:    float
    in_stock: bool

PRODUCTS = {
    1: Product(id=1, title="Keyboard", price=49.99, in_stock=True),
    2: Product(id=2, title="Monitor",  price=299.99, in_stock=False),
}

@expose(method="GET")
async def list_products() -> list[Product]:
    """Get all products"""
    return list(PRODUCTS.values())

@expose(method="GET")
async def get_product(id: int) -> Product:
    """Get product by ID"""
    product = PRODUCTS.get(id)
    if not product:
        raise NotFoundError(f"Product {id} not found")
    return product

@expose
async def create_product(title: str, price: float) -> Product:
    """Create a new product"""
    new_id = max(PRODUCTS.keys()) + 1
    product = Product(id=new_id, title=title, price=price, in_stock=True)
    PRODUCTS[new_id] = product
    return product

if __name__ == "__main__":
    app = SagnosApp(title="My Shop")
    app.run()
```

### 2. Run the backend

```bash
python backend.py
```

```
╔══════════════════════════════════════════════╗
║            🐍  Sagnos v0.1.0                 ║
╠══════════════════════════════════════════════╣
║  Server  →  http://127.0.0.1:8000            ║
║  Docs    →  http://127.0.0.1:8000/docs       ║
║  Schema  →  http://127.0.0.1:8000/sagnos/schema
╚══════════════════════════════════════════════╝
```

### 3. Generate Dart bindings

```bash
python -c "
from sagnos.codegen import generate
generate(
  'http://127.0.0.1:8000/sagnos/schema',
  './my_flutter_app/lib/sagnos'
)
"
```

This generates 4 files into your Flutter project:

```
my_flutter_app/lib/sagnos/
├── models.dart            ← Product class, fromJson, toJson
├── sagnos_client.dart     ← listProducts(), getProduct(), createProduct()
├── sagnos_exception.dart  ← typed error handling
└── sagnos_stream.dart     ← WebSocket streaming support
```

### 4. Use in Flutter

```dart
import 'sagnos/sagnos_client.dart';
import 'sagnos/models.dart';
import 'sagnos/sagnos_exception.dart';

final client = SagnosClient(baseUrl: 'http://127.0.0.1:8000');

// List products
final products = await client.listProducts();

// Get one product
final product = await client.getProduct(1);
print(product.title); // Keyboard

// Create a product
final newProduct = await client.createProduct('USB Hub', 29.99);

// Typed error handling
try {
  await client.getProduct(999);
} on SagnosException catch (e) {
  if (e.isNotFound) print('Product not found');
}
```

---

## Decorators

### `@model`

Registers a Python class as a Sagnos data model.
Auto-generates the Dart class with `fromJson`, `toJson`, `copyWith`.

```python
@model
class User:
    id:         int
    name:       str
    created_at: datetime       # → DateTime in Dart
    bio:        Optional[str]  # → String? in Dart (null safe)
```

### `@expose`

Registers a function as a REST endpoint.
Auto-generates a typed Dart method in `SagnosClient`.

```python
@expose(method="GET")               # GET or POST
async def get_user(id: int) -> User:
    ...

@expose(auth_required=True)         # Protected endpoint
async def delete_user(id: int) -> bool:
    ...

@expose(deprecated=True)            # Marks as deprecated in Dart
async def old_endpoint() -> str:
    ...
```

### `@stream`

Registers an async generator as a WebSocket stream.
Auto-generates `SagnosStream<T>` usage in Flutter.

```python
@stream
async def live_updates() -> AsyncGenerator[User, None]:
    while True:
        yield get_latest_user()
        await asyncio.sleep(1)
```

```dart
// Flutter side
final stream = SagnosStream<User>(
  url: 'ws://127.0.0.1:8000/ws/live-updates',
  fromJson: User.fromJson,
);
stream.stream.listen((user) => setState(() => _user = user));
```

---

## Type Mapping

Sagnos automatically converts Python types to Dart:

| Python         | Dart        |
| -------------- | ----------- |
| `int`          | `int`       |
| `float`        | `double`    |
| `str`          | `String`    |
| `bool`         | `bool`      |
| `datetime`     | `DateTime`  |
| `UUID`         | `String`    |
| `Decimal`      | `double`    |
| `Optional[X]`  | `X?`        |
| `list[X]`      | `List<X>`   |
| `dict[K, V]`   | `Map<K, V>` |
| `@model class` | Dart class  |

---

## Error Handling

Define typed errors in Python:

```python
from sagnos import NotFoundError, ValidationError_, AuthError

@expose
async def get_user(id: int) -> User:
    user = db.get(id)
    if not user:
        raise NotFoundError(f"User {id} not found")
    return user
```

Catch them by type in Flutter:

```dart
try {
  final user = await client.getUser(999);
} on SagnosException catch (e) {
  if (e.isNotFound)     print('User not found');
  if (e.isUnauthorized) print('Please login');
  if (e.isValidation)   print('Bad input: ${e.message}');
}
```

---

## Real World Use Cases

**AI Mobile App**

```python
import torch
from sagnos import expose, model, SagnosApp

@model
class Prediction:
    label:      str
    confidence: float

@expose
async def predict(text: str) -> Prediction:
    result = my_ml_model(text)
    return Prediction(label=result.label, confidence=result.score)
```

Flutter sends text, Python ML model processes it, result shows in UI. Zero HTTP code written.

**IoT Dashboard**

```python
@stream
async def sensor_data() -> AsyncGenerator[Reading, None]:
    while True:
        yield read_sensor()
        await asyncio.sleep(0.5)
```

Real-time sensor readings streamed to Flutter UI via WebSocket.

---

## Project Structure

```
my_app/
├── backend.py              ← your Python code (@expose, @model)
├── requirements.txt
└── flutter_app/
    ├── lib/
    │   ├── main.dart       ← your Flutter UI
    │   └── sagnos/         ← AUTO-GENERATED, never edit
    │       ├── models.dart
    │       ├── sagnos_client.dart
    │       ├── sagnos_exception.dart
    │       └── sagnos_stream.dart
    └── pubspec.yaml
```

**Rule:** Edit `backend.py` for logic. Edit `main.dart` for UI. Never touch the `sagnos/` folder — it gets regenerated.

---

## API Docs

When your backend is running, visit:

- **`http://localhost:8000/docs`** — Interactive Swagger UI
- **`http://localhost:8000/sagnos/schema`** — Raw schema JSON
- **`http://localhost:8000/sagnos/health`** — Health check

---

## Contributing

Pull requests welcome. For major changes please open an issue first.

```bash
git clone https://github.com/YOUR_USERNAME/sagnos
cd sagnos
python -m venv .venv
.venv\Scripts\activate
pip install -e .
pytest tests/ -v
```

---

## License

MIT

---

## Author

Built by Siddhardh — an 18-year-old CS student who wanted Python to work seamlessly with Flutter.

_"Write Python. Get Flutter. That's it."_
