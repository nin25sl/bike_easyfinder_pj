from pathlib import Path
from zipfile import ZipInfo

import pytest

from collection_worker.errors import ConfigurationError
from collection_worker.regions import MAX_ARCHIVE_MEMBER_BYTES, _safe_extract


class FakeArchive:
    def __init__(self, members: list[ZipInfo]):
        self.members = members
        self.extracted: list[str] = []

    def infolist(self) -> list[ZipInfo]:
        return self.members

    def extract(self, member: ZipInfo, destination: Path) -> None:
        self.extracted.append(member.filename)


def member(name: str, size: int = 1) -> ZipInfo:
    info = ZipInfo(name)
    info.file_size = size
    return info


def test_safe_extract_prefers_shapefile_and_skips_large_geojson(tmp_path: Path) -> None:
    archive = FakeArchive(
        [
            member("N03.geojson", MAX_ARCHIVE_MEMBER_BYTES + 1),
            member("N03.shp"),
            member("N03.shx"),
            member("N03.dbf"),
            member("N03.prj"),
        ]
    )

    _safe_extract(archive, tmp_path)  # type: ignore[arg-type]

    assert archive.extracted == ["N03.shp", "N03.shx", "N03.dbf", "N03.prj"]


def test_safe_extract_rejects_large_geojson_when_it_is_the_only_dataset(tmp_path: Path) -> None:
    archive = FakeArchive([member("N03.geojson", MAX_ARCHIVE_MEMBER_BYTES + 1)])

    with pytest.raises(ConfigurationError, match="member is too large"):
        _safe_extract(archive, tmp_path)  # type: ignore[arg-type]
