from decimal import Decimal

from sqlmodel import Session, select

from app.core.database import create_db_and_tables, engine
from app.core.security import hash_password
from app.modules.category.models import Category
from app.modules.ingredient.models import Ingredient
from app.modules.pagos.models import FormaPago
from app.modules.pedidos.models import EstadoPedido
from app.modules.pedidos.schemas import EstadoPedidoEnum
from app.modules.product.models import (
    Product,
    ProductCategoryLink,
    ProductIngredientLink,
)
from app.modules.user.models import User
from app.modules.user.rol import Rol
from app.modules.user.user_rol import UserRol

# Importados para que create_db_and_tables() registre todas las tablas
import app.modules.direcciones.models  # noqa


# ── Datos iniciales — seguridad ───────────────────────────────────────────────

ROLES_INICIALES = [
    Rol(code="ADMIN",   name="Administrador", description="Acceso total sin restricciones"),
    Rol(code="STOCK",   name="Stock",         description="Actualiza stock y disponible"),
    Rol(code="PEDIDOS", name="Pedidos",        description="Avanza estados CONFIRMADO a ENTREGADO"),
    Rol(code="CLIENT",  name="Cliente",        description="Opera solo sus propios datos"),
]

USUARIOS_INICIALES = [
    {
        "username":  "admin",
        "full_name": "Administrador del Sistema",
        "email":     "admin@example.com",
        "password":  "Admin1234!",
        "rol_code":  "ADMIN",
    },
    {
        "username":  "juan",
        "full_name": "Juan Pérez",
        "email":     "juan@example.com",
        "password":  "Juan1234!",
        "rol_code":  "CLIENT",
    },
    {
        "username":  "lionel",
        "full_name": "Lionel Messi",
        "email":     "lionel@example.com",
        "password":  "Lionel1234!",
        "rol_code":  "STOCK",
    },
    {
        "username":  "pepe",
        "full_name": "Pepe Argento",
        "email":     "pepe@example.com",
        "password":  "Pepe1234!",
        "rol_code":  "PEDIDOS",
    },
]


def seed_estado_pedido(db: Session) -> None:
    estados = [
        {
            "codigo": EstadoPedidoEnum.PENDIENTE,
            "descripcion": "Pedido recibido, esperando confirmación",
            "orden": 1,
        },
        {
            "codigo": EstadoPedidoEnum.CONFIRMADO,
            "descripcion": "Pago confirmado, listo para preparar",
            "orden": 2,
        },
        {
            "codigo": EstadoPedidoEnum.EN_PREP,
            "descripcion": "En preparación en cocina",
            "orden": 3,
        },
        {
            "codigo": EstadoPedidoEnum.EN_CAMINO,
            "descripcion": "En camino al cliente",
            "orden": 4,
        },
        {
            "codigo": EstadoPedidoEnum.ENTREGADO,
            "descripcion": "Entregado exitosamente",
            "orden": 5,
        },
        {
            "codigo": EstadoPedidoEnum.CANCELADO,
            "descripcion": "Pedido cancelado",
            "orden": 6,
        },
    ]
    for est in estados:
        if not db.exec(
            select(EstadoPedido).where(EstadoPedido.codigo == est["codigo"])
        ).first():
            db.add(EstadoPedido(**est))
    db.commit()


def seed_formas_pago(db: Session) -> None:
    formas = [
        {
            "nombre": "Efectivo",
            "descripcion": "Pago en efectivo al recibir",
            "requiere_monto_pago": True,
        },
        {
            "nombre": "Tarjeta Débito",
            "descripcion": "Pago con tarjeta de débito",
            "requiere_monto_pago": False,
        },
        {
            "nombre": "Tarjeta Crédito",
            "descripcion": "Pago con tarjeta de crédito",
            "requiere_monto_pago": False,
        },
        {
            "nombre": "Mercado Pago",
            "descripcion": "Pago mediante plataforma Mercado Pago",
            "requiere_monto_pago": False,
        },
    ]
    for fp in formas:
        if not db.exec(
            select(FormaPago).where(FormaPago.nombre == fp["nombre"])
        ).first():
            db.add(FormaPago(**fp))
    db.commit()


def seed_categories(db: Session) -> dict[str, Category]:
    """Crea categorías padre y subcategorías. Retorna dict name -> Category."""

    padres = [
        {
            "name": "Hamburguesas",
            "description": "Hamburguesas artesanales",
            "order_display": 1,
        },
        {"name": "Bebidas", "description": "Bebidas frías", "order_display": 2},
        {
            "name": "Acompañamientos",
            "description": "Para complementar tu pedido",
            "order_display": 3,
        },
        {"name": "Postres", "description": "El toque dulce final", "order_display": 4},
    ]

    cats: dict[str, Category] = {}
    for data in padres:
        obj = db.exec(select(Category).where(Category.name == data["name"])).first()
        if not obj:
            obj = Category(**data)
            db.add(obj)
            db.flush()
        cats[data["name"]] = obj

    subcats = [
        {
            "name": "Clásicas",
            "description": "Las favoritas de siempre",
            "order_display": 1,
            "parent_id": cats["Hamburguesas"].id,
        },
        {
            "name": "Premium",
            "description": "Ingredientes seleccionados",
            "order_display": 2,
            "parent_id": cats["Hamburguesas"].id,
        },
        {
            "name": "Sin Alcohol",
            "description": "Refrescos, jugos y agua",
            "order_display": 1,
            "parent_id": cats["Bebidas"].id,
        },
    ]
    for data in subcats:
        obj = db.exec(select(Category).where(Category.name == data["name"])).first()
        if not obj:
            obj = Category(**data)
            db.add(obj)
            db.flush()
        cats[data["name"]] = obj

    db.commit()
    return cats


