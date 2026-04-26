# app/modules/Productes/repository.py
from sqlmodel import Session, select, delete
from app.core.repository import BaseRepository
from app.modules.product.models import Product
from app.modules.product.models import ProductCategoryLink, ProductIngredientLink


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Product)

    def get_by_name(self, name: str) -> Product | None:
        return self.session.exec(select(Product).where(Product.name == name)).first()

    def get_all(self, offset=0, limit=20):
        return list(
            self.session.exec(select(Product).offset(offset).limit(limit)).all()
        )

    def count(self) -> int:
        return len(self.session.exec(select(Product)).all())

    def get_category_links(self, product_id: int) -> list[ProductCategoryLink]:
        return list(
            self.session.exec(
                select(ProductCategoryLink).where(
                    ProductCategoryLink.product_id == product_id
                )
            ).all()
        )

    def get_category_links_by_product_ids(
        self, product_ids: list[int]
    ) -> list[ProductCategoryLink]:
        if not product_ids:
            return []

        statement = select(ProductCategoryLink).where(
            ProductCategoryLink.product_id.in_(product_ids)
        )

        return list(self.session.exec(statement).all())

    def add_category(
        self, productCategoryLink: ProductCategoryLink
    ) -> ProductCategoryLink:
        self.session.add(productCategoryLink)
        self.session.flush()
        return productCategoryLink

    def remove_category(self, product_id: int, category_id: int) -> None:
        statement = delete(ProductCategoryLink).where(
            ProductCategoryLink.product_id == product_id,
            ProductCategoryLink.category_id == category_id,
        )
        self.session.exec(statement)

    def get_ingredient_links(self, product_id: int) -> list[ProductIngredientLink]:
        return list(
            self.session.exec(
                select(ProductIngredientLink).where(
                    ProductIngredientLink.product_id == product_id
                )
            ).all()
        )

    def get_ingredient_links_by_product_ids(
        self, product_ids: list[int]
    ) -> list[ProductIngredientLink]:
        if not product_ids:
            return []

        statement = select(ProductIngredientLink).where(
            ProductIngredientLink.product_id.in_(product_ids)
        )

        return list(self.session.exec(statement).all())

    def add_ingredient(
        self, productIngredientLink: ProductIngredientLink
    ) -> ProductIngredientLink:
        self.session.add(productIngredientLink)
        self.session.flush()
        return productIngredientLink

    def remove_ingredient(self, product_id: int, ingredient_id: int) -> None:
        statement = delete(ProductIngredientLink).where(
            ProductIngredientLink.product_id == product_id,
            ProductIngredientLink.ingredient_id == ingredient_id,
        )
        self.session.exec(statement)
