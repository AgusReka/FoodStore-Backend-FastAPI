from sqlmodel import Session, select
from app.core.repository import BaseRepository
from app.modules.images.models import Image


class ImageRepository(BaseRepository[Image]):

    def __init__(self, session: Session):
        super().__init__(session, Image)

    def get_all_ordered(self) -> list[Image]:
        return list(
            self.session.exec(
                select(Image).order_by(Image.created_at.desc())
            ).all()
        )

    def get_by_public_id(self, public_id: str) -> Image | None:
        return self.session.exec(
            select(Image).where(Image.public_id == public_id)
        ).first()