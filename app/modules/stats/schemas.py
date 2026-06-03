from datetime import date
from decimal import Decimal
from typing import Optional
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


class TicketEvolutionItem(SQLModel):
    """Ticket promedio por día — para el gráfico de línea."""
    date: date
    avg_ticket: Decimal


class OrdersByStatus(SQLModel):
    """Cantidad de pedidos agrupados por estado actual."""
    pendiente: int
    confirmado: int
    en_preparacion: int
    listo: int
    entregado: int
    cancelado: int


class OrdersByDayItem(SQLModel):
    """Cantidad de pedidos por día — para el gráfico de barras semanal."""
    date: date
    day_name: str
    count: int
