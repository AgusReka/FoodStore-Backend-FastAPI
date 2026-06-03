import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.core.database import create_db_and_tables, engine
from app.core.security import hash_password
from app.modules.category.models import Category
from app.modules.direcciones.models import DireccionEntrega
from app.modules.ingredient.models import Ingredient
from app.modules.pagos.models import FormaPago
from app.modules.pedidos.models import (
    EstadoPedido,
    Pedido,
    DetallePedido,
    HistorialEstadoPedido,
    TransicionEstado,
)
from app.modules.pedidos.schemas import EstadoPedidoEnum
from app.modules.product.models import (
    Product,
    ProductCategoryLink,
    ProductIngredientLink,
)
from app.modules.user.models import User
from app.modules.user.rol import Rol
from app.modules.user.user_rol import UserRol

# ── Seed de datos para gráficos ──────────────────────────────────────────────
# Productos de referencia para generar pedidos con datos realistas.
# Se cargan por nombre después de que seed_products() los haya creado.
PRODUCTOS_SEED = [
    {"name": "Hamburguesa Clásica", "price": Decimal("1500.00")},
    {"name": "Hamburguesa BBQ Bacon", "price": Decimal("2000.00")},
    {"name": "Hamburguesa Doble", "price": Decimal("2200.00")},
    {"name": "Hamburguesa Picante", "price": Decimal("1900.00")},
    {"name": "Papas Fritas", "price": Decimal("800.00")},
    {"name": "Aros de Cebolla", "price": Decimal("900.00")},
    {"name": "Coca Cola 500ml", "price": Decimal("600.00")},
    {"name": "Agua Mineral 500ml", "price": Decimal("400.00")},
    {"name": "Brownie de Chocolate", "price": Decimal("700.00")},
]

COSTO_ENVIO = Decimal("500.00")

# Semilla fija para que los datos sean reproducibles
random.seed(42)

# Importados para que create_db_and_tables() registre todas las tablas
import app.modules.direcciones.models  # noqa


# ── Datos iniciales — seguridad ───────────────────────────────────────────────

ROLES_INICIALES = [
    Rol(
        code="ADMIN", name="Administrador", description="Acceso total sin restricciones"
    ),
    Rol(code="STOCK", name="Stock", description="Actualiza stock y disponible"),
    Rol(
        code="PEDIDOS",
        name="Pedidos",
        description="Avanza estados CONFIRMADO a ENTREGADO",
    ),
    Rol(
        code="COCINA",
        name="Cocina",
        description="Prepara y marca pedidos listos para entrega",
    ),
    Rol(code="CLIENT", name="Cliente", description="Opera solo sus propios datos"),
]

