"""Uygulama içi güncelleme: GitHub Releases denetimi, doğrulamalı indirme ve sessiz kurulumu başlatma (UI'dan bağımsız)."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, BinaryIO
import urllib.error
import urllib.parse
import urllib.request

from src.core import app_paths
from src.version import APP_NAME, RELEASE_REPO

logger = logging.getLogger(__name__)

NO_UPDATE_CHECK_ENV = "TABSCREEN_NO_UPDATE_CHECK"
API_HOST = "api.github.com"
DOWNLOAD_HOST = "github.com"
CDN_HOST_SUFFIX = ".githubusercontent.com"
MAX_INSTALLER_BYTES = 400 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_SHA_FILE_BYTES = 4 * 1024
MAX_NOTES_CHARS = 4000
REQUEST_TIMEOUT_SEC = 15.0
CHUNK_BYTES = 64 * 1024
WINERROR_BLOCKED = (4551, 1260)  # Akıllı Uygulama Denetimi / grup ilkesi engeli

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_SHA256_RE = re.compile(r"\b([0-9a-fA-F]{64})\b")
_INSTALLER_NAME_RE = re.compile(rf"^{re.escape(APP_NAME)}-Setup-\d+\.\d+\.\d+\.exe$")

Response = BinaryIO
Opener = Callable[[urllib.request.Request], AbstractContextManager[Any]]
ProgressCallback = Callable[[int, int], None]


class UpdateError(Exception):
    """Güncelleme denetimi/indirmesi başarısız (kullanıcıya gösterilebilir Türkçe mesajla)."""


class InstallerBlockedError(UpdateError):
    """Windows kurulum dosyasını başlatmayı engelledi (ör. Akıllı Uygulama Denetimi)."""


@dataclass(frozen=True)
class UpdateInfo:
    """Yüklü sürümden yeni, doğrulanabilir bir yayının özeti."""

    version: str
    tag: str
    asset_name: str
    download_url: str
    size: int
    sha256: str | None
    sha256_url: str | None
    notes: str
    html_url: str


@dataclass
class UpdatePreferences:
    """`~/.tabscreen_usb/updates.json`: açılış denetimi ve atlanan sürüm."""

    check_on_startup: bool = True
    skipped_version: str = ""


# ---------------------------------------------------------------- sürüm


def parse_version(text: str) -> tuple[int, int, int] | None:
    """`2.1.5` / `v2.1.5` -> (2, 1, 5); ön sürüm (`-rc1`) veya bozuk biçim None."""
    match = _VERSION_RE.match(text.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def is_newer(candidate: str, current: str) -> bool:
    """Sayısal karşılaştırma (`2.10.0 > 2.9.0`); biçimi tanınmayan sürüm yeni sayılmaz."""
    cand, cur = parse_version(candidate), parse_version(current)
    return cand is not None and cur is not None and cand > cur


def installer_asset_name(version: str) -> str:
    return f"{APP_NAME}-Setup-{version}.exe"


# ---------------------------------------------------------------- güvenlik doğrulamaları


def _host_allowed(url: str, *, hosts: tuple[str, ...], allow_cdn: bool) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return host in hosts or (allow_cdn and host.endswith(CDN_HOST_SUFFIX))


def validate_download_url(url: str, repo: str = RELEASE_REPO) -> None:
    """İndirme adresi yalnızca bu deponun `releases/download/` yolu olabilir."""
    parsed = urllib.parse.urlparse(url)
    prefix = f"/{repo}/releases/download/"
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != DOWNLOAD_HOST or not parsed.path.startswith(prefix):
        raise UpdateError("Güncelleme adresi güvenilir değil; indirme reddedildi.")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Yönlendirmeyi yalnızca github.com ve *.githubusercontent.com adreslerine kabul eder."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        if not _host_allowed(newurl, hosts=(DOWNLOAD_HOST, API_HOST), allow_cdn=True):
            raise urllib.error.URLError(f"Güvenilmeyen yönlendirme reddedildi: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def default_opener() -> Opener:
    director = urllib.request.build_opener(_SafeRedirectHandler)

    def _open(request: urllib.request.Request) -> AbstractContextManager[Any]:
        return director.open(request, timeout=REQUEST_TIMEOUT_SEC)

    return _open


def _read_limited(response: Response, limit: int) -> bytes:
    data = response.read(limit + 1)
    if len(data) > limit:
        raise UpdateError("Sunucu yanıtı beklenenden büyük; işlem durduruldu.")
    return data


def _request(url: str, *, accept: str) -> urllib.request.Request:
    # Kimlik bilgisi gönderilmez; yalnızca kimlik belirten sabit başlık.
    return urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}-updater", "Accept": accept})


# ---------------------------------------------------------------- denetim


def update_check_disabled_by_env() -> bool:
    return os.environ.get(NO_UPDATE_CHECK_ENV, "").strip() not in ("", "0")


def fetch_latest_release(repo: str = RELEASE_REPO, opener: Opener | None = None) -> dict[str, Any]:
    """`GET /repos/<depo>/releases/latest` (tek istek, kimlik bilgisi yok)."""
    url = f"https://{API_HOST}/repos/{repo}/releases/latest"
    try:
        with (opener or default_opener())(_request(url, accept="application/vnd.github+json")) as response:
            payload = json.loads(_read_limited(response, MAX_JSON_BYTES).decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpdateError(f"Güncelleme sunucusuna ulaşılamadı: {exc}") from exc
    if not isinstance(payload, dict):
        raise UpdateError("Güncelleme sunucusu beklenmeyen bir yanıt verdi.")
    return payload


def release_to_update(release: dict[str, Any], current_version: str, repo: str = RELEASE_REPO) -> UpdateInfo | None:
    """Yayın JSON'unu yüklü sürümle kıyaslar; ön sürüm/taslak, eski sürüm ve uygunsuz varlık için None."""
    if release.get("draft") or release.get("prerelease"):
        return None
    tag = str(release.get("tag_name", ""))
    parsed = parse_version(tag)
    if parsed is None or not is_newer(tag, current_version):
        return None
    version = ".".join(str(part) for part in parsed)
    expected_name = installer_asset_name(version)

    assets = release.get("assets")
    if not isinstance(assets, list):
        return None
    installer: dict[str, Any] | None = None
    sha_asset: dict[str, Any] | None = None
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if asset.get("name") == expected_name:
            installer = asset
        elif asset.get("name") == f"{expected_name}.sha256":
            sha_asset = asset
    if installer is None:
        return None

    url = str(installer.get("browser_download_url", ""))
    validate_download_url(url, repo)
    size = int(installer.get("size", 0) or 0)
    if size <= 0 or size > MAX_INSTALLER_BYTES:
        raise UpdateError("Kurulum dosyasının boyutu geçersiz; güncelleme reddedildi.")

    digest = str(installer.get("digest") or "")
    sha256 = digest.split(":", 1)[1].lower() if digest.lower().startswith("sha256:") and _SHA256_RE.search(digest) else None
    sha_url = str(sha_asset.get("browser_download_url", "")) if sha_asset else None
    if sha_url:
        validate_download_url(sha_url, repo)

    notes = str(release.get("body") or "")[:MAX_NOTES_CHARS]
    return UpdateInfo(
        version=version,
        tag=tag,
        asset_name=expected_name,
        download_url=url,
        size=size,
        sha256=sha256,
        sha256_url=sha_url,
        notes=notes,
        html_url=str(release.get("html_url") or f"https://github.com/{repo}/releases/tag/{tag}"),
    )


