"""服务层，封装用户/组的聚合查询与修改行为。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from passlib.context import CryptContext

from hybrid_agent.core.database import (
    GroupModel,
    UserGroupModel,
    UserModel,
    db_manager,
)


@dataclass
class GroupMemberInfo:
    user_id: str
    username: str | None
    role: str


@dataclass
class UserGroupInfo:
    group_id: str
    group_name: str | None
    role: str


class AdminService:
    def __init__(self) -> None:
        self._db_manager = db_manager
        self._pwd_context = CryptContext(
            schemes=["pbkdf2_sha256", "bcrypt"],
            deprecated="auto",
        )

    def permission_denied(self, detail: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    def _session(self):
        if not self._db_manager or not self._db_manager.SessionLocal:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database unavailable",
            )
        return self._db_manager.SessionLocal()

    def list_users(self) -> list[dict]:
        with self._db_manager._get_session() as session:
            users = session.query(UserModel).order_by(UserModel.username).all()
            result: list[dict] = []
            for user in users:
                groups = self._load_user_groups(session, str(user.id))
                result.append({
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_active": bool(user.is_active),
                    "groups": [g.__dict__ for g in groups],
                })
            return result

    def create_user(
        self,
        username: str,
        password: str,
        email: str | None = None,
        role: str = "member",
        is_active: bool = True,
    ) -> dict:
        with self._db_manager._get_session() as session:
            existing = session.query(UserModel).filter(UserModel.username == username).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User {username} already exists",
                )

            user = UserModel(
                id=str(uuid4()),
                username=username,
                email=email,
                hashed_password=self._pwd_context.hash(password),
                role=role,
                is_active=is_active,
            )
            session.add(user)
            session.flush()
            return {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_active": bool(user.is_active),
                "groups": [],
            }

    def list_groups(self) -> list[dict]:
        with self._db_manager._get_session() as session:
            groups = session.query(GroupModel).order_by(GroupModel.name).all()
            result: list[dict] = []
            for group in groups:
                members = self._load_group_members(session, str(group.id))
                result.append({
                    "id": str(group.id),
                    "name": group.name,
                    "description": group.description,
                    "members": [m.__dict__ for m in members],
                })
            return result

    def create_group(self, name: str, description: str | None = None) -> dict:
        with self._db_manager._get_session() as session:
            existing = session.query(GroupModel).filter(GroupModel.name == name).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Group {name} already exists",
                )
            group = GroupModel(id=str(uuid4()), name=name, description=description)
            session.add(group)
            session.flush()
            return {
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "members": [],
            }

    def add_member(self, group_id: str, user_id: str, role: str) -> None:
        with self._db_manager._get_session() as session:
            group = session.query(GroupModel).filter(GroupModel.id == group_id).first()
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Group not found",
                )
            user = session.query(UserModel).filter(UserModel.id == user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            membership = (
                session.query(UserGroupModel)
                .filter(
                    UserGroupModel.group_id == group_id,
                    UserGroupModel.user_id == user_id,
                )
                .first()
            )
            if membership:
                membership.role = role
                return
            session.add(UserGroupModel(user_id=user_id, group_id=group_id, role=role))

    def remove_member(self, group_id: str, user_id: str) -> None:
        with self._db_manager._get_session() as session:
            membership = (
                session.query(UserGroupModel)
                .filter(
                    UserGroupModel.group_id == group_id,
                    UserGroupModel.user_id == user_id,
                )
                .first()
            )
            if not membership:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Membership not found",
                )
            session.delete(membership)

    def _load_user_groups(self, session: Any, user_id: str) -> list[UserGroupInfo]:
        rows = (
            session.query(UserGroupModel, GroupModel.name)
            .join(GroupModel, GroupModel.id == UserGroupModel.group_id, isouter=True)
            .filter(UserGroupModel.user_id == user_id)
            .all()
        )
        result: list[UserGroupInfo] = []
        for membership, group_name in rows:
            result.append(
                UserGroupInfo(
                    group_id=membership.group_id,
                    group_name=group_name,
                    role=membership.role,
                )
            )
        return result

    def _load_group_members(self, session: Any, group_id: str) -> list[GroupMemberInfo]:
        rows = (
            session.query(UserGroupModel, UserModel.username)
            .join(UserModel, UserModel.id == UserGroupModel.user_id, isouter=True)
            .filter(UserGroupModel.group_id == group_id)
            .all()
        )
        result: list[GroupMemberInfo] = []
        for membership, username in rows:
            result.append(
                GroupMemberInfo(
                    user_id=membership.user_id,
                    username=username,
                    role=membership.role,
                )
            )
        return result


admin_service = AdminService()
