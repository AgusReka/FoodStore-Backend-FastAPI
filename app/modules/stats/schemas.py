from decimal import Decimal
from sqlmodel import SQLModel


class DashboardStats(SQLModel):
    # ── Pedidos / Ventas ──────────────────────────────────────────────────
    pedidos_hoy: int
    ganancia_hoy: Decimal
    ticket_promedio_hoy: Decimal
    pedidos_pendientes: int
    pedidos_semana: int

    # ── Catálogo / Stock ──────────────────────────────────────────────────
    productos_activos: int
    productos_bajo_stock: int
    ingredientes_activos: int
    ingredientes_bajo_stock: int