def check_for_update(current_version: str, repo: str = RELEASE_REPO, opener: Opener | None = None) -> UpdateInfo | None:
    return release_to_update(fetch_latest_release(repo, opener), current_version, repo)


# ---------------------------------------------------------------- indirme


def resolve_sha256(info: UpdateInfo, opener: Opener | None = None) -> str:
    """Özet: önce GitHub `digest` alanı, yoksa Release'teki `.sha256` dosyası; ikisi de yoksa güncelleme reddedilir."""
    if info.sha256:
        return info.sha256
    if info.sha256_url:
        try:
            with (opener or default_opener())(_request(info.sha256_url, accept="text/plain")) as response:
                text = _read_limited(response, MAX_SHA_FILE_BYTES).decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as exc:
            raise UpdateError(f"Özet dosyası indirilemedi: {exc}") from exc
        match = _SHA256_RE.search(text)
        if match:
            return match.group(1).lower()
    raise UpdateError("Kurulum dosyasının SHA-256 özeti bulunamadı; güvenlik nedeniyle güncelleme reddedildi.")


def update_download_dir() -> Path:
    return Path(tempfile.gettempdir()) / f"{APP_NAME}Update"


def download_installer(
    info: UpdateInfo,
    dest_dir: Path | None = None,
    progress: ProgressCallback | None = None,
    opener: Opener | None = None,
    repo: str = RELEASE_REPO,
) -> Path:
    """Kurulum dosyasını indirir; ad, adres, boyut ve SHA-256 doğrulanır. Uyuşmazlıkta dosya silinir."""
    validate_download_url(info.download_url, repo)
    if info.asset_name != installer_asset_name(info.version):
        raise UpdateError("Kurulum dosyası adı beklenen desene uymuyor; indirme reddedildi.")
    expected_sha = resolve_sha256(info, opener)

    target_dir = dest_dir or update_download_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / info.asset_name
    partial = target.with_suffix(".exe.part")

    hasher = hashlib.sha256()
    received = 0
    try:
        with (opener or default_opener())(_request(info.download_url, accept="application/octet-stream")) as response:
            with partial.open("wb") as out:
                while True:
                    chunk = response.read(CHUNK_BYTES)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > min(info.size, MAX_INSTALLER_BYTES):
                        raise UpdateError("İndirilen dosya beklenenden büyük; işlem durduruldu.")
                    hasher.update(chunk)
                    out.write(chunk)
                    if progress is not None:
                        progress(received, info.size)
    except (urllib.error.URLError, OSError) as exc:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"İndirme başarısız: {exc}") from exc
    except UpdateError:
        partial.unlink(missing_ok=True)
        raise

    if received != info.size:
        partial.unlink(missing_ok=True)
        raise UpdateError("İndirilen dosyanın boyutu Release ile uyuşmuyor; dosya silindi.")
    if hasher.hexdigest().lower() != expected_sha.lower():
        partial.unlink(missing_ok=True)
        raise UpdateError("SHA-256 özeti uyuşmuyor; dosya silindi ve güncelleme iptal edildi.")
    target.unlink(missing_ok=True)
    partial.replace(target)
    return target