def seed_ingredients(db: Session) -> dict[str, Ingredient]:
    """Crea ingredientes. Retorna dict name -> Ingredient."""

    data = [
        {
            "name": "Pan brioche",
            "description": "Pan suave y esponjoso",
            "is_allergen": True,
        },
        {
            "name": "Carne vacuna",
            "description": "Medallón de carne 200g",
            "is_allergen": False,
        },
        {"name": "Lechuga", "description": "Lechuga fresca", "is_allergen": False},
        {
            "name": "Tomate",
            "description": "Tomate fresco en rodajas",
            "is_allergen": False,
        },
        {"name": "Cebolla", "description": "Cebolla morada", "is_allergen": False},
        {
            "name": "Queso cheddar",
            "description": "Queso cheddar fundido",
            "is_allergen": True,
        },
        {"name": "Bacon", "description": "Panceta crocante", "is_allergen": False},
        {"name": "Mayonesa", "description": "Mayonesa casera", "is_allergen": True},
        {"name": "Ketchup", "description": "Salsa ketchup", "is_allergen": False},
        {"name": "Mostaza", "description": "Mostaza Dijón", "is_allergen": False},
        {"name": "Salsa BBQ", "description": "Salsa BBQ ahumada", "is_allergen": False},
        {
            "name": "Jalapeños",
            "description": "Jalapeños encurtidos",
            "is_allergen": False,
        },
        {"name": "Papas", "description": "Papa blanca", "is_allergen": False},
        {"name": "Huevo", "description": "Huevo frito", "is_allergen": True},
    ]

    ingrs: dict[str, Ingredient] = {}
    for d in data:
        obj = db.exec(select(Ingredient).where(Ingredient.name == d["name"])).first()
        if not obj:
            obj = Ingredient(**d)
            db.add(obj)
            db.flush()
        ingrs[d["name"]] = obj

    db.commit()
    return ingrs


def _link_categories(
    db: Session, product: Product, categories: list[tuple[Category, bool]]
) -> None:
    """Vincula un producto con sus categorías. El segundo elemento de la tupla indica si es primaria."""
    for cat, is_primary in categories:
        exists = db.exec(
            select(ProductCategoryLink).where(
                ProductCategoryLink.product_id == product.id,
                ProductCategoryLink.category_id == cat.id,
            )
        ).first()
        if not exists:
            db.add(
                ProductCategoryLink(
                    product_id=product.id, category_id=cat.id, is_primary=is_primary
                )
            )


def _link_ingredients(
    db: Session, product: Product, ingredients: list[tuple[Ingredient, bool]]
) -> None:
    """Vincula un producto con sus ingredientes. El segundo elemento indica si es removible."""
    for ingr, is_removable in ingredients:
        exists = db.exec(
            select(ProductIngredientLink).where(
                ProductIngredientLink.product_id == product.id,
                ProductIngredientLink.ingredient_id == ingr.id,
            )
        ).first()
        if not exists:
            db.add(
                ProductIngredientLink(
                    product_id=product.id,
                    ingredient_id=ingr.id,
                    is_removable=is_removable,
                )
            )


