# app/modules/Productes/repository.py
from decimal import Decimal
from sqlmodel import Session, select, delete
from sqlalchemy import func
from app.core.repository import BaseRepository
from app.modules.product.models import Product
from app.modules.product.models import ProductCategoryLink, ProductIngredientLink


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Product)

    def get_by_id_for_update(self, product_id: int) -> Product | None:
        return self.session.exec(
            select(Product)
            .where(Product.id == product_id, Product.deleted_at.is_(None))
            .with_for_update()
        ).first()

    def get_by_name(self, name: str) -> Product | None:
        # Soft-deleted products free their name for reuse.
        return self.session.exec(
            select(Product).where(
                Product.name == name,
                Product.deleted_at.is_(None),
            )
        ).first()

    def _build_filtered_stmt(
        self,
        *,
        include_deleted: bool = False,
        name: str | None = None,
        category_ids: list[int] | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        ingredient_ids: list[int] | None = None,
        available: bool | None = None,
    ):
        """
        Construye el SELECT con todos los filtros aplicados. Devuelve un statement
        que ya selecciona Product (distinct cuando hay joins N:N para evitar duplicados).
        """
        stmt = select(Product)
        needs_distinct = False

        if not include_deleted:
            stmt = stmt.where(Product.deleted_at.is_(None))

        if name:
            stmt = stmt.where(Product.name.ilike(f"%{name}%"))

        if available is not None:
            stmt = stmt.where(Product.available == available)

        if price_min is not None:
            stmt = stmt.where(Product.base_price >= price_min)

        if price_max is not None:
            stmt = stmt.where(Product.base_price <= price_max)

        if category_ids:
            stmt = stmt.join(
                ProductCategoryLink, ProductCategoryLink.product_id == Product.id
            ).where(ProductCategoryLink.category_id.in_(category_ids))
            needs_distinct = True

        if ingredient_ids:
            # Semántica AND: el producto debe contener TODOS los ingredientes seleccionados.
            stmt = (
                stmt.join(
                    ProductIngredientLink,
                    ProductIngredientLink.product_id == Product.id,
                )
                .where(ProductIngredientLink.ingredient_id.in_(ingredient_ids))
                .group_by(Product.id)
                .having(
                    func.count(func.distinct(ProductIngredientLink.ingredient_id))
                    == len(ingredient_ids)
                )
            )
            needs_distinct = False  # GROUP BY ya colapsa

        if needs_distinct:
            stmt = stmt.distinct()

        return stmt

    def get_all(
        self,
        offset: int = 0,
        limit: int = 20,
        *,
        include_deleted: bool = False,
        name: str | None = None,
        category_ids: list[int] | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        ingredient_ids: list[int] | None = None,
        available: bool | None = None,
    ):
        stmt = self._build_filtered_stmt(
            include_deleted=include_deleted,
            name=name,
            category_ids=category_ids,
            price_min=price_min,
            price_max=price_max,
            ingredient_ids=ingredient_ids,
            available=available,
        )
        return list(self.session.exec(stmt.offset(offset).limit(limit)).all())

    def count(
        self,
        *,
        include_deleted: bool = False,
        name: str | None = None,
        category_ids: list[int] | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        ingredient_ids: list[int] | None = None,
        available: bool | None = None,
    ) -> int:
        stmt = self._build_filtered_stmt(
            include_deleted=include_deleted,
            name=name,
            category_ids=category_ids,
            price_min=price_min,
            price_max=price_max,
            ingredient_ids=ingredient_ids,
            available=available,
        )
        # `len(all())` mantiene consistencia con el resto del repo (sin contar nulls del GROUP BY).
        return len(self.session.exec(stmt).all())

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
