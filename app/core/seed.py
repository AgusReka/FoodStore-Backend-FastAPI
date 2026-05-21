from sqlmodel import Session, select

from app.core.database import create_db_and_tables, engine
from app.modules.pagos.models import FormaPago
from app.modules.pedidos.models import EstadoPedido


def seed_estado_pedido(db: Session):
    """Seed obligatorio: Estados del pedido."""
    estados = [
        {"codigo": "PENDIENTE", "descripcion": "Pedido recibido, esperando confirmación", "orden": 1},
        {"codigo": "CONFIRMADO", "descripcion": "Pago confirmado, listo para preparar", "orden": 2},
        {"codigo": "EN_PREP", "descripcion": "En preparación en cocina", "orden": 3},
        {"codigo": "EN_CAMINO", "descripcion": "En camino al cliente", "orden": 4},
        {"codigo": "ENTREGADO", "descripcion": "Entregado exitosamente", "orden": 5},
        {"codigo": "CANCELADO", "descripcion": "Pedido cancelado", "orden": 6},
    ]
    for est in estados:
        if not db.exec(select(EstadoPedido).where(EstadoPedido.codigo == est["codigo"])).first():
            db.add(EstadoPedido(**est))
    db.commit()

def seed_formas_pago(db: Session):
    """Seed obligatorio: Formas de pago."""
    formas = [
        {"nombre": "Efectivo", "descripcion": "Pago en efectivo al recibir", "requiere_monto_pago": True},
        {"nombre": "Tarjeta Débito", "descripcion": "Pago con tarjeta de débito", "requiere_monto_pago": False},
        {"nombre": "Tarjeta Crédito", "descripcion": "Pago con tarjeta de crédito", "requiere_monto_pago": False},
        {"nombre": "Mercado Pago", "descripcion": "Pago mediante plataforma Mercado Pago", "requiere_monto_pago": False},
    ]
    for fp in formas:
        if not db.exec(select(FormaPago).where(FormaPago.nombre == fp["nombre"])).first():
            db.add(FormaPago(**fp))
    db.commit()


def run_seed() -> None:
    create_db_and_tables()
    with Session(engine) as db:
        seed_estado_pedido(db)
        seed_formas_pago(db)


if __name__ == "__main__":
    run_seed()