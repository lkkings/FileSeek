"""本地适配器的压缩/解压。

这两个方法就是回收站的物理动作：**加入回收站＝压缩，从回收站恢复＝解压**，从回收站
移除才是物理删除（那一步走 `delete()`）。所以这里盯的是"互逆"：压完只剩包，解完只剩
文件，且解出来的路径和压之前一模一样。

之前这两个方法没有任何测试，于是三件事都错着：压完不删原件（文件留在原地、磁盘占用翻倍）、
解压解进一个 `<包名>/` 目录（还原后的路径比原来多一层）、解完不删包。
"""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from fileseek.infrastructure.storage.local_adapter import LocalFileSystemAdapter
from fileseek.shared.domain.file_types import FileType


@pytest.fixture
def document(tmp_path: Path) -> Path:
    path = tmp_path / "季度报告.txt"
    path.write_text("第一行\n第二行\n", encoding="utf-8")
    return path


class TestCompressReplacesTheFile:
    def test_compressing_leaves_only_the_archive(self, document: Path) -> None:
        archive = LocalFileSystemAdapter(document).compress()

        # 加入回收站＝压缩：原件不该还留在原地。
        assert not document.exists()
        assert archive.exists()
        assert archive == document.with_suffix(".zip")

    def test_a_video_is_archived_as_tar_gz(self, tmp_path: Path) -> None:
        video = tmp_path / "骑行.mp4"
        video.write_bytes(b"\x00\x01\x02")

        archive = LocalFileSystemAdapter(video).compress()

        # 视频已经是压缩过的容器，zip 再压一遍没意义，走 tar.gz。
        assert archive.name == "骑行.tar.gz"
        assert tarfile.is_tarfile(archive)
        assert not video.exists()

    def test_the_archive_holds_the_file_under_its_own_name(self, document: Path) -> None:
        archive = LocalFileSystemAdapter(document).compress()

        with zipfile.ZipFile(archive) as opened:
            # 成员名是原文件名，不带目录——解压时靠这个落回原位置。
            assert opened.namelist() == ["季度报告.txt"]

    def test_compressing_a_missing_file_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            LocalFileSystemAdapter(tmp_path / "并不存在.txt").compress()

    def test_an_unknown_extension_still_compresses(self, tmp_path: Path) -> None:
        odd = tmp_path / "备份.bin"
        odd.write_bytes(b"payload")

        archive = LocalFileSystemAdapter(odd).compress()

        # 认不出类型不能让删除失败，退回 zip。
        assert archive.name == "备份.zip"
        assert not odd.exists()


class TestDecompressRestoresTheFile:
    def test_restoring_puts_the_file_back_where_it_was(self, document: Path) -> None:
        original_text = document.read_text(encoding="utf-8")
        archive = LocalFileSystemAdapter(document).compress()

        restored = LocalFileSystemAdapter(archive).decompress()

        # 从回收站恢复＝解压：路径和内容都回到压之前的样子。
        assert restored == document
        assert restored.read_text(encoding="utf-8") == original_text

    def test_restoring_removes_the_archive(self, document: Path) -> None:
        archive = LocalFileSystemAdapter(document).compress()

        LocalFileSystemAdapter(archive).decompress()

        # 包已经还原成文件了，留着它就是一份多余副本。
        assert not archive.exists()

    def test_a_video_round_trips_too(self, tmp_path: Path) -> None:
        video = tmp_path / "骑行.mp4"
        video.write_bytes(b"\x00\x01\x02")
        archive = LocalFileSystemAdapter(video).compress()

        restored = LocalFileSystemAdapter(archive).decompress()

        assert restored == video
        assert restored.read_bytes() == b"\x00\x01\x02"
        assert not archive.exists()

    def test_the_round_trip_is_exact_for_every_media_type(self, tmp_path: Path) -> None:
        for name, file_type in (
            ("报告.pdf", FileType.DOCUMENT),
            ("猫.jpg", FileType.IMAGE),
            ("片子.mp4", FileType.VIDEO),
        ):
            source = tmp_path / name
            source.write_bytes(name.encode("utf-8"))

            archive = LocalFileSystemAdapter(source, file_type).compress()
            restored = LocalFileSystemAdapter(archive).decompress()

            assert restored == source
            assert restored.read_bytes() == name.encode("utf-8")

    def test_decompressing_something_that_is_not_an_archive_is_refused(
        self, document: Path
    ) -> None:
        with pytest.raises(ValueError, match="不支持的压缩文件格式"):
            LocalFileSystemAdapter(document).decompress()

    def test_decompressing_a_missing_archive_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            LocalFileSystemAdapter(tmp_path / "并不存在.zip").decompress()


class TestMultiMemberArchives:
    def test_a_directory_archive_extracts_into_its_own_folder(self, tmp_path: Path) -> None:
        folder = tmp_path / "相册"
        folder.mkdir()
        (folder / "a.jpg").write_bytes(b"a")
        (folder / "b.jpg").write_bytes(b"b")

        archive = LocalFileSystemAdapter(folder).compress()
        restored = LocalFileSystemAdapter(archive).decompress()

        # 多个成员不能散落到包的同级目录里，那会把别的文件混在一起。
        assert restored.is_dir()
        assert sorted(p.name for p in restored.rglob("*.jpg")) == ["a.jpg", "b.jpg"]

    def test_a_member_escaping_the_target_directory_is_refused(self, tmp_path: Path) -> None:
        archive = tmp_path / "恶意.zip"
        with zipfile.ZipFile(archive, "w") as opened:
            opened.writestr("../外面.txt", "escaped")

        # zip slip：`extractall` 会照包里的名字写盘，`../` 能写到目标目录外面去。
        with pytest.raises(ValueError, match="非法路径"):
            LocalFileSystemAdapter(archive).decompress()

        assert not (tmp_path.parent / "外面.txt").exists()
