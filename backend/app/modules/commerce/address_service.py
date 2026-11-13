from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.commerce.models import Address
from app.modules.commerce.schemas import AddressIn, AddressUpdate


async def list_addresses(db: AsyncSession, user: User) -> list[Address]:
    """默认地址排在最前，其余按创建时间倒序。"""
    stmt = (
        select(Address)
        .where(Address.user_id == user.id)
        .order_by(Address.is_default.desc(), Address.id.desc())
    )
    return list((await db.scalars(stmt)).all())


async def _get_address(db: AsyncSession, user: User, address_id: int) -> Address:
    address = await db.get(Address, address_id)
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在"
        )
    if address.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该地址"
        )
    return address


async def _clear_default(
    db: AsyncSession, user: User, exclude_id: int | None = None
) -> None:
    stmt = update(Address).where(
        Address.user_id == user.id, Address.is_default.is_(True)
    )
    if exclude_id is not None:
        stmt = stmt.where(Address.id != exclude_id)
    await db.execute(stmt.values(is_default=False))


async def create_address(
    db: AsyncSession, user: User, data: AddressIn
) -> Address:
    """新增地址；首个地址或请求指定时设为默认，并清除旧默认。"""
    count = int(
        await db.scalar(
            select(func.count()).select_from(Address).where(
                Address.user_id == user.id
            )
        )
        or 0
    )
    make_default = data.is_default or count == 0
    if make_default:
        await _clear_default(db, user)

    address = Address(
        user_id=user.id,
        is_default=make_default,
        **data.model_dump(exclude={"is_default"}),
    )
    db.add(address)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="地址创建冲突，请重试"
        ) from exc
    await db.refresh(address)
    return address


async def update_address(
    db: AsyncSession, user: User, address_id: int, data: AddressUpdate
) -> Address:
    address = await _get_address(db, user, address_id)
    payload = data.model_dump(exclude_unset=True, exclude_none=True)
    make_default = payload.pop("is_default", None)

    if make_default is True:
        await _clear_default(db, user, exclude_id=address.id)
        address.is_default = True
    elif make_default is False and address.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少保留一个默认地址",
        )

    for field, value in payload.items():
        setattr(address, field, value)

    await db.commit()
    await db.refresh(address)
    return address


async def delete_address(db: AsyncSession, user: User, address_id: int) -> None:
    """删除地址；若删的是默认地址，自动把剩余最早的一条设为默认。"""
    address = await _get_address(db, user, address_id)
    was_default = address.is_default

    await db.delete(address)
    await db.flush()

    if was_default:
        replacement = await db.scalar(
            select(Address)
            .where(Address.user_id == user.id)
            .order_by(Address.id.asc())
            .limit(1)
        )
        if replacement is not None:
            replacement.is_default = True

    await db.commit()
