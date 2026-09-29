from __future__ import annotations

import re
import socket
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from fileseek.features.settings.application.commands import (
    CreateStorageLocationCommand,
    DeleteStorageLocationCommand,
    TestStorageConnectionCommand,
    UpdateStorageLocationCommand,
)
from fileseek.features.settings.application.dto import (
    ConnectionTestResultDTO,
    StorageLocationDeletionDTO,
    StorageLocationDTO,
)
from fileseek.features.settings.application.mappers import storage_location_to_dto
from fileseek.features.settings.application.queries import ListStorageLocationsQuery
from fileseek.features.settings.domain.entities import StorageLocation, StorageProtocol
from fileseek.features.settings.domain.exceptions import StorageConnectionError
from fileseek.features.settings.domain.repositories import StorageLocationRepository
from fileseek.shared.domain.exceptions import NotFoundError, ValidationError
from fileseek.shared.domain.identifiers import generate_id

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_PROTOCOLS = {"file", "mounted", "smb", "nfs", "webdav"}
_DEFAULT_PORTS = {"smb": 445, "nfs": 2049, "webdav": 443}


class ListStorageLocationsUseCase:
    def __init__(self, repository: StorageLocationRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        query: ListStorageLocationsQuery,
    ) -> list[StorageLocationDTO]:
        _ = query
        locations = await self.repository.list_active_manageable()
        return [storage_location_to_dto(location) for location in locations]


class CreateStorageLocationUseCase:
    def __init__(self, repository: StorageLocationRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        command: CreateStorageLocationCommand,
    ) -> StorageLocationDTO:
        location_id = command.id or generate_id("storage")
        if not _ID_PATTERN.fullmatch(location_id):
            raise ValidationError("存储标识只能包含小写字母、数字、下划线和连字符")
        if await self.repository.get_by_id(location_id, include_deleted=True):
            raise ValidationError(f"存储标识已存在: {location_id}")

        name = command.name.strip()
        protocol = command.protocol.strip().lower()
        validated_protocol = cast(StorageProtocol, protocol)
        endpoint = command.endpoint.strip()
        root_path = command.root_path.strip()
        if not name:
            raise ValidationError("存储名称不能为空")
        if protocol not in _PROTOCOLS:
            raise ValidationError(f"不支持的存储协议: {command.protocol}")
        if not endpoint:
            raise ValidationError("存储地址不能为空")
        if protocol == "mounted" and not root_path:
            root_path = endpoint

        location = await self.repository.save(
            StorageLocation(
                id=location_id,
                type="nas",
                name=name,
                protocol=validated_protocol,
                endpoint=endpoint,
                root_path=root_path,
                account=command.account,
                password=command.password,
            )
        )
        return storage_location_to_dto(location)


class UpdateStorageLocationUseCase:
    def __init__(self, repository: StorageLocationRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        command: UpdateStorageLocationCommand,
    ) -> StorageLocationDTO:
        current = await self.repository.get_by_id(
            command.location_id,
            include_deleted=True,
        )
        if current is None:
            raise NotFoundError(f"存储位置不存在: {command.location_id}")
        if current.is_system:
            raise ValidationError("系统存储位置不能修改")

        name = command.name.strip()
        protocol = command.protocol.strip().lower()
        validated_protocol = cast(StorageProtocol, protocol)
        endpoint = command.endpoint.strip()
        root_path = command.root_path.strip()
        if not name:
            raise ValidationError("存储名称不能为空")
        if protocol not in _PROTOCOLS:
            raise ValidationError(f"不支持的存储协议: {command.protocol}")
        if not endpoint:
            raise ValidationError("存储地址不能为空")
        if protocol == "mounted" and not root_path:
            root_path = endpoint

        location = await self.repository.save(
            StorageLocation(
                id=current.id,
                type=current.type,
                name=name,
                protocol=validated_protocol,
                endpoint=endpoint,
                root_path=root_path,
                account=command.account,
                password=command.password if command.password is not None else current.password,
                status=current.status,
                is_system=current.is_system,
            )
        )
        return storage_location_to_dto(location)


class DeleteStorageLocationUseCase:
    def __init__(self, repository: StorageLocationRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        command: DeleteStorageLocationCommand,
    ) -> StorageLocationDeletionDTO:
        location = await self.repository.get_by_id(
            command.location_id,
            include_deleted=True,
        )
        if location is None:
            raise NotFoundError(f"存储位置不存在: {command.location_id}")
        if location.is_system:
            raise ValidationError("系统存储位置不能删除")

        deleted = await self.repository.mark_deleted(location.id)
        if not deleted:
            raise ValidationError(f"存储位置已删除: {location.id}")

        return StorageLocationDeletionDTO(
            id=location.id,
            status="deleted",
            affected_files=0,
        )


class TestStorageConnectionUseCase:
    def __init__(self, repository: StorageLocationRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        command: TestStorageConnectionCommand,
    ) -> ConnectionTestResultDTO:
        location = await self.repository.get_by_id(command.location_id)
        if location is None:
            raise NotFoundError(f"存储位置不存在: {command.location_id}")

        if location.protocol in {"file", "mounted"}:
            root = Path(location.root_path or location.endpoint)
            if not root.is_dir():
                raise StorageConnectionError(f"存储路径不可访问: {root}")
            return ConnectionTestResultDTO(
                success=True,
                message="连接成功",
            )

        parsed = urlparse(location.endpoint)
        if not parsed.hostname:
            raise StorageConnectionError(f"存储地址缺少主机: {location.endpoint}")
        port = parsed.port or _DEFAULT_PORTS.get(location.protocol)
        if port is None:
            raise StorageConnectionError(f"不支持的存储协议: {location.protocol}")

        try:
            with socket.create_connection(
                (parsed.hostname, port),
                timeout=3,
            ):
                pass
        except OSError as exc:
            raise StorageConnectionError(
                f"无法连接到 {parsed.hostname}:{port}"
            ) from exc

        return ConnectionTestResultDTO(success=True, message="连接成功")
