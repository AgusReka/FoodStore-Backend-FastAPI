# app/modules/product/service.py
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlmodel import Session

from app.modules.category.models import Category
from app.modules.ingredient.models import Ingredient
from app.modules.product.models import Product
from app.modules.product.schemas import (
    ProductCreate,
    ProductPublic,
    ProductUpdate,
    ProductList,
)
from app.modules.product.unit_of_work import ProductUnitOfWork
from datetime import datetime, timezone

from app.modules.product.models import ProductCategoryLink, ProductIngredientLink
from app.modules.product.schemas import (
    ProductCategoryInput,
    ProductCategoryPublic,
    ProductIngredientInput,
    ProductIngredientPublic,
)


class ProductService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Helpers privados ──────────────────────────────────────────────────────

    def _get_or_404(self, uow: ProductUnitOfWork, product_id: int) -> Product:
        product = uow.products.get_by_id(product_id)
        if not product:
            raise ValueError(f"Product con id={product_id} no encontrado")
        return product

    def _assert_name_unique(self, uow: ProductUnitOfWork, name: str) -> None:
        if uow.products.get_by_name(name):
            raise ValueError(f"El name '{name}' ya está en uso")

    def _validate_and_get_categories(
        self,
        uow: ProductUnitOfWork,
        categories: list[ProductCategoryInput],
    ):
        if not categories:
            raise ValueError("El producto debe tener al menos una categoría")

        # duplicados
        ids = [c.id for c in categories]
        if len(set(ids)) != len(ids):
            raise ValueError("No se permiten categorías duplicadas")

        # primaria
        primary_count = sum(1 for c in categories if c.is_primary)
        if primary_count == 0:
            raise ValueError("Debe haber una categoría primaria")
        if primary_count > 1:
            raise ValueError("Solo puede haber una categoría primaria")

        # traer de DB
        db_categories = uow.categories.get_all_in(ids)
        db_map = {c.id: c for c in db_categories}

        missing = set(ids) - db_map.keys()
        if missing:
            raise ValueError(f"Categorías no encontradas: {list(missing)}")

        return db_map

    def _validate_and_get_ingredients(
        self,
        uow: ProductUnitOfWork,
        ingredients: list[ProductIngredientInput],
    ):
        if not ingredients:
            return

        # duplicados
        ids = [ing.id for ing in ingredients]
        if len(set(ids)) != len(ids):
            raise ValueError("No se permiten ingredientes duplicados")

        # traer de DB
        db_ingredients = uow.ingredients.get_all_in(ids)
        db_map = {ing.id: ing for ing in db_ingredients}

        missing = set(ids) - db_map.keys()
        if missing:
            raise ValueError(f"Ingredientes no encontrados: {list(missing)}")

        return db_map

    # ── Helpers de stock ──────────────────────────────────────────────────────

    @staticmethod
    def _compute_available_stock(
        ingredient_map: dict[int, Ingredient],
        ingredient_items: list[tuple[int, int]],
        stock_quantity: int = 0,
    ) -> int:
        """
        Calcula el stock disponible de un producto.

        Para productos con receta: MIN(ingrediente.stock_quantity / cantidad_necesaria)
        Para productos sin receta (standalone): stock_quantity físico.

        Args:
            ingredient_map: dict[id_ingrediente -> Ingredient]
            ingredient_items: lista de tuplas (ingredient_id, quantity)
            stock_quantity: stock físico del producto (usado si no tiene receta)

        Returns:
            int: stock disponible
        """
        if not ingredient_items:
            return stock_quantity

        try:
            return min(
                ingredient_map[ing_id].stock_quantity // qty
                for ing_id, qty in ingredient_items
                if ing_id in ingredient_map and qty > 0
            )
        except (ValueError, ZeroDivisionError):
            return 0

    # ── Casos de uso ─────────────────────────────────────────────────────────

    def create(self, data: ProductCreate) -> ProductPublic:
        uow: ProductUnitOfWork
        with ProductUnitOfWork(self._session) as uow:
            # 🔒 validaciones
            self._assert_name_unique(uow, data.name)
            category_map = self._validate_and_get_categories(uow, data.categories)
            ingredient_map = self._validate_and_get_ingredients(uow, data.ingredients)

            # 🧱 crear producto
            product = Product(
                name=data.name,
                description=data.description,
                base_price=data.base_price,
                stock_quantity=data.stock_quantity,
                image_urls=data.image_urls,
                prep_time_min=data.prep_time_min,
                available=data.available,
            )

            uow.products.add(product)

            # 🔗 crear relaciones - categorías
            for cat in data.categories:
                uow.products.add_category(
                    ProductCategoryLink(
                        product_id=product.id,
                        category_id=cat.id,
                        is_primary=cat.is_primary,
                    )
                )

            # 🔗 crear relaciones - ingredientes
            # Guardamos la receta del producto: qué ingredientes usa y en qué cantidad
            for ing in data.ingredients:
                uow.products.add_ingredient(
                    ProductIngredientLink(
                        product_id=product.id,
                        ingredient_id=ing.id,
                        is_removable=ing.is_removable,
                        quantity=ing.quantity,
                    )
                )

            # 📊 stock fabricable (si tiene receta, se calcula desde ingredientes)
            available_stock = self._compute_available_stock(
                ingredient_map,
                [(ing.id, ing.quantity) for ing in data.ingredients],
                stock_quantity=data.stock_quantity,
            )

            # 🎯 armar response
            result = ProductPublic(
                id=product.id,
                name=product.name,
                description=product.description,
                base_price=product.base_price,
                stock_quantity=product.stock_quantity,
                available_stock=available_stock,
                image_urls=product.image_urls,
                prep_time_min=product.prep_time_min,
                available=product.available,
                created_at=product.created_at,
                updated_at=product.updated_at,
                deleted_at=product.deleted_at,
                categories=[
                    ProductCategoryPublic(
                        id=cat.id,
                        name=category_map[cat.id].name,
                        is_primary=cat.is_primary,
                    )
                    for cat in data.categories
                ],
                ingredients=[
                    ProductIngredientPublic(
                        id=ing.id,
                        name=ingredient_map[ing.id].name,
                        is_removable=ing.is_removable,
                        quantity=ing.quantity,
                        is_allergen=ingredient_map[ing.id].is_allergen,
                    )
                    for ing in data.ingredients
                ],
            )

            return result

    def update(self, product_id: int, data: ProductUpdate) -> ProductPublic:
        uow: ProductUnitOfWork
        with ProductUnitOfWork(self._session) as uow:
            # 🔎 buscar producto
            product = uow.products.get_by_id(product_id)
            if not product:
                raise ValueError("Producto no encontrado")

            # 🧠 convertir solo lo que vino
            update_data = data.model_dump(exclude_unset=True)

            # 🔒 validar nombre si viene y cambia
            if "name" in update_data and update_data["name"] != product.name:
                self._assert_name_unique(uow, update_data["name"])

            # 🧱 actualizar campos simples
            for field, value in update_data.items():
                if field not in ["categories", "ingredients"]:
                    setattr(product, field, value)

            # 🔥 categorías (solo si vienen)
            if "categories" in update_data:
                categories = data.categories

                # validar + traer categorías
                category_map = self._validate_and_get_categories(uow, categories)

                # actuales
                current_links = uow.products.get_category_links(product.id)
                current_map = {l.category_id: l for l in current_links}

                # nuevas
                new_map = {c.id: c for c in categories}

                current_ids = set(current_map.keys())
                new_ids = set(new_map.keys())

                # 🗑️ eliminar
                for cat_id in current_ids - new_ids:
                    uow.products.remove_category(product.id, cat_id)

                # ➕ agregar
                for cat_id in new_ids - current_ids:
                    cat = new_map[cat_id]
                    uow.products.add_category(
                        ProductCategoryLink(
                            product_id=product.id,
                            category_id=cat.id,
                            is_primary=cat.is_primary,
                        )
                    )

                # 🔄 actualizar
                for cat_id in current_ids & new_ids:
                    link = current_map[cat_id]
                    new_cat = new_map[cat_id]

                    if link.is_primary != new_cat.is_primary:
                        link.is_primary = new_cat.is_primary

            else:
                # si no vienen categorías, armamos el map desde DB para response
                current_links = uow.products.get_category_links(product.id)
                category_ids = [l.category_id for l in current_links]
                db_categories = uow.categories.get_all_in(category_ids)
                category_map = {c.id: c for c in db_categories}

                categories = [
                    ProductCategoryInput(id=l.category_id, is_primary=l.is_primary)
                    for l in current_links
                ]

            # 🥘 ingredientes (solo si vienen)
            if "ingredients" in update_data:
                ingredients = data.ingredients

                # validar + traer ingredientes
                ingredient_map = self._validate_and_get_ingredients(uow, ingredients)

                # actuales
                current_ing_links = uow.products.get_ingredient_links(product.id)
                current_ing_map = {l.ingredient_id: l for l in current_ing_links}

                # nuevos
                new_ing_map = {ing.id: ing for ing in ingredients}

                current_ing_ids = set(current_ing_map.keys())
                new_ing_ids = set(new_ing_map.keys())

                # 🗑️ eliminar
                for ing_id in current_ing_ids - new_ing_ids:
                    uow.products.remove_ingredient(product.id, ing_id)

                # ➕ agregar
                for ing_id in new_ing_ids - current_ing_ids:
                    ing = new_ing_map[ing_id]
                    uow.products.add_ingredient(
                        ProductIngredientLink(
                            product_id=product.id,
                            ingredient_id=ing.id,
                            is_removable=ing.is_removable,
                            quantity=ing.quantity,
                        )
                    )

                # 🔄 actualizar existentes: también actualizamos la cantidad usada en la receta
                for ing_id in current_ing_ids & new_ing_ids:
                    link = current_ing_map[ing_id]
                    new_ing = new_ing_map[ing_id]

                    if link.is_removable != new_ing.is_removable:
                        link.is_removable = new_ing.is_removable
                    if link.quantity != new_ing.quantity:
                        link.quantity = new_ing.quantity

            else:
                # si no vienen ingredientes, armamos el map desde DB para response
                current_ing_links = uow.products.get_ingredient_links(product.id)
                ingredient_ids = [l.ingredient_id for l in current_ing_links]
                db_ingredients = uow.ingredients.get_all_in(ingredient_ids)
                ingredient_map = {ing.id: ing for ing in db_ingredients}

                ingredients = [
                    ProductIngredientInput(
                        id=l.ingredient_id,
                        is_removable=l.is_removable,
                        quantity=l.quantity,
                    )
                    for l in current_ing_links
                ]

            # 📊 stock fabricable (si tiene receta, se calcula desde ingredientes)
            available_stock = self._compute_available_stock(
                ingredient_map,
                [(ing.id, ing.quantity) for ing in ingredients],
                stock_quantity=product.stock_quantity,
            )

            # 🕒 updated_at
            product.updated_at = datetime.now(timezone.utc)

            # 🎯 response
            result = ProductPublic(
                id=product.id,
                name=product.name,
                description=product.description,
                base_price=product.base_price,
                stock_quantity=product.stock_quantity,
                available_stock=available_stock,
                image_urls=product.image_urls,
                prep_time_min=product.prep_time_min,
                available=product.available,
                created_at=product.created_at,
                updated_at=product.updated_at,
                deleted_at=product.deleted_at,
                categories=[
                    ProductCategoryPublic(
                        id=cat.id,
                        name=category_map[cat.id].name,
                        is_primary=cat.is_primary,
                    )
                    for cat in categories
                ],
                ingredients=[
                    ProductIngredientPublic(
                        id=ing.id,
                        name=ingredient_map[ing.id].name,
                        is_allergen=ingredient_map[ing.id].is_allergen,
                        is_removable=ing.is_removable,
                        quantity=ing.quantity,
                    )
                    for ing in ingredients
                ],
            )

            return result

    def get_all(
        self,
        offset: int = 0,
        limit: int = 20,
        *,
        include_deleted: bool = False,
        name: str | None = None,
        category_id: int | None = None,
        cascade: bool = True,
        price_min=None,
        price_max=None,
        ingredient_ids: list[int] | None = None,
        available: bool | None = None,
    ) -> ProductList:
        uow: ProductUnitOfWork
        with ProductUnitOfWork(self._session) as uow:
            # Resolver cascada de categoría → lista plana de IDs
            category_ids: list[int] | None = None
            if category_id is not None:
                if cascade:
                    category_ids = uow.categories.get_descendant_ids(
                        category_id, include_self=True
                    )
                else:
                    category_ids = [category_id]

            # Validación cruzada de precio
            if price_min is not None and price_max is not None and price_min > price_max:
                raise ValueError("price_min no puede ser mayor que price_max")

            # Validar que los ingredientes existan (si vinieron)
            if ingredient_ids:
                found = uow.ingredients.get_all_in(ingredient_ids)
                missing = set(ingredient_ids) - {ing.id for ing in found}
                if missing:
                    raise ValueError(f"Ingredientes no encontrados: {sorted(missing)}")

            products = uow.products.get_all(
                offset,
                limit,
                include_deleted=include_deleted,
                name=name,
                category_ids=category_ids,
                price_min=price_min,
                price_max=price_max,
                ingredient_ids=ingredient_ids,
                available=available,
            )
            total = uow.products.count(
                include_deleted=include_deleted,
                name=name,
                category_ids=category_ids,
                price_min=price_min,
                price_max=price_max,
                ingredient_ids=ingredient_ids,
                available=available,
            )

            product_ids = [p.id for p in products]

            # 🔗 traer links (N:N) - categorías
            category_links = uow.products.get_category_links_by_product_ids(product_ids)
            # 🔗 traer links (N:N) - ingredientes
            ingredient_links = uow.products.get_ingredient_links_by_product_ids(
                product_ids
            )

            # 📦 agrupar links por producto - categorías
            category_links_by_product: dict[int, list[ProductCategoryLink]] = {}
            for link in category_links:
                category_links_by_product.setdefault(link.product_id, []).append(link)

            # 📦 agrupar links por producto - ingredientes
            ingredient_links_by_product: dict[int, list[ProductIngredientLink]] = {}
            for link in ingredient_links:
                ingredient_links_by_product.setdefault(link.product_id, []).append(link)

            # 📚 traer categorías
            category_ids = list({l.category_id for l in category_links})
            db_categories = uow.categories.get_all_in(category_ids)
            category_map = {c.id: c for c in db_categories}

            # 📚 traer ingredientes
            ingredient_ids = list({l.ingredient_id for l in ingredient_links})
            db_ingredients = uow.ingredients.get_all_in(ingredient_ids)
            ingredient_map = {ing.id: ing for ing in db_ingredients}

            # 🎯 armar respuesta
            data = []
            for product in products:
                product_category_links = category_links_by_product.get(product.id, [])
                product_ingredient_links = ingredient_links_by_product.get(
                    product.id, []
                )

                categories = [
                    ProductCategoryPublic(
                        id=link.category_id,
                        name=category_map[link.category_id].name,
                        is_primary=link.is_primary,
                    )
                    for link in product_category_links
                ]

                ingredients = [
                    ProductIngredientPublic(
                        id=link.ingredient_id,
                        name=ingredient_map[link.ingredient_id].name,
                        is_allergen=ingredient_map[link.ingredient_id].is_allergen,
                        is_removable=link.is_removable,
                        quantity=link.quantity,
                    )
                    for link in product_ingredient_links
                ]

                # 📊 stock fabricable
                available_stock = self._compute_available_stock(
                    ingredient_map,
                    [(link.ingredient_id, link.quantity) for link in product_ingredient_links],
                    stock_quantity=product.stock_quantity,
                )

                data.append(
                    ProductPublic(
                        id=product.id,
                        name=product.name,
                        description=product.description,
                        base_price=product.base_price,
                        stock_quantity=product.stock_quantity,
                        available_stock=available_stock,
                        image_urls=product.image_urls,
                        prep_time_min=product.prep_time_min,
                        available=product.available,
                        created_at=product.created_at,
                        updated_at=product.updated_at,
                        deleted_at=product.deleted_at,
                        categories=categories,
                        ingredients=ingredients,
                    )
                )

            return ProductList(data=data, total=total)

    def get_by_id(self, product_id: int) -> ProductPublic:
        uow: ProductUnitOfWork
        with ProductUnitOfWork(self._session) as uow:
            # 🔎 buscar producto
            product = self._get_or_404(uow, product_id)

            # 🔗 traer links - categorías
            category_links = uow.products.get_category_links_by_product_ids([product.id])
            # 🔗 traer links - ingredientes
            ingredient_links = uow.products.get_ingredient_links_by_product_ids(
                [product.id]
            )

            # 📚 traer categorías
            category_ids = [l.category_id for l in category_links]
            db_categories = uow.categories.get_all_in(category_ids)
            category_map = {c.id: c for c in db_categories}

            # 📚 traer ingredientes
            ingredient_ids = [l.ingredient_id for l in ingredient_links]
            db_ingredients = uow.ingredients.get_all_in(ingredient_ids)
            ingredient_map = {ing.id: ing for ing in db_ingredients}

            # 🎯 armar categorías
            categories = [
                ProductCategoryPublic(
                    id=link.category_id,
                    name=category_map[link.category_id].name,
                    is_primary=link.is_primary,
                )
                for link in category_links
            ]

            # 🎯 armar ingredientes
            ingredients = [
                ProductIngredientPublic(
                    id=link.ingredient_id,
                    name=ingredient_map[link.ingredient_id].name,
                    is_allergen=ingredient_map[link.ingredient_id].is_allergen,
                    is_removable=link.is_removable,
                    quantity=link.quantity,
                )
                for link in ingredient_links
            ]

            # 📊 stock fabricable
            available_stock = self._compute_available_stock(
                ingredient_map,
                [(link.ingredient_id, link.quantity) for link in ingredient_links],
                stock_quantity=product.stock_quantity,
            )

            # 🎯 response
            result = ProductPublic(
                id=product.id,
                name=product.name,
                description=product.description,
                base_price=product.base_price,
                stock_quantity=product.stock_quantity,
                available_stock=available_stock,
                image_urls=product.image_urls,
                prep_time_min=product.prep_time_min,
                available=product.available,
                created_at=product.created_at,
                updated_at=product.updated_at,
                deleted_at=product.deleted_at,
                categories=categories,
                ingredients=ingredients,
            )

            return result

    def soft_delete(self, product_id: int) -> None:
        # Definitivo: marca deleted_at. No toca `available` (concepto separado).
        with ProductUnitOfWork(self._session) as uow:
            product = self._get_or_404(uow, product_id)
            if product.deleted_at is not None:
                raise ValueError("El producto ya está eliminado")
            product.deleted_at = datetime.now(timezone.utc)

    def set_availability(self, product_id: int, available: bool) -> None:
        # Pausar/reanudar venta sin afectar el soft delete.
        with ProductUnitOfWork(self._session) as uow:
            product = self._get_or_404(uow, product_id)
            if product.deleted_at is not None:
                raise ValueError(
                    "No se puede cambiar la disponibilidad de un producto eliminado"
                )
            product.available = available
            product.updated_at = datetime.now(timezone.utc)
