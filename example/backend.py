"""
The example backend — run this to test Sagnos end to end.
"""

from datetime import datetime
from typing import Optional
from sagnos import expose, model, stream, SagnosApp, NotFoundError

@model
class User:
    id:         int
    name:       str
    email:      str
    created_at: datetime
    bio:        Optional[str]

@model
class Product:
    id:       int
    title:    str
    price:    float
    in_stock: bool

# Fake DB
USERS = {
    1: User(id=1, name="Ada Lovelace",  email="ada@dev.com",  created_at=datetime.now(), bio="First programmer"),
    2: User(id=2, name="Alan Turing",   email="alan@dev.com", created_at=datetime.now(), bio=None),
}

PRODUCTS = {
    1: Product(id=1, title="Keyboard", price=49.99, in_stock=True),
    2: Product(id=2, title="Monitor",  price=299.99, in_stock=False),
}

@expose(method="GET")
async def get_user(id: int) -> User:
    """Get user by ID"""
    user = USERS.get(id)
    if not user:
        raise NotFoundError(f"User {id} not found")
    return user

@expose(method="GET")
async def list_users() -> list[User]:
    """Get all users"""
    return list(USERS.values())

@expose
async def create_user(name: str, email: str) -> User:
    """Create a new user"""
    new_id         = max(USERS.keys()) + 1
    user           = User(id=new_id, name=name, email=email, created_at=datetime.now(), bio=None)
    USERS[new_id]  = user
    return user

@expose(method="GET")
async def list_products() -> list[Product]:
    """Get all products"""
    return list(PRODUCTS.values())

if __name__ == "__main__":
    app = SagnosApp(title="Sagnos Example")
    app.run()