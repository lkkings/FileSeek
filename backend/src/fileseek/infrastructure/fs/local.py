from __future__ import annotations

import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Literal

from fileseek.infrastructure.fs.base import FileSystem
from fileseek.infrastructure.fs.path import VirtualPath


class LocalFileSystem(FileSystem):
    """本地文件系统实现。

    负责：

    - 文件读写
    - 文件存在性判断
    - 文件属性获取
    - 文件删除
    - 目录遍历
    - 文件/目录压缩
    - 压缩包解压

    VirtualPath 负责路径抽象，
    LocalFileSystem 负责真正的本地磁盘操作。
    """

    # ==================================================
    # 基础文件操作
    # ==================================================

    def open(
        self,
        path: VirtualPath,
        mode: Literal[
            "r",
            "rb",
            "w",
            "wb",
            "a",
            "ab",
        ] = "rb",
        **kwargs,
    ):
        """打开本地文件。"""

        return open(
            path.path,
            mode,
            **kwargs,
        )

    def exists(
        self,
        path: VirtualPath,
    ) -> bool:
        """判断路径是否存在。"""

        return Path(
            path.path
        ).exists()

    def is_file(
        self,
        path: VirtualPath,
    ) -> bool:
        """判断路径是否为普通文件。"""

        return Path(
            path.path
        ).is_file()

    def is_dir(
        self,
        path: VirtualPath,
    ) -> bool:
        """判断路径是否为目录。"""

        return Path(
            path.path
        ).is_dir()

    def stat(
        self,
        path: VirtualPath,
    ):
        """获取文件属性。"""

        stat = Path(path.path).stat()

        return {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "ctime": stat.st_ctime,
            "atime": stat.st_atime,
            "mode": stat.st_mode,
            "is_file": Path(path.path).is_file(),
            "is_dir": Path(path.path).is_dir(),
        }

    def iterdir(
        self,
        path: VirtualPath,
    ):
        """遍历目录。"""

        directory = Path(
            path.path
        )

        if not directory.exists():
            raise FileNotFoundError(
                f"路径不存在: {path}"
            )

        if not directory.is_dir():
            raise NotADirectoryError(
                f"不是目录: {path}"
            )

        for child in directory.iterdir():
            yield VirtualPath(
                str(child)
            )

    # ==================================================
    # 删除
    # ==================================================

    def delete(
        self,
        path: VirtualPath,
    ) -> None:
        """删除文件或目录。"""

        target = Path(
            path.path
        )

        if not target.exists():
            return

        if target.is_dir():
            shutil.rmtree(target)
            return

        target.unlink()

    # ==================================================
    # 压缩
    # ==================================================

    def compress(
        self,
        path: VirtualPath,
        target_path: VirtualPath | None = None,
    ) -> Path:
        """压缩文件或目录。

        压缩格式根据 target_path 的后缀决定：

            xxx.zip
            xxx.tar
            xxx.tar.gz
            xxx.tgz
            xxx.tar.bz2
            xxx.tbz2
            xxx.tar.xz
            xxx.txz

        如果没有指定 target_path：

            file.txt -> file.zip
            directory -> directory.zip

        压缩成功后不会删除原始文件。

        是否删除原文件应该由上层业务决定，
        FileSystem 不应该隐式修改用户数据。
        """

        source = Path(
            path.path
        )

        if not source.exists():
            raise FileNotFoundError(
                f"文件或目录不存在: {path}"
            )

        if target_path is None:
            target = source.with_suffix(
                ".zip"
            )
        else:
            target = Path(
                target_path.path
            )

        if target.exists():
            raise FileExistsError(
                f"目标文件已存在: {target}"
            )

        if source.resolve() == target.resolve():
            raise ValueError(
                "源文件和目标压缩包不能相同"
            )

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        suffix = self._compression_suffix(
            target
        )

        try:

            if suffix == "zip":
                self._compress_zip(
                    source,
                    target,
                )

            elif suffix == "tar":
                self._compress_tar(
                    source,
                    target,
                    compression=None,
                )

            elif suffix in {
                "tar.gz",
                "tgz",
            }:
                self._compress_tar(
                    source,
                    target,
                    compression="gz",
                )

            elif suffix in {
                "tar.bz2",
                "tbz2",
            }:
                self._compress_tar(
                    source,
                    target,
                    compression="bz2",
                )

            elif suffix in {
                "tar.xz",
                "txz",
            }:
                self._compress_tar(
                    source,
                    target,
                    compression="xz",
                )

            else:
                raise ValueError(
                    f"不支持的压缩格式: {target.suffix}"
                )

        except Exception:

            # 压缩过程中失败时删除不完整的压缩包。
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()

            raise

        return target

    # ==================================================
    # ZIP
    # ==================================================

    def _compress_zip(
        self,
        source: Path,
        target: Path,
    ) -> None:
        """创建 ZIP 压缩包。"""

        with zipfile.ZipFile(
            target,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:

            if source.is_file():

                archive.write(
                    source,
                    arcname=source.name,
                )

                return

            root = source.parent

            for item in source.rglob("*"):

                archive.write(
                    item,
                    arcname=item.relative_to(
                        root
                    ),
                )

    # ==================================================
    # TAR
    # ==================================================

    def _compress_tar(
        self,
        source: Path,
        target: Path,
        compression: str | None,
    ) -> None:
        """创建 TAR 系列压缩包。"""

        mode = "w"

        if compression:
            mode += f":{compression}"

        with tarfile.open(
            target,
            mode=mode,
        ) as archive:

            archive.add(
                source,
                arcname=source.name,
            )

    # ==================================================
    # 解压
    # ==================================================

    def decompress(
        self,
        path: VirtualPath,
        target_path: VirtualPath | None = None,
    ) -> Path:
        """解压压缩包。

        支持：

            .zip
            .tar
            .tar.gz
            .tgz
            .tar.bz2
            .tbz2
            .tar.xz
            .txz

        如果没有指定 target_path：

            /data/a.zip
                ↓
            /data/a/

        如果归档中只有一个文件，则返回该文件路径。

        如果归档中包含多个文件，则返回解压目录。
        """

        archive = Path(
            path.path
        )

        if not archive.exists():
            raise FileNotFoundError(
                f"压缩文件不存在: {path}"
            )

        if not archive.is_file():
            raise IsADirectoryError(
                f"不是文件: {path}"
            )

        target = (
            Path(target_path.path)
            if target_path is not None
            else archive.with_suffix("")
        )

        if target.exists():
            raise FileExistsError(
                f"解压目标已存在: {target}"
            )

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:

            if zipfile.is_zipfile(
                archive
            ):

                return self._decompress_zip(
                    archive,
                    target,
                )

            if tarfile.is_tarfile(
                archive
            ):

                return self._decompress_tar(
                    archive,
                    target,
                )

            raise ValueError(
                f"不支持的压缩文件格式: "
                f"{archive.name}"
            )

        except Exception:

            if target.exists():

                if target.is_dir():
                    shutil.rmtree(target)

                else:
                    target.unlink()

            raise

    # ==================================================
    # ZIP 解压
    # ==================================================

    def _decompress_zip(
        self,
        archive: Path,
        target: Path,
    ) -> Path:
        """解压 ZIP。"""

        with zipfile.ZipFile(
            archive,
            mode="r",
        ) as zf:

            members = zf.infolist()

            self._validate_zip_members(
                members,
                target,
            )

            entries = self._archive_entries(
                [
                    member.filename
                    for member in members
                    if member.filename
                ]
            )

            # 只有一个顶层成员。
            if len(entries) == 1:

                top_level = entries[0]

                # 单文件归档：
                #
                # a.zip
                #   └── a.txt
                #
                # 直接解压到 target.parent，
                # 最终得到：
                #
                # a.txt
                #
                # 而不是：
                #
                # target/a.txt
                if self._is_single_file_zip(
                    members
                ):

                    zf.extractall(
                        target.parent
                    )

                    return (
                        target.parent
                        / top_level
                    )

            target.mkdir(
                parents=True,
                exist_ok=True,
            )

            zf.extractall(
                target
            )

            return target

    # ==================================================
    # TAR 解压
    # ==================================================

    def _decompress_tar(
        self,
        archive: Path,
        target: Path,
    ) -> Path:
        """解压 TAR。"""

        with tarfile.open(
            archive,
            mode="r:*",
        ) as tf:

            members = tf.getmembers()

            self._validate_tar_members(
                members,
                target,
            )

            entries = self._archive_entries(
                [
                    member.name
                    for member in members
                    if member.name
                ]
            )

            if (
                len(entries) == 1
                and self._is_single_file_tar(
                    members
                )
            ):

                tf.extractall(
                    target.parent,
                    filter="data",
                )

                return (
                    target.parent
                    / entries[0]
                )

            target.mkdir(
                parents=True,
                exist_ok=True,
            )

            tf.extractall(
                target,
                filter="data",
            )

            return target

    # ==================================================
    # 安全校验
    # ==================================================

    @staticmethod
    def _validate_zip_members(
        members,
        target: Path,
    ) -> None:
        """防止 ZIP Slip。"""

        root = target.resolve()

        for member in members:

            name = member.filename

            destination = (
                root / name
            ).resolve()

            if not destination.is_relative_to(
                root
            ):
                raise ValueError(
                    f"压缩包内含非法路径: {name}"
                )

    @staticmethod
    def _validate_tar_members(
        members,
        target: Path,
    ) -> None:
        """防止 Tar Slip。"""

        root = target.resolve()

        for member in members:

            destination = (
                root / member.name
            ).resolve()

            if not destination.is_relative_to(
                root
            ):
                raise ValueError(
                    f"压缩包内含非法路径: "
                    f"{member.name}"
                )

    # ==================================================
    # Archive Utils
    # ==================================================

    @staticmethod
    def _archive_entries(
        members: list[str],
    ) -> list[str]:
        """获取归档中的顶层成员。"""

        entries: set[str] = set()

        for member in members:

            normalized = member.replace(
                "\\",
                "/",
            ).strip("/")

            if not normalized:
                continue

            top_level = normalized.split(
                "/",
                1,
            )[0]

            entries.add(
                top_level
            )

        return sorted(entries)

    @staticmethod
    def _is_single_file_zip(
        members,
    ) -> bool:
        """判断 ZIP 是否只包含一个文件。"""

        files = [
            member
            for member in members
            if not member.is_dir()
        ]

        return len(files) == 1

    @staticmethod
    def _is_single_file_tar(
        members,
    ) -> bool:
        """判断 TAR 是否只包含一个普通文件。"""

        files = [
            member
            for member in members
            if member.isfile()
        ]

        return len(files) == 1

    @staticmethod
    def _compression_suffix(
        path: Path,
    ) -> str:
        """获取压缩格式。"""

        name = path.name.lower()

        if name.endswith(".tar.gz"):
            return "tar.gz"

        if name.endswith(".tar.bz2"):
            return "tar.bz2"

        if name.endswith(".tar.xz"):
            return "tar.xz"

        if name.endswith(".tgz"):
            return "tgz"

        if name.endswith(".tbz2"):
            return "tbz2"

        if name.endswith(".txz"):
            return "txz"

        if name.endswith(".tar"):
            return "tar"

        if name.endswith(".zip"):
            return "zip"

        return path.suffix.lower().lstrip(".")