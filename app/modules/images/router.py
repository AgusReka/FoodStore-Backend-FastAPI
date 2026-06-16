from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, File
from sqlmodel import Session

from app.core.database import get_session
from app.core.deps import require_admin
from app.modules.images.schemas import ImagePublic
from app.modules.images.service import ImageService
from app.modules.user.models import User

router = APIRouter()


def get_image_service(session: Session = Depends(get_session)) -> ImageService:
    return ImageService(session)


@router.get("", response_model=list[ImagePublic])
def list_images(svc: ImageService = Depends(get_image_service)):
    return svc.list_all()


@router.get("/{image_id}", response_model=ImagePublic)
def get_image(image_id: int, svc: ImageService = Depends(get_image_service)):
    return svc.get_by_id(image_id)


@router.post("/upload", response_model=list[ImagePublic], status_code=201)
async def upload_images(
    _: Annotated[User, Depends(require_admin)],
    files: list[UploadFile] = File(...),
    svc: ImageService = Depends(get_image_service),
):
    return await svc.upload_many(files)


@router.delete("/{image_id}", status_code=204)
def delete_image(
    image_id: int,
    _: Annotated[User, Depends(require_admin)],
    svc: ImageService = Depends(get_image_service),
):
    svc.delete(image_id)