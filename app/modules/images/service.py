import asyncio
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile
from sqlmodel import Session

from app.core.config import settings
from app.core.exceptions.custom_exceptions import AppError, ResourceNotFoundError
from app.modules.images.models import Image
from app.modules.images.schemas import ImagePublic
from app.modules.images.unit_of_work import ImageUnitOfWork

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
    secure=True,
)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/jpg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class ImageService:

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[ImagePublic]:
        with ImageUnitOfWork(self._session) as uow:
            images = uow.images.get_all_ordered()
            return [ImagePublic.model_validate(img) for img in images]

    def get_by_id(self, image_id: int) -> ImagePublic:
        with ImageUnitOfWork(self._session) as uow:
            image = uow.images.get_by_id(image_id)
            if not image:
                raise ResourceNotFoundError(message="Image not found")
            return ImagePublic.model_validate(image)

    async def upload_many(self, files: list[UploadFile]) -> list[ImagePublic]:
        results: list[ImagePublic] = []
        for file in files:
            if file.content_type not in ALLOWED_TYPES:
                raise AppError(
                    message=f"File '{file.filename}' has unsupported type '{file.content_type}'.",
                    status_code=422,
                    code="unsupported_media_type",
                )
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise AppError(
                    message=f"File '{file.filename}' exceeds the 10 MB limit.",
                    status_code=413,
                    code="file_too_large",
                )
            upload_result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                content,
                folder="foodstore",
                resource_type="image",
            )
            image = Image(
                public_id=upload_result["public_id"],
                url=upload_result["secure_url"],
                filename=file.filename or upload_result["public_id"],
                format=upload_result.get("format"),
                width=upload_result.get("width"),
                height=upload_result.get("height"),
                bytes=upload_result.get("bytes"),
            )
            with ImageUnitOfWork(self._session) as uow:
                saved = uow.images.add(image)
                results.append(ImagePublic.model_validate(saved))
        return results

    def delete(self, image_id: int) -> None:
        with ImageUnitOfWork(self._session) as uow:
            image = uow.images.get_by_id(image_id)
            if not image:
                raise ResourceNotFoundError(message="Image not found")
            cloudinary.uploader.destroy(image.public_id, resource_type="image")
            uow.images.delete(image)