USUARIOS_INICIALES = [
    {
        "username": "admin",
        "full_name": "Administrador del Sistema",
        "email": "admin@example.com",
        "password": "Admin1234!",
        "rol_code": "ADMIN",
    },
    {
        "username": "juan",
        "full_name": "Juan Pérez",
        "email": "juan@example.com",
        "password": "Juan1234!",
        "rol_code": "CLIENT",
    },
    {
        "username": "lionel",
        "full_name": "Lionel Messi",
        "email": "lionel@example.com",
        "password": "Lionel1234!",
        "rol_code": "STOCK",
    },
    {
        "username": "pepe",
        "full_name": "Pepe Argento",
        "email": "pepe@example.com",
        "password": "Pepe1234!",
        "rol_code": "PEDIDOS",
    },
    {
        "username": "carlos",
        "full_name": "Carlos Cocinero",
        "email": "carlos@example.com",
        "password": "Carlos1234!",
        "rol_code": "COCINA",
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
            "codigo": EstadoPedidoEnum.LISTO,
            "descripcion": "Listo para entrega — preparación finalizada en cocina",
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


def seed_transiciones(db: Session) -> None:
    """Carga las reglas de transición de estado por rol (máquina de estados + RBAC)."""
    # Mapa código -> id resolviendo contra los estados ya sembrados
    estados = {e.codigo: e.id for e in db.exec(select(EstadoPedido)).all()}

    P = EstadoPedidoEnum
    # (rol, origen, destino)
    reglas = [
        # ADMIN: cualquier transición válida de la máquina de estados
        ("ADMIN", P.PENDIENTE, P.CONFIRMADO),
        ("ADMIN", P.PENDIENTE, P.CANCELADO),
        ("ADMIN", P.CONFIRMADO, P.EN_PREP),
        ("ADMIN", P.CONFIRMADO, P.CANCELADO),
        ("ADMIN", P.EN_PREP, P.LISTO),
        ("ADMIN", P.EN_PREP, P.CANCELADO),
        ("ADMIN", P.LISTO, P.ENTREGADO),
        ("ADMIN", P.LISTO, P.CANCELADO),
        # PEDIDOS (cajero): confirma/cancela y entrega cuando está listo
        ("PEDIDOS", P.PENDIENTE, P.CONFIRMADO),
        ("PEDIDOS", P.PENDIENTE, P.CANCELADO),
        ("PEDIDOS", P.LISTO, P.ENTREGADO),
        # COCINA: pasa a preparación y luego marca como listo
        ("COCINA", P.CONFIRMADO, P.EN_PREP),
        ("COCINA", P.CONFIRMADO, P.CANCELADO),
        ("COCINA", P.EN_PREP, P.LISTO),
    ]

    for rol_code, origen, destino in reglas:
        origen_id = estados[origen]
        destino_id = estados[destino]
        existe = db.exec(
            select(TransicionEstado).where(
                TransicionEstado.estado_origen_id == origen_id,
                TransicionEstado.estado_destino_id == destino_id,
                TransicionEstado.rol_code == rol_code,
            )
        ).first()
        if not existe:
            db.add(
                TransicionEstado(
                    estado_origen_id=origen_id,
                    estado_destino_id=destino_id,
                    rol_code=rol_code,
                )
            )
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
            "stock_quantity": 120,
        },
        {
            "name": "Carne vacuna",
            "description": "Medallón de carne 200g",
            "is_allergen": False,
            "stock_quantity": 80,
        },
        {
            "name": "Lechuga",
            "description": "Lechuga fresca",
            "is_allergen": False,
            "stock_quantity": 60,
        },
        {
            "name": "Tomate",
            "description": "Tomate fresco en rodajas",
            "is_allergen": False,
            "stock_quantity": 50,
        },
        {
            "name": "Cebolla",
            "description": "Cebolla morada",
            "is_allergen": False,
            "stock_quantity": 70,
        },
        {
            "name": "Queso cheddar",
            "description": "Queso cheddar fundido",
            "is_allergen": True,
            "stock_quantity": 90,
        },
        {
            "name": "Bacon",
            "description": "Panceta crocante",
            "is_allergen": False,
            "stock_quantity": 40,
        },
        {
            "name": "Mayonesa",
            "description": "Mayonesa casera",
            "is_allergen": True,
            "stock_quantity": 200,
        },
        {
            "name": "Ketchup",
            "description": "Salsa ketchup",
            "is_allergen": False,
            "stock_quantity": 200,
        },
        {
            "name": "Mostaza",
            "description": "Mostaza Dijón",
            "is_allergen": False,
            "stock_quantity": 150,
        },
        {
            "name": "Salsa BBQ",
            "description": "Salsa BBQ ahumada",
            "is_allergen": False,
            "stock_quantity": 100,
        },
        {
            "name": "Jalapeños",
            "description": "Jalapeños encurtidos",
            "is_allergen": False,
            "stock_quantity": 30,
        },
        {
            "name": "Papas",
            "description": "Papa blanca",
            "is_allergen": False,
            "stock_quantity": 250,
        },
        {
            "name": "Huevo",
            "description": "Huevo frito",
            "is_allergen": True,
            "stock_quantity": 8,
        },
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
    db: Session,
    product: Product,
    ingredients: list[tuple[Ingredient, bool, int]],
) -> None:
    """Vincula un producto con sus ingredientes. Tupla: (ingr, is_removable, quantity)."""
    for ingr, is_removable, quantity in ingredients:
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
                    quantity=quantity,
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
                ("Pan brioche", False, 1),
                ("Carne vacuna", False, 1),
                ("Lechuga", True, 1),
                ("Tomate", True, 1),
                ("Cebolla", True, 1),
                ("Mayonesa", True, 1),
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
                ("Pan brioche", False, 1),
                ("Carne vacuna", False, 1),
                ("Queso cheddar", True, 1),
                ("Bacon", True, 2),
                ("Salsa BBQ", True, 1),
                ("Cebolla", True, 1),
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
                ("Pan brioche", False, 1),
                ("Carne vacuna", False, 2),
                ("Queso cheddar", True, 2),
                ("Lechuga", True, 1),
                ("Tomate", True, 1),
                ("Mayonesa", True, 1),
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
                ("Pan brioche", False, 1),
                ("Carne vacuna", False, 1),
                ("Jalapeños", True, 2),
                ("Queso cheddar", True, 1),
                ("Salsa BBQ", True, 1),
                ("Mayonesa", True, 1),
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
            "ingrs": [("Papas", False, 1)],
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
            "ingrs": [("Cebolla", False, 1)],
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
        _link_ingredients(
            db,
            product,
            [(ingrs[i], is_r, qty) for i, is_r, qty in p["ingrs"]],
        )

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
                username=data["username"],
                full_name=data["full_name"],
                email=data["email"],
                hashed_password=hash_password(data["password"]),
            )
            db.add(usuario)
            db.flush()  # genera el id sin commitear aún
            user_rol = UserRol(id_user=usuario.id, rol_code=data["rol_code"])
            db.add(user_rol)
            print(
                f"  [+] Creado:    {data['username']} / {data['password']}  (role={data['rol_code']})"
            )
    db.commit()


