"""Bun pins every platform from its GitHub release, including Termux."""

import zipfile

import pytest

from pm import Store, get_package
from pm.store import ALL_TARGETS, MUSL_TARGETS


EXPECTED = {
    "win32-x64": "bun-windows-x64.zip",
    "win32-arm64": "bun-windows-aarch64.zip",
    "linux-x64": "bun-linux-x64.zip",
    "linux-arm64": "bun-linux-aarch64.zip",
    "linux-x64-musl": "bun-linux-x64-musl.zip",
    "linux-arm64-musl": "bun-linux-aarch64-musl.zip",
    "linux-arm64-bionic": "bun-linux-aarch64-android.zip",
    "darwin-x64": "bun-darwin-x64.zip",
    "darwin-arm64": "bun-darwin-aarch64.zip",
}


@pytest.mark.parametrize("target,asset", sorted(EXPECTED.items()))
def test_every_target_fetches_its_release_asset(target, asset):
    package = get_package("bun")
    assert package.missing_reason(target) is None
    assert package.fetch_url("1.4.2", target) == (
        "https://github.com/oven-sh/bun/releases/download/bun-v1.4.2/" + asset
    )


def test_all_targets_have_a_bun_artifact():
    assert set(EXPECTED) == set(ALL_TARGETS)
    assert not MUSL_TARGETS - set(EXPECTED)


def test_termux_uses_the_android_build():
    package = get_package("bun")
    assert "android" in package.fetch_url("1.4.2", "linux-arm64-bionic")


def test_bun_is_optional_and_not_a_default_install():
    package = get_package("bun")
    assert package.optional is True
    assert package.default is False


def test_pinning_uses_the_release_digest_without_downloading(monkeypatch):
    from pm import packages

    seen = []

    def digests(repo, tag):
        seen.append((repo, tag))
        return {"bun-darwin-aarch64.zip": "a" * 64}

    monkeypatch.setattr(packages, "_github_release_digests", digests)
    package = get_package("bun")
    url = package.fetch_url("1.4.2", "darwin-arm64")
    assert package.known_sha256("1.4.2", url) == "a" * 64
    assert seen == [("oven-sh/bun", "bun-v1.4.2")]


def test_staging_flattens_the_release_directory(tmp_path):
    package = get_package("bun")
    archive = tmp_path / "bun.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("bun-darwin-aarch64/bun", "fixture")
    staged = tmp_path / "staged"
    package.unpack(archive, staged, "darwin-arm64")
    package.stage(Store(tmp_path / "store"), staged, "1.4.2", "darwin-arm64")
    assert package.binary(staged, "darwin-arm64") == staged / "bun"
    assert (staged / "bun").read_text(encoding="utf-8") == "fixture"


def test_latest_versions_uses_release_tags(monkeypatch):
    from pm import packages

    monkeypatch.setattr(packages, "github_release_tags", lambda repo, strip_prefix="": ["1.4.2"])
    assert get_package("bun").latest_versions("darwin-arm64") == ["1.4.2"]
