from typing import Generic, TypeVar, Type, Sequence, Union
from sqlmodel import Session, SQLModel, select

ModelT = TypeVar("ModelT", bound=SQLModel)


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: Session, model: Type[ModelT]) -> None:
        self.session = session
        self.model = model

    def get_by_id(self, record_id: int) -> ModelT | None:
        return self.session.get(self.model, record_id)

    def get(self, record_id: int) -> ModelT | None:
        return self.session.get(self.model, record_id)

    def get_all(self, offset: int = 0, limit: int = 20) -> Sequence[ModelT]:
        return self.session.exec(select(self.model).offset(offset).limit(limit)).all()

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        self.session.flush()
        self.session.refresh(instance)
        return instance

    def create(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        self.session.flush()
        self.session.refresh(instance)
        return instance

    def update(self, record_id: int, instance: ModelT) -> ModelT:
        self.session.add(instance)
        self.session.flush()
        self.session.refresh(instance)
        return instance

    def delete(self, instance_or_id: Union[ModelT, int]) -> None:
        if isinstance(instance_or_id, int):
            instance = self.get(instance_or_id)
            if instance:
                self.session.delete(instance)
        else:
            self.session.delete(instance_or_id)
        self.session.flush()