# ─────────────────────────────────────────────────────────────────────
# Direcciones de ejemplo para usuarios CLIENT
# ─────────────────────────────────────────────────────────────────────
def seed_direcciones(db: Session) -> dict[int, int]:
    """Crea direcciones de prueba y retorna dict user_id -> direccion_id."""
    clientes = db.exec(
        select(User)
        .join(UserRol, UserRol.id_user == User.id)
        .where(UserRol.rol_code == "CLIENT")
    ).all()

    direcciones_por_usuario: dict[int, int] = {}
    calles = ["Av. Siempre Viva", "San Martín", "Belgrano", "Mitre", "Sarmiento"]
    localidades = ["Buenos Aires", "Córdoba", "Rosario", "Mendoza", "La Plata"]

    for user in clientes:
        existing = db.exec(
            select(DireccionEntrega).where(
                DireccionEntrega.usuario_id == user.id,
                DireccionEntrega.es_principal == True,
            )
        ).first()
        if existing:
            direcciones_por_usuario[user.id] = existing.id
            continue

        calle = random.choice(calles)
        direccion = DireccionEntrega(
            usuario_id=user.id,
            alias="Casa",
            calle=calle,
            numero=str(random.randint(100, 3000)),
            piso_dpto=None,
            ciudad=random.choice(localidades),
            provincia="Buenos Aires",
            codigo_postal=str(random.randint(1000, 9999)),
            es_principal=True,
        )
        db.add(direccion)
        db.flush()
        direcciones_por_usuario[user.id] = direccion.id

    db.commit()
    return direcciones_por_usuario


