from sqlmodel import Session
from app.core.unit_of_work import UnitOfWork
from app.modules.category.repository import CategoryRepository
from app.modules.product.repository import ProductRepository
from app.modules.ingredient.repository import IngredientRepository


class ProductUnitOfWork(UnitOfWork):
    def __init__(self, session: Session) -> None:

        super().__init__(session)
        self.product = ProductRepository(session)
        self.category = CategoryRepository(session)
        self.ingredient = IngredientRepository(session)

    def refresh(self, entity):
        self._session.refresh(entity)
