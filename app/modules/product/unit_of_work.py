from sqlmodel import Session
from app.core.unit_of_work import UnitOfWork
from app.modules.product.repository import ProductRepository
from app.modules.category.repository import CategoryRepository
from app.modules.ingredient.repository import IngredientRepository


class ProductUnitOfWork(UnitOfWork):
    """
    Unidad de Trabajo específica para Productos.
    Inicializa los repositorios de productos, categorías e ingredientes.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.products = ProductRepository(session)
        self.categories = CategoryRepository(session)
        self.ingredients = IngredientRepository(session)
    def refresh(self, entity):
        self._session.refresh(entity)
