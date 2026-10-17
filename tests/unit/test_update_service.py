"""update_service: sürüm karşılaştırma, Release ayrıştırma, güvenlik kuralları (adres/ad/boyut/SHA-256), kurulum başlatma."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

import pytest

from src.services import update_service as us
from src.version import APP_NAME, RELEASE_REPO

REPO = RELEASE_REPO
PAYLOAD = b"MZ" + b"kurulum-icerigi" * 1000
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def make_opener(routes: dict[str, bytes], calls: list[str] | None = None) -> us.Opener:
    def _open(request: urllib.request.Request) -> FakeResponse:
        url = request.full_url
        if calls is not None:
            calls.append(url)
        if url not in routes:
            raise urllib.error.URLError(f"beklenmeyen adres: {url}")
        return FakeResponse(routes[url])

    return _open


def asset(version: str, *, digest: str | None = None, size: int | None = None, name: str | None = None) -> dict[str, object]:
    asset_name = name or us.installer_asset_name(version)
    data: dict[str, object] = {
        "name": asset_name,
        "size": len(PAYLOAD) if size is None else size,
        "browser_download_url": f"https://github.com/{REPO}/releases/download/v{version}/{asset_name}",
    }
    if digest is not None:
        data["digest"] = digest
    return data


def release(version: str = "2.0.0", **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": False,
        "body": "Yenilikler",
        "html_url": f"https://github.com/{REPO}/releases/tag/v{version}",
        "assets": [asset(version, digest=f"sha256:{PAYLOAD_SHA}")],
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------- sürüm


def test_version_parsing_and_numeric_comparison() -> None:
    assert us.parse_version("v2.1.5") == (2, 1, 5)
    assert us.parse_version("2.10.0") == (2, 10, 0)
    assert us.parse_version("2.2.0-rc1") is None  # ön sürüm tanınmaz
    assert us.parse_version("abc") is None
    assert us.is_newer("2.10.0", "2.9.0") is True  # sayısal, sözlük sırası değil
    assert us.is_newer("2.1.5", "2.1.5") is False
    assert us.is_newer("garip", "1.0.0") is False


def test_release_to_update_accepts_only_newer_stable_releases() -> None:
    info = us.release_to_update(release("2.0.0"), "1.0.0")
    assert info is not None
    assert (info.version, info.sha256, info.asset_name) == ("2.0.0", PAYLOAD_SHA, f"{APP_NAME}-Setup-2.0.0.exe")

    assert us.release_to_update(release("1.0.0"), "1.0.0") is None  # aynı sürüm
    assert us.release_to_update(release("2.0.0", prerelease=True), "1.0.0") is None
    assert us.release_to_update(release("2.0.0", draft=True), "1.0.0") is None
    assert us.release_to_update(release("2.0.0", tag_name="v2.0.0-rc1"), "1.0.0") is None
    assert us.release_to_update(release("2.0.0", assets=[]), "1.0.0") is None  # kurulum dosyası yok


def test_release_rejects_untrusted_download_host_and_bad_size() -> None:
    evil = release("2.0.0")
    evil["assets"] = [{**asset("2.0.0", digest=f"sha256:{PAYLOAD_SHA}"), "browser_download_url": "https://evil.example/x.exe"}]
    with pytest.raises(us.UpdateError):
        us.release_to_update(evil, "1.0.0")

    other_repo = release("2.0.0")
    other_repo["assets"] = [{**asset("2.0.0"), "browser_download_url": "https://github.com/baska/depo/releases/download/v2.0.0/a.exe"}]
    with pytest.raises(us.UpdateError):
        us.release_to_update(other_repo, "1.0.0")

    huge = release("2.0.0", assets=[asset("2.0.0", size=us.MAX_INSTALLER_BYTES + 1)])
    with pytest.raises(us.UpdateError):
        us.release_to_update(huge, "1.0.0")


def test_wrong_asset_name_is_ignored() -> None:
    wrong = release("2.0.0", assets=[asset("2.0.0", name="Baska-Setup-2.0.0.exe")])
    assert us.release_to_update(wrong, "1.0.0") is None


def test_notes_are_length_limited() -> None:
    info = us.release_to_update(release("2.0.0", body="x" * 50_000), "1.0.0")
    assert info is not None and len(info.notes) == us.MAX_NOTES_CHARS


# ---------------------------------------------------------------- ağ + indirme


def test_fetch_latest_release_uses_single_unauthenticated_request() -> None:
    calls: list[str] = []
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    opener = make_opener({url: json.dumps(release("2.0.0")).encode("utf-8")}, calls)
    assert us.check_for_update("1.0.0", opener=opener) is not None
    assert calls == [url]

    with pytest.raises(us.UpdateError):
        us.fetch_latest_release(opener=make_opener({}))  # ağ hatası UpdateError'a çevrilir


def test_oversized_json_response_is_rejected() -> None:
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    opener = make_opener({url: b"{" + b" " * (us.MAX_JSON_BYTES + 10) + b"}"})
    with pytest.raises(us.UpdateError):
        us.fetch_latest_release(opener=opener)


def _info(**overrides: object) -> us.UpdateInfo:
    base = us.release_to_update(release("2.0.0"), "1.0.0")
    assert base is not None
    values = {**base.__dict__, **overrides}
    return us.UpdateInfo(**values)  # type: ignore[arg-type]


def test_download_verifies_sha256_and_reports_progress(tmp_path: Path) -> None:
    info = _info()
    progress: list[tuple[int, int]] = []
    opener = make_opener({info.download_url: PAYLOAD})
    result = us.download_installer(info, tmp_path, lambda done, total: progress.append((done, total)), opener)
    assert result.read_bytes() == PAYLOAD
    assert progress[-1] == (len(PAYLOAD), len(PAYLOAD))
    assert not list(tmp_path.glob("*.part"))


def test_download_deletes_file_on_sha_mismatch(tmp_path: Path) -> None:
    info = _info(sha256="0" * 64)
    with pytest.raises(us.UpdateError, match="SHA-256"):
        us.download_installer(info, tmp_path, opener=make_opener({info.download_url: PAYLOAD}))
    assert not list(tmp_path.iterdir())


def test_download_rejects_size_mismatch_and_oversize(tmp_path: Path) -> None:
    short = _info(size=len(PAYLOAD) + 5)
    with pytest.raises(us.UpdateError):
        us.download_installer(short, tmp_path, opener=make_opener({short.download_url: PAYLOAD}))
    assert not list(tmp_path.iterdir())

    small = _info(size=10)  # Release'te yazandan fazla veri gelirse akış kesilir
    with pytest.raises(us.UpdateError):
        us.download_installer(small, tmp_path, opener=make_opener({small.download_url: PAYLOAD}))
    assert not list(tmp_path.iterdir())


def test_download_refuses_when_no_digest_anywhere(tmp_path: Path) -> None:
    info = _info(sha256=None, sha256_url=None)
    with pytest.raises(us.UpdateError, match="SHA-256"):
        us.download_installer(info, tmp_path, opener=make_opener({info.download_url: PAYLOAD}))


def test_digest_is_read_from_sha256_asset_when_api_digest_missing(tmp_path: Path) -> None:
    sha_url = f"https://github.com/{REPO}/releases/download/v2.0.0/{APP_NAME}-Setup-2.0.0.exe.sha256"
    info = _info(sha256=None, sha256_url=sha_url)
    text = f"{PAYLOAD_SHA} *{APP_NAME}-Setup-2.0.0.exe\n".encode()
    opener = make_opener({info.download_url: PAYLOAD, sha_url: text})
    assert us.download_installer(info, tmp_path, opener=opener).is_file()


def test_download_rejects_untrusted_url_and_wrong_name(tmp_path: Path) -> None:
    with pytest.raises(us.UpdateError):
        us.download_installer(_info(download_url="http://github.com/x/y/releases/download/a/b.exe"), tmp_path)
    with pytest.raises(us.UpdateError):
        us.download_installer(_info(asset_name="Setup.exe"), tmp_path, opener=make_opener({}))


def test_redirect_handler_allows_only_github_hosts() -> None:
    handler = us._SafeRedirectHandler()
    request = urllib.request.Request("https://github.com/x")
    ok = handler.redirect_request(request, io.BytesIO(), 302, "Found", {}, "https://objects.githubusercontent.com/abc")  # type: ignore[arg-type]
    assert ok is not None
    with pytest.raises(urllib.error.URLError):
        handler.redirect_request(request, io.BytesIO(), 302, "Found", {}, "https://evil.example/abc")  # type: ignore[arg-type]
    with pytest.raises(urllib.error.URLError):
        handler.redirect_request(request, io.BytesIO(), 302, "Found", {}, "http://github.com/abc")  # type: ignore[arg-type]


# ---------------------------------------------------------------- kurulum başlatma


def test_installer_arguments_are_fixed_and_shell_free(tmp_path: Path) -> None:
    installer = tmp_path / f"{APP_NAME}-Setup-2.0.0.exe"
    args = us.installer_arguments(installer, tmp_path)
    assert args[0] == str(installer)
    assert args[1:4] == ["/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS"]
    assert args[4] == f"/LOG={tmp_path / 'install.log'}"


def test_launch_installer_starts_detached_process(tmp_path: Path) -> None:
    installer = tmp_path / f"{APP_NAME}-Setup-2.0.0.exe"
    started: list[tuple[list[str], dict[str, object]]] = []
    us.launch_installer(installer, tmp_path, popen=lambda args, **kw: started.append((args, kw)))
    assert len(started) == 1
    flags = started[0][1]["creationflags"]
    assert flags & getattr(subprocess, "DETACHED_PROCESS", 0x8)  # type: ignore[operator]
    assert started[0][1].get("shell") is None  # kabuk yok


def test_launch_installer_falls_back_to_explorer_on_sac_block_then_raises(tmp_path: Path) -> None:
    installer = tmp_path / f"{APP_NAME}-Setup-2.0.0.exe"

    def blocked(*_a: object, **_k: object) -> None:
        exc = OSError("engellendi")
        exc.winerror = 4551  # type: ignore[attr-defined]
        raise exc

    executed: list[str] = []
    us.launch_installer(installer, tmp_path, popen=blocked, shell_execute=lambda p, _args: executed.append(p) or 42)
    assert executed == [str(installer)]

    with pytest.raises(us.InstallerBlockedError):
        us.launch_installer(installer, tmp_path, popen=blocked, shell_execute=lambda _p, _a: 5)


def test_launch_installer_other_errors_and_bad_names(tmp_path: Path) -> None:
    installer = tmp_path / f"{APP_NAME}-Setup-2.0.0.exe"

    def missing(*_a: object, **_k: object) -> None:
        raise FileNotFoundError("yok")

    with pytest.raises(us.UpdateError):
        us.launch_installer(installer, tmp_path, popen=missing)
    with pytest.raises(us.UpdateError):
        us.launch_installer(tmp_path / "zararli.exe", tmp_path, popen=lambda *a, **k: None)


# ---------------------------------------------------------------- tercihler + ortam


def test_preferences_roundtrip_and_corrupt_file_fallback() -> None:
    assert us.load_preferences() == us.UpdatePreferences()
    us.save_preferences(us.UpdatePreferences(check_on_startup=False, skipped_version="2.0.0"))
    loaded = us.load_preferences()
    assert loaded.check_on_startup is False and loaded.skipped_version == "2.0.0"

    us.preferences_path().write_text("{bozuk", encoding="utf-8")
    assert us.load_preferences() == us.UpdatePreferences()


def test_env_variable_disables_update_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(us.NO_UPDATE_CHECK_ENV, raising=False)
    assert us.update_check_disabled_by_env() is False
    monkeypatch.setenv(us.NO_UPDATE_CHECK_ENV, "1")
    assert us.update_check_disabled_by_env() is True
    monkeypatch.setenv(us.NO_UPDATE_CHECK_ENV, "0")
    assert us.update_check_disabled_by_env() is False
