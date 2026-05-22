from sqlmodel import SQLModel, Field
from typing import Optional

class Rol(SQLModel, table=True):
    __tablename__ = "roles"

    code:      str           = Field(primary_key=True, max_length=20)
    name:      str           = Field(unique=True, max_length=50)
    description: Optional[str] = Field(default=None)