# ---------------------------------------------------------------- kurulum


def installer_arguments(installer: Path, log_dir: Path) -> list[str]:
    """Sabit argümanlar (kabuk yok): sessiz kurulum + ilerleme penceresi, çalışan uygulamayı kapat, günlük yaz."""
    return [str(installer), "/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", f"/LOG={log_dir / 'install.log'}"]


def launch_installer(
    installer: Path,
    log_dir: Path | None = None,
    popen: Callable[..., Any] = subprocess.Popen,
    shell_execute: Callable[[str, str], int] | None = None,
) -> None:
    """
    Kurulum dosyasını bağımsız süreç olarak başlatır. Windows engellerse (WinError 4551/1260) önce Gezgin'in
    çift tıklama yolunu (`ShellExecute`) dener; ikisi de engelliyse `InstallerBlockedError` fırlatır.
    """
    if not _INSTALLER_NAME_RE.match(installer.name):
        raise UpdateError("Kurulum dosyası adı beklenen desene uymuyor; başlatılmadı.")
    target_log_dir = log_dir or installer.parent
    args = installer_arguments(installer, target_log_dir)
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        popen(args, creationflags=flags, close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    except OSError as exc:
        if getattr(exc, "winerror", None) not in WINERROR_BLOCKED:
            raise UpdateError(f"Kurulum başlatılamadı: {exc}") from exc
        logger.warning("Kurulum doğrudan başlatılamadı (WinError %s); Gezgin yolu deneniyor", exc.winerror)

    execute = shell_execute or _shell_execute
    params = " ".join(f'"{a}"' if " " in a else a for a in args[1:])
    if execute(str(installer), params) <= 32:
        raise InstallerBlockedError("Windows kurulum dosyasını şimdilik engelledi.")


def _shell_execute(path: str, params: str) -> int:
    import ctypes

    return int(ctypes.windll.shell32.ShellExecuteW(None, "open", path, params, None, 1))


# ---------------------------------------------------------------- tercihler


def preferences_path() -> Path:
    return app_paths.user_data_dir() / "updates.json"


def load_preferences() -> UpdatePreferences:
    path = preferences_path()
    if not path.is_file():
        return UpdatePreferences()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Güncelleme tercihleri okunamadı, varsayılanlar kullanılıyor: %s", exc)
        return UpdatePreferences()
    if not isinstance(raw, dict):
        return UpdatePreferences()
    return UpdatePreferences(
        check_on_startup=bool(raw.get("check_on_startup", True)),
        skipped_version=str(raw.get("skipped_version", "")),
    )


def save_preferences(prefs: UpdatePreferences) -> None:
    path = preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(prefs), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
