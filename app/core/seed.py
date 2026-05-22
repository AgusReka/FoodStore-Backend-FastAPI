"""
Script de seed — carga usuarios iniciales para pruebas.
Idempotente: se puede ejecutar múltiples veces sin duplicar datos.

Uso:
    python -m app.core.seed

Requiere PostgreSQL corriendo con las variables de .env configuradas.

Crea:
  - admin / Admin1234!  (role=admin)
  - juan / Juan1234!    (role=user)
"""

from app.modules.user.user_rol import UserRol
from sqlmodel import Session, select
from app.core.database import engine, create_db_and_tables
from app.core.security import hash_password
from app.modules.user.models import User
from app.modules.user.rol import Rol


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
        "rol_code": "ADMIN",
    },
    {
        "username":  "juan",
        "full_name": "Juan Pérez",
        "email":     "juan@example.com",
        "password":  "Juan1234!",
        "rol_code": "CLIENT",
    },
    {
        "username":  "lionel",
        "full_name": "Lionel Messi",
        "email":     "lionel@example.com",
        "password":  "Lionel1234!",
        "rol_code": "STOCK",
    },  
    {
        "username":  "pepe",
        "full_name": "Pepe Argento",
        "email":     "pepe@example.com",
        "password":  "Pepe1234!",
        "rol_code": "PEDIDOS",
    },
]


def seed_roles(session: Session) -> None:
    for rol in ROLES_INICIALES:
        existing = session.get(Rol, rol.code)
        if existing:
            print(f"  [=] Rol ya existe: {rol.code}")
        else:
            session.add(rol)
            print(f"  [+] Rol creado:    {rol.code} — {rol.description}")


def seed_usuarios(session: Session) -> None:
    for data in USUARIOS_INICIALES:
        existing = session.exec(
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
                #role            = data["role"],
            )
            session.add(usuario)
            session.flush()  # genera el id sin commitear
            user_rol = UserRol(id_user=usuario.id, rol_code=data["rol_code"])
            session.add(user_rol)
            print(f"  [+] Creado:    {data['username']} / {data['password']}  (role={data['rol_code']})")


def run() -> None:
    print("=== Seed — Seguridad JWT (PostgreSQL) ===")
    create_db_and_tables()

    with Session(engine) as session:
        
        print("\n— Roles —")
        seed_roles(session)
        session.flush()  # los roles deben existir ANTES de asignarlos

        print("\n— Usuarios —")
        seed_usuarios(session)

        session.commit()

    print("\nUsuarios disponibles para pruebas:")
    print("  admin   / Admin1234!   -> role=ADMIN")
    print("  juan    / Juan1234!    -> role=CLIENT")
    print("  lionel  / Lionel1234!  -> role=STOCK")
    print("  pepe    / Pepe1234!    -> role=PEDIDOS")
    print()


if __name__ == "__main__":
    run()