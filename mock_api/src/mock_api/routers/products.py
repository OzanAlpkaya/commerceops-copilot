from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from mock_api.db import SessionDep
from mock_api.errors import not_found
from mock_api.models import Product
from mock_api.pagination import DEFAULT_LIMIT, CursorParam, Keyset, LimitParam, paginate
from mock_api.schemas import Page, ProductOut
from mock_api.security import rate_limited_client

router = APIRouter(
    prefix="/products", tags=["products"], dependencies=[Depends(rate_limited_client)]
)

KEYSET = Keyset((Product.sku,), ("str",))


@router.get("/{sku}")
def get_product(sku: str, session: SessionDep) -> ProductOut:
    product = session.get(Product, sku)
    if product is None:
        raise not_found("product", sku)
    return ProductOut.model_validate(product)


@router.get("")
def list_products(
    session: SessionDep,
    supplier_id: Annotated[str | None, Query(max_length=16)] = None,
    limit: LimitParam = DEFAULT_LIMIT,
    cursor: CursorParam = None,
) -> Page[ProductOut]:
    stmt = select(Product)
    if supplier_id is not None:
        stmt = stmt.where(Product.supplier_id == supplier_id)
    rows, next_cursor = paginate(session, stmt, KEYSET, limit, cursor)
    return Page(data=[ProductOut.model_validate(p) for p in rows], next_cursor=next_cursor)