# ─────────────────────────────────────────────────────────────────────
# Pedidos de prueba con datos variados para los gráficos
# ─────────────────────────────────────────────────────────────────────
def seed_pedidos(
    db: Session,
    direcciones: dict[int, int],
) -> None:
    """Genera ~65 pedidos en los últimos 30 días con estados y totales variados."""

    # Mapeo estado_codigo -> estado_id
    estados: dict[str, int] = {}
    rows = db.exec(select(EstadoPedido)).all()
    for e in rows:
        estados[e.codigo.value] = e.id

    # Productos disponibles (name -> {id, base_price})
    productos: dict[str, dict] = {}
    for p in db.exec(select(Product)).all():
        productos[p.name] = {"id": p.id, "price": p.base_price}

    # Saltar si ya hay pedidos (seed manual con python -m app.core.seed)
    existing = db.exec(select(Pedido.id).limit(1)).first()
    if existing:
        print("  [=] Pedidos ya existen — regeneralos con: python -m app.core.seed")
        return

    now = datetime.now(timezone.utc)
    cliente_ids = list(direcciones.keys())
    if not cliente_ids:
        print("  [!] No hay clientes con dirección — saltando pedidos")
        return

    for dia in range(30, 0, -1):
        # Fecha del pedido
        order_date = now - timedelta(days=dia)
        # Más pedidos en finde, menos entre semana
        is_weekend = order_date.weekday() >= 5
        orders_this_day = (
            random.randint(2, 4) if not is_weekend else random.randint(3, 6)
        )

        for _ in range(orders_this_day):
            user_id = random.choice(cliente_ids)
            direccion_id = direcciones[user_id]

            # Seleccionar 1-3 productos
            picks = random.choices(
                list(productos.values()),
                k=random.randint(1, 3),
            )

            # Asignar cantidades
            detalles_data = []
            subtotal = Decimal("0.00")
            for prod in picks:
                qty = random.randint(1, 3)
                line_total = prod["price"] * qty
                detalles_data.append(
                    {
                        "producto_id": prod["id"],
                        "producto_nombre": [
                            k for k, v in productos.items() if v["id"] == prod["id"]
                        ][0],
                        "producto_precio_unitario": prod["price"],
                        "cantidad": qty,
                        "subtotal": line_total,
                    }
                )
                subtotal += line_total

            costo_envio = COSTO_ENVIO
            total = subtotal + costo_envio

            # Decidir estado según la antigüedad del pedido
            dias_antiguedad = (now - order_date).days

            if dias_antiguedad >= 2:
                # Pedidos viejos: mayormente ENTREGADO, algunos CANCELADO
                estado_codigo = (
                    EstadoPedidoEnum.CANCELADO
                    if random.random() < 0.12
                    else EstadoPedidoEnum.ENTREGADO
                )
            elif dias_antiguedad >= 1:
                # Pedidos de ayer: CONFIRMADO, EN_PREP, LISTO o ya ENTREGADO
                estado_codigo = random.choice(
                    [
                        EstadoPedidoEnum.CONFIRMADO,
                        EstadoPedidoEnum.EN_PREP,
                        EstadoPedidoEnum.LISTO,
                        EstadoPedidoEnum.ENTREGADO,
                    ]
                )
            else:
                # Pedidos de hoy: PENDIENTE o CONFIRMADO
                estado_codigo = random.choice(
                    [
                        EstadoPedidoEnum.PENDIENTE,
                        EstadoPedidoEnum.CONFIRMADO,
                        EstadoPedidoEnum.EN_PREP,
                    ]
                )

            estado_id = estados[estado_codigo.value]

            # Crear el pedido
            pedido = Pedido(
                usuario_id=user_id,
                direccion_entrega_id=direccion_id,
                forma_pago_id=random.randint(1, 4),
                estado_id=estado_id,
                subtotal=subtotal,
                costo_envio=costo_envio,
                total=total,
                notas_cliente=random.choice(
                    [
                        None,
                        None,
                        None,
                        "Sin cebolla por favor",
                        "Bien de sal",
                        "Salsa extra",
                    ]
                ),
                created_at=order_date,
                updated_at=order_date,
            )
            db.add(pedido)
            db.flush()

            # Crear detalles del pedido
            for d in detalles_data:
                detalle = DetallePedido(
                    pedido_id=pedido.id,
                    producto_id=d["producto_id"],
                    producto_nombre=d["producto_nombre"],
                    producto_precio_unitario=d["producto_precio_unitario"],
                    cantidad=d["cantidad"],
                    subtotal=d["subtotal"],
                )
                db.add(detalle)

            # Crear historial de estados
            # Estados en orden de avance (CANCELADO se maneja aparte)
            estados_orden = [
                EstadoPedidoEnum.PENDIENTE,
                EstadoPedidoEnum.CONFIRMADO,
                EstadoPedidoEnum.EN_PREP,
                EstadoPedidoEnum.LISTO,
                EstadoPedidoEnum.ENTREGADO,
            ]

            historial_fechas: list[tuple[EstadoPedidoEnum, datetime]] = []
            if estado_codigo == EstadoPedidoEnum.CANCELADO:
                # Cancelado: avanzó hasta EN_PREP o CONFIRMADO, luego canceló
                ultimo_activo = random.choice(
                    [
                        EstadoPedidoEnum.CONFIRMADO,
                        EstadoPedidoEnum.EN_PREP,
                    ]
                )
                for i, est in enumerate(estados_orden):
                    if est == ultimo_activo or (
                        estados_orden.index(est) < estados_orden.index(ultimo_activo)
                    ):
                        cambio = order_date + timedelta(
                            minutes=random.randint(5, 60 * (i + 1))
                        )
                        historial_fechas.append((est, cambio))
                    else:
                        break
                # Agregar CANCELADO al final
                historial_fechas.append(
                    (
                        EstadoPedidoEnum.CANCELADO,
                        order_date + timedelta(minutes=random.randint(30, 120)),
                    )
                )
            else:
                for i, est in enumerate(estados_orden):
                    if est == estado_codigo or (
                        estados_orden.index(est) < estados_orden.index(estado_codigo)
                    ):
                        cambio = order_date + timedelta(
                            minutes=random.randint(5, 60 * (i + 1))
                        )
                        historial_fechas.append((est, cambio))
                    else:
                        break

            for est, fecha in historial_fechas:
                db.add(
                    HistorialEstadoPedido(
                        pedido_id=pedido.id,
                        estado_id=estados[est.value],
                        usuario_cambio_id=1,  # admin
                        observaciones=None,
                        created_at=fecha,
                    )
                )

    db.commit()
    total_pedidos = db.exec(select(Pedido.id)).all()
    print(f"  [+] {len(total_pedidos)} pedidos generados")


