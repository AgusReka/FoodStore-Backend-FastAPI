from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel


class ImagePublic(SQLModel):
    id: int
    public_id: str
    url: str
    filename: str
    format: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    bytes: Optional[int] = None
    created_at: datetime