def seed_products(
    db: Session, cats: dict[str, Category], ingrs: dict[str, Ingredient]
) -> None:
    productos = [
        {
            "data": {
                "name": "Hamburguesa Clásica",
                "description": "La clásica de siempre: carne, lechuga, tomate y mayonesa",
                "base_price": Decimal("1500.00"),
                "stock_quantity": 50,
                "prep_time_min": 15,
            },
            "cats": [("Clásicas", True), ("Hamburguesas", False)],
            "ingrs": [
                ("Pan brioche", False),
                ("Carne vacuna", False),
                ("Lechuga", True),
                ("Tomate", True),
                ("Cebolla", True),
                ("Mayonesa", True),
            ],
        },
        {
            "data": {
                "name": "Hamburguesa BBQ Bacon",
                "description": "Carne jugosa, bacon crocante y salsa BBQ ahumada",
                "base_price": Decimal("2000.00"),
                "stock_quantity": 30,
                "prep_time_min": 20,
            },
            "cats": [("Premium", True), ("Hamburguesas", False)],
            "ingrs": [
                ("Pan brioche", False),
                ("Carne vacuna", False),
                ("Queso cheddar", True),
                ("Bacon", True),
                ("Salsa BBQ", True),
                ("Cebolla", True),
            ],
        },
        {
            "data": {
                "name": "Hamburguesa Doble",
                "description": "Doble medallón de carne con queso cheddar",
                "base_price": Decimal("2200.00"),
                "stock_quantity": 25,
                "prep_time_min": 20,
            },
            "cats": [("Clásicas", True), ("Hamburguesas", False)],
            "ingrs": [
                ("Pan brioche", False),
                ("Carne vacuna", False),
                ("Queso cheddar", True),
                ("Lechuga", True),
                ("Tomate", True),
                ("Mayonesa", True),
            ],
        },
        {
            "data": {
                "name": "Hamburguesa Picante",
                "description": "Para los que la quieren con fuego: jalapeños y salsa BBQ",
                "base_price": Decimal("1900.00"),
                "stock_quantity": 20,
                "prep_time_min": 18,
            },
            "cats": [("Premium", True), ("Hamburguesas", False)],
            "ingrs": [
                ("Pan brioche", False),
                ("Carne vacuna", False),
                ("Jalapeños", True),
                ("Queso cheddar", True),
                ("Salsa BBQ", True),
                ("Mayonesa", True),
            ],
        },
        {
            "data": {
                "name": "Papas Fritas",
                "description": "Papas fritas crocantes con sal",
                "base_price": Decimal("800.00"),
                "stock_quantity": 100,
                "prep_time_min": 10,
            },
            "cats": [("Acompañamientos", True)],
            "ingrs": [("Papas", False)],
        },
        {
            "data": {
                "name": "Aros de Cebolla",
                "description": "Cebolla rebozada y frita",
                "base_price": Decimal("900.00"),
                "stock_quantity": 80,
                "prep_time_min": 12,
            },
            "cats": [("Acompañamientos", True)],
            "ingrs": [("Cebolla", False)],
        },
        {
            "data": {
                "name": "Coca Cola 500ml",
                "description": "Bebida gaseosa fría",
                "base_price": Decimal("600.00"),
                "stock_quantity": 150,
                "prep_time_min": 1,
            },
            "cats": [("Sin Alcohol", True), ("Bebidas", False)],
            "ingrs": [],
        },
        {
            "data": {
                "name": "Agua Mineral 500ml",
                "description": "Agua mineral sin gas",
                "base_price": Decimal("400.00"),
                "stock_quantity": 200,
                "prep_time_min": 1,
            },
            "cats": [("Sin Alcohol", True), ("Bebidas", False)],
            "ingrs": [],
        },
        {
            "data": {
                "name": "Brownie de Chocolate",
                "description": "Brownie casero con chips de chocolate",
                "base_price": Decimal("700.00"),
                "stock_quantity": 40,
                "prep_time_min": 5,
            },
            "cats": [("Postres", True)],
            "ingrs": [],
        },
    ]

    for p in productos:
        product = db.exec(
            select(Product).where(Product.name == p["data"]["name"])
        ).first()
        if not product:
            product = Product(**p["data"])
            db.add(product)
            db.flush()

        _link_categories(db, product, [(cats[c], is_p) for c, is_p in p["cats"]])
        _link_ingredients(db, product, [(ingrs[i], is_r) for i, is_r in p["ingrs"]])

    db.commit()


def seed_roles(db: Session) -> None:
    for rol in ROLES_INICIALES:
        existing = db.get(Rol, rol.code)
        if existing:
            print(f"  [=] Rol ya existe: {rol.code}")
        else:
            db.add(rol)
            print(f"  [+] Rol creado:    {rol.code} — {rol.description}")
    db.commit()


def seed_usuarios(db: Session) -> None:
    for data in USUARIOS_INICIALES:
        existing = db.exec(
            select(User).where(User.username == data["username"])
        ).first()

        if existing:
            print(f"  [=] Ya existe: {data['username']} ({data['rol_code']})")
        else:
            usuario = User(
                username        = data["username"],
                full_name       = data["full_name"],
                email           = data["email"],
                hashed_password = hash_password(data["password"]),
            )
            db.add(usuario)
            db.flush()  # genera el id sin commitear aún
            user_rol = UserRol(id_user=usuario.id, rol_code=data["rol_code"])
            db.add(user_rol)
            print(f"  [+] Creado:    {data['username']} / {data['password']}  (role={data['rol_code']})")
    db.commit()


def run_seed() -> None:
    create_db_and_tables()
    with Session(engine) as db:
        print("\n— Roles —")
        seed_roles(db)  # los roles deben existir ANTES de asignarlos a usuarios

        print("\n— Usuarios —")
        seed_usuarios(db)

        print("\n— Estados de Pedido —")
        seed_estado_pedido(db)

        print("\n— Formas de Pago —")
        seed_formas_pago(db)

        print("\n— Categorías —")
        cats = seed_categories(db)

        print("\n— Ingredientes —")
        ingrs = seed_ingredients(db)

        print("\n— Productos —")
        seed_products(db, cats, ingrs)

    print("\nUsuarios disponibles para pruebas:")
    print("  admin  / Admin1234!   → role=ADMIN")
    print("  juan   / Juan1234!   → role=CLIENT")
    print("  lionel / Lionel1234! → role=STOCK")
    print("  pepe   / Pepe1234!   → role=PEDIDOS")
    print()


if __name__ == "__main__":
    run_seed()
