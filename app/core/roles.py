"""
Códigos de roles del sistema (RBAC).

Fuente de verdad única para los strings de rol que circulan en el código.
La tabla `roles` en DB usa los mismos códigos en su PK (`code`).

StrEnum: cada miembro ES un string. Esto permite:
    RoleCode.ADMIN == "ADMIN"          → True
    RoleCode.ADMIN in ["ADMIN", ...]   → True
Sin tener que escribir `.value` en cada uso.
"""

from enum import StrEnum


class RoleCode(StrEnum):
    ADMIN = "ADMIN"
    STOCK = "STOCK"
    PEDIDOS = "PEDIDOS"