def run_seed() -> None:
    create_db_and_tables()
    with Session(engine) as db:
        print("\n— Roles —")
        seed_roles(db)

        print("\n— Usuarios —")
        seed_usuarios(db)

        print("\n— Estados de Pedido —")
        seed_estado_pedido(db)

        print("\n— Transiciones de Estado —")
        seed_transiciones(db)

        print("\n— Formas de Pago —")
        seed_formas_pago(db)

        print("\n— Categorías —")
        cats = seed_categories(db)

        print("\n— Ingredientes —")
        ingrs = seed_ingredients(db)

        print("\n— Productos —")
        seed_products(db, cats, ingrs)

        print("\n— Direcciones —")
        direcciones = seed_direcciones(db)
        print(f"  [+] {len(direcciones)} direcciones creadas")

        print("\n— Pedidos de prueba —")
        seed_pedidos(db, direcciones)

    print("\nUsuarios disponibles para pruebas:")
    print("  admin  / Admin1234!   -> role=ADMIN")
    print("  juan   / Juan1234!   -> role=CLIENT")
    print("  lionel / Lionel1234! -> role=STOCK")
    print("  pepe   / Pepe1234!   -> role=PEDIDOS")
    print("  carlos / Carlos1234! → role=COCINA")
    print()


if __name__ == "__main__":
    run_seed()
