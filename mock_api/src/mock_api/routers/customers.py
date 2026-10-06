from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from mock_api.db import SessionDep
from mock_api.errors import not_found
from mock_api.models import Customer
from mock_api.pagination import DEFAULT_LIMIT, CursorParam, Keyset, LimitParam, paginate
from mock_api.schemas import CustomerOut, Page
from mock_api.security import rate_limited_client

router = APIRouter(
    prefix="/customers", tags=["customers"], dependencies=[Depends(rate_limited_client)]
)

KEYSET = Keyset((Customer.id,), ("str",))


@router.get("/{customer_id}")
def get_customer(customer_id: str, session: SessionDep) -> CustomerOut:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise not_found("customer", customer_id)
    return CustomerOut.model_validate(customer)


@router.get("")
def list_customers(
    session: SessionDep,
    email: Annotated[str | None, Query(max_length=254)] = None,
    limit: LimitParam = DEFAULT_LIMIT,
    cursor: CursorParam = None,
) -> Page[CustomerOut]:
    stmt = select(Customer)
    if email is not None:
        stmt = stmt.where(func.lower(Customer.email) == email.strip().lower())
    rows, next_cursor = paginate(session, stmt, KEYSET, limit, cursor)
    return Page(data=[CustomerOut.model_validate(c) for c in rows], next_cursor=next_cursor)
