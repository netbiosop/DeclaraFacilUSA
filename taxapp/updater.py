"""Actualizaciones automaticas desde GitHub Releases / Automatic updates from GitHub Releases.

Como funciona:
1. Usted publica una version con publicar_actualizacion.bat (sube Instalar_DeclaraFacilUSA_<version>.exe y su .sha256
   como "release" del repositorio configurado en data/actualizaciones.json).
2. La app consulta https://api.github.com/repos/<repo>/releases/latest; si la version es mas nueva que la instalada,
   avisa al administrador.
3. Al aceptar: descarga el instalador, verifica tamano y SHA-256, lo ejecuta en modo silencioso y se cierra; el instalador
   reemplaza el programa (los datos en Documentos\\DeclaraFacilUSA no se tocan) y vuelve a abrir la app.

Repositorio publico: no requiere clave. Repositorio privado: use una clave (token) de solo lectura del repositorio.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from . import __version__, data_loader
from .i18n import _, tr

logger = logging.getLogger(__name__)

ASSET_RE = re.compile(r"^Instalar_DeclaraFacilUSA_.*\.exe$", re.I)
API = "https://api.github.com"
TIMEOUT = 20


class UpdateError(Exception):
    pass


# ---------------------------------------------------------------------------- configuracion
@dataclass
class UpdateConfig:
    repo: str = "netbiosop/DeclaraFacilUSA"
    token: str = ""            # cifrado (DPAPI) si se usa repositorio privado
    auto_check: bool = True
    last_check: str = ""
    skipped: str = ""          # version que el usuario decidio omitir

    def get_token(self) -> str:
        if not self.token:
            return ""
        from .assistant import unprotect
        try:
            return unprotect(self.token)
        except (OSError, ValueError, AttributeError) as e:
            logger.warning("No se pudo descifrar el token de GitHub guardado: %s", e)
            return ""

    def set_token(self, tok: str):
        from .assistant import protect
        self.token = protect(tok.strip()) if tok.strip() else ""


def _user_file() -> Path:
    return data_loader.user_dir() / "actualizaciones.json"


def load_config() -> UpdateConfig:
    cfg = UpdateConfig()
    for p in (data_loader.data_dir() / "actualizaciones.json", _user_file()):
        for k, v in data_loader.read_json(p, {}).items():
            if k in UpdateConfig.__dataclass_fields__:
                setattr(cfg, k, v)
    return cfg


def save_config(cfg: UpdateConfig):
    _user_file().write_text(json.dumps(asdict(cfg), indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------- versiones
def parse_version(v: str) -> tuple:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:4]) + (0,) * (3 - min(3, len(nums[:4])))


def is_newer(remote: str, local: str = None) -> bool:
    return parse_version(remote) > parse_version(local or __version__)


def is_installed_app() -> bool:
    """True si corre como programa instalado (PyInstaller); False si corre desde el codigo fuente."""
    return bool(getattr(sys, "frozen", False))


@dataclass
class Release:
    version: str
    tag: str
    name: str
    notes: str
    published: str
    page_url: str
    asset_name: str = ""
    asset_api_url: str = ""
    asset_download_url: str = ""
    size: int = 0
    sha256: str = ""
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------- HTTP
def _headers(token: str = "", accept="application/vnd.github+json") -> dict:
    h = {"Accept": accept, "User-Agent": f"DeclaraFacilUSA/{__version__}", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _open(req, timeout=TIMEOUT):
    return urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context())


def _get_json(url: str, token: str = "") -> dict:
    try:
        with _open(urllib.request.Request(url, headers=_headers(token))) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError(_("No se encontró el repositorio o todavía no tiene versiones publicadas. "
                                "Si el repositorio es privado, configure la clave de acceso.")) from e
        if e.code in (401, 403):
            raise UpdateError(tr("GitHub rechazó la consulta ({c}). Revise la clave de acceso o intente más tarde.",
                                 c=e.code)) from e
        raise UpdateError(tr("Error de GitHub ({c}).", c=e.code)) from e
    except urllib.error.URLError as e:
        raise UpdateError(tr("Sin conexión con GitHub: {e}", e=e.reason)) from e
    except (OSError, ValueError) as e:
        raise UpdateError(tr("Sin conexión con GitHub: {e}", e=e)) from e


def _get_text(url: str, token: str = "", accept="application/octet-stream") -> str:
    data = _download_bytes(url, token, accept)
    return data.decode("utf-8", "replace")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _resolve(url: str, token: str, accept: str):
    """Para repositorios privados: pide el archivo con la clave sin seguir la redireccion; la descarga real
    (servidor de GitHub) se hace sin la clave."""
    if not token:
        return urllib.request.Request(url, headers=_headers("", accept))
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        r = opener.open(urllib.request.Request(url, headers=_headers(token, accept)), timeout=TIMEOUT)
        return r          # sin redireccion: el contenido viene directo
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
            return urllib.request.Request(e.headers["Location"], headers={"User-Agent": f"DeclaraFacilUSA/{__version__}"})
        raise


def _download_bytes(url, token="", accept="application/octet-stream") -> bytes:
    target = _resolve(url, token, accept)
    if isinstance(target, urllib.request.Request):
        with _open(target) as r:
            return r.read()
    with target as r:
        return r.read()


# ---------------------------------------------------------------------------- operaciones
def latest_release(cfg: UpdateConfig) -> Release:
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", cfg.repo or ""):
        raise UpdateError(_("Repositorio de actualizaciones no configurado (formato usuario/repositorio)."))
    tok = cfg.get_token()
    d = _get_json(f"{API}/repos/{cfg.repo}/releases/latest", tok)
    tag = d.get("tag_name", "")
    rel = Release(version=".".join(str(x) for x in parse_version(tag)), tag=tag, name=d.get("name") or tag,
                  notes=d.get("body") or "", published=(d.get("published_at") or "")[:10],
                  page_url=d.get("html_url") or f"https://github.com/{cfg.repo}/releases")
    sha_asset = None
    for a in d.get("assets", []):
        if ASSET_RE.match(a.get("name", "")):
            rel.asset_name, rel.size = a["name"], int(a.get("size") or 0)
            rel.asset_api_url, rel.asset_download_url = a.get("url", ""), a.get("browser_download_url", "")
    for a in d.get("assets", []):
        if rel.asset_name and a.get("name", "").lower() == rel.asset_name.lower() + ".sha256":
            sha_asset = a
    if sha_asset:
        try:
            txt = _get_text(sha_asset["url"] if tok else sha_asset["browser_download_url"], tok)
            m = re.search(r"\b[0-9a-fA-F]{64}\b", txt)
            rel.sha256 = m.group(0).lower() if m else ""
        except (UpdateError, urllib.error.URLError, OSError) as e:
            logger.warning("No se pudo leer la huella SHA-256 de %s; la descarga no se verificará: %s",
                           rel.asset_name, e)
            rel.sha256 = ""
    return rel


def check(cfg: UpdateConfig = None, save=True) -> Optional[Release]:
    """Devuelve la version publicada si es mas nueva que la instalada; si no, None."""
    cfg = cfg or load_config()
    rel = latest_release(cfg)
    cfg.last_check = datetime.now().isoformat(timespec="minutes")
    if save:
        try:
            save_config(cfg)
        except OSError as e:
            logger.warning("No se pudo guardar la configuración de actualizaciones: %s", e)
    return rel if is_newer(rel.version) else None


def download(rel: Release, cfg: UpdateConfig = None, progress: Callable[[int, int], None] = None,
             dest_dir: Path = None) -> Path:
    if not rel.asset_name:
        raise UpdateError(_("La versión publicada no incluye el instalador (Instalar_DeclaraFacilUSA_….exe)."))
    cfg = cfg or load_config()
    tok = cfg.get_token()
    dest_dir = Path(dest_dir or tempfile.mkdtemp(prefix="declarafacil_upd_"))
    dest = dest_dir / rel.asset_name
    url = rel.asset_api_url if tok else rel.asset_download_url
    try:
        target = _resolve(url, tok, "application/octet-stream")
        resp = _open(target, timeout=60) if isinstance(target, urllib.request.Request) else target
        total = int(resp.headers.get("Content-Length") or rel.size or 0)
        h = hashlib.sha256()
        got = 0
        with resp, open(dest, "wb") as fh:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
                h.update(chunk)
                got += len(chunk)
                if progress:
                    progress(got, total)
    except urllib.error.URLError as e:
        raise UpdateError(tr("No se pudo descargar la actualización: {e}", e=getattr(e, "reason", e))) from e
    except OSError as e:
        raise UpdateError(tr("No se pudo descargar la actualización: {e}", e=e)) from e
    if rel.size and got != rel.size:
        raise UpdateError(_("La descarga está incompleta. Intente de nuevo."))
    if rel.sha256 and h.hexdigest().lower() != rel.sha256:
        dest.unlink(missing_ok=True)
        raise UpdateError(_("El archivo descargado no coincide con su huella SHA-256; se descartó por seguridad."))
    return dest


def install(installer: Path):
    """Ejecuta el instalador en modo silencioso; al terminar vuelve a abrir la app (ver instalador/*.iss)."""
    if not sys.platform.startswith("win"):
        raise UpdateError(_("La instalación automática solo funciona en Windows."))
    flags = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(installer), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                     creationflags=flags, close_fds=True)


def notes_text(rel: Release, limit=4000) -> str:
    """Notas de la version en texto simple (sin marcas de Markdown)."""
    t = rel.notes or ""
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"^\s*[-*]\s+", "• ", t, flags=re.M)
    return t.strip()[:limit]


# ============================================================================ actualizacion por archivos (codigo)
# El repositorio de GitHub contiene el codigo y un manifiesto (actualizacion.json) con la huella SHA-256 de cada
# archivo de taxapp/, data/, docs/ y assets/. La app compara y descarga solo lo que cambio, en una carpeta nueva
# (%LOCALAPPDATA%\DeclaraFacilUSA\codigo\<version>); main.py la usa al reiniciar y vuelve a la anterior si falla.
import os  # noqa: E402
import shutil  # noqa: E402

BRANCH = "main"
MANIFEST = "actualizacion.json"
CODE_DIRS = ("taxapp", "data", "docs", "assets")


@dataclass
class CodeUpdate:
    version: str
    base: str
    notes: str
    published: str
    commit: str
    files: dict
    changed: list
    needs_installer: bool = False
    page_url: str = ""


def code_store() -> Path:
    d = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "DeclaraFacilUSA" / "codigo"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path() -> Path:
    return code_store() / "estado.json"


def load_state() -> dict:
    return data_loader.read_json(_state_path(), {})


def save_state(st: dict):
    _state_path().write_text(json.dumps(st, indent=1), encoding="utf-8")


def current_root() -> Path:
    return data_loader.app_dir()


def base_version() -> str:
    return os.environ.get("DECLARAFACIL_BASE_VERSION") or __version__


def rolled_back_version() -> str:
    return os.environ.get("DECLARAFACIL_ROLLBACK", "")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(256 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_rel(rel: str) -> bool:
    parts = Path(rel).parts
    return bool(parts) and parts[0] in CODE_DIRS and ".." not in parts and not Path(rel).is_absolute() \
        and ":" not in rel and not rel.startswith(("/", "\\"))


def _fetch(url: str, token: str = "", accept: str = "*/*") -> bytes:
    h = {"Accept": accept, "User-Agent": f"DeclaraFacilUSA/{__version__}"}
    if token:
        h["Authorization"] = f"token {token}"
    try:
        with _open(urllib.request.Request(url, headers=h), timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError(_("No se encontró el repositorio o todavía no tiene versiones publicadas. "
                                "Si el repositorio es privado, configure la clave de acceso.")) from e
        if e.code in (401, 403):
            raise UpdateError(tr("GitHub rechazó la consulta ({c}). Revise la clave de acceso o intente más tarde.",
                                 c=e.code)) from e
        raise UpdateError(tr("Error de GitHub ({c}).", c=e.code)) from e
    except urllib.error.URLError as e:
        raise UpdateError(tr("Sin conexión con GitHub: {e}", e=e.reason)) from e
    except OSError as e:
        raise UpdateError(tr("Sin conexión con GitHub: {e}", e=e)) from e


def _raw_file(repo: str, commit: str, rel: str, token: str = "") -> bytes:
    """Contenido de un archivo del repositorio en un commit exacto (raw.githubusercontent.com; si esa direccion
    estuviera bloqueada en la red, se usa la API de GitHub)."""
    try:
        return _fetch(f"https://raw.githubusercontent.com/{repo}/{commit}/{rel}", token)
    except UpdateError:
        return _fetch(f"{API}/repos/{repo}/contents/{rel}?ref={commit}", token, "application/vnd.github.raw")


def check_code(cfg: UpdateConfig = None) -> Optional[CodeUpdate]:
    """Version de codigo publicada en GitHub si es mas nueva que la que se esta usando; si no, None."""
    cfg = cfg or load_config()
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", cfg.repo or ""):
        raise UpdateError(_("Repositorio de actualizaciones no configurado (formato usuario/repositorio)."))
    tok = cfg.get_token()
    sha = _fetch(f"{API}/repos/{cfg.repo}/commits/{BRANCH}", tok, "application/vnd.github.sha").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise UpdateError(_("Respuesta inesperada de GitHub."))
    try:
        man = json.loads(_raw_file(cfg.repo, sha, MANIFEST, tok).decode("utf-8"))
    except ValueError as e:
        raise UpdateError(_("El manifiesto de actualización no es válido.")) from e
    ver = str(man.get("version", "0"))
    if not is_newer(ver) or ver in load_state().get("bad", []):
        return None
    files = {k: v for k, v in (man.get("files") or {}).items() if _safe_rel(k) and re.fullmatch(r"[0-9a-f]{64}",
                                                                                                str(v.get("sha256", "")))}
    root = current_root()
    changed = []
    for rel, info in files.items():
        p = root / rel
        if not p.is_file() or sha256_file(p) != info["sha256"]:
            changed.append(rel)
    return CodeUpdate(version=ver, base=str(man.get("base", "0")), notes=man.get("notes", ""),
                      published=str(man.get("published", ""))[:10], commit=sha, files=files, changed=changed,
                      needs_installer=is_newer(str(man.get("base", "0")), base_version()),
                      page_url=f"https://github.com/{cfg.repo}/commits/{BRANCH}")


def apply_code(upd: CodeUpdate, cfg: UpdateConfig = None, progress: Callable[[int, int], None] = None) -> Path:
    """Arma la carpeta de la version nueva: copia los archivos iguales y descarga solo los que cambiaron."""
    cfg = cfg or load_config()
    tok = cfg.get_token()
    store = code_store()
    tmp = store / (upd.version + ".tmp")
    dest = store / upd.version
    shutil.rmtree(tmp, ignore_errors=True)
    src = current_root()
    n = len(upd.files)
    for i, (rel, info) in enumerate(sorted(upd.files.items()), 1):
        target = tmp / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        local = src / rel
        if rel not in upd.changed and local.is_file():
            shutil.copyfile(local, target)
        else:
            data = _raw_file(cfg.repo, upd.commit, rel, tok)
            if hashlib.sha256(data).hexdigest() != info["sha256"]:
                shutil.rmtree(tmp, ignore_errors=True)
                raise UpdateError(tr("El archivo {f} no coincide con su huella SHA-256; actualización cancelada.", f=rel))
            target.write_bytes(data)
        if progress:
            progress(i, n)
    if not (tmp / "taxapp" / "__init__.py").is_file():
        shutil.rmtree(tmp, ignore_errors=True)
        raise UpdateError(_("El manifiesto de actualización no es válido."))
    (tmp / ".completo").write_text(upd.version, encoding="utf-8")
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    st = load_state()
    using_store = store.resolve() in current_root().resolve().parents
    st.update(active=upd.version, previous=current_root().name if using_store else None, trial=True, attempts=0)
    save_state(st)
    keep = {st.get("active"), st.get("previous")}
    for d in store.iterdir():
        if d.is_dir() and d.name not in keep:
            shutil.rmtree(d, ignore_errors=True)
    return dest


def confirm_code_ok():
    """La app arranco bien con el codigo actual: ya no hace falta volver atras."""
    try:
        st = load_state()
        if st.get("trial"):
            st.update(trial=False, attempts=0)
            save_state(st)
    except OSError as e:
        logger.warning("No se pudo confirmar que la versión actual arrancó bien: %s", e)


def restart():
    """Vuelve a abrir el programa (para usar el codigo nuevo)."""
    args = [sys.executable] + (sys.argv[1:] if is_installed_app() else [str(data_loader.app_dir() / "main.py")])
    subprocess.Popen(args, close_fds=True)


def check_any(cfg: UpdateConfig = None):
    """('code', CodeUpdate) | ('installer', Release) | None. Prefiere la actualizacion por archivos."""
    cfg = cfg or load_config()
    code_err = None
    try:
        cu = check_code(cfg)
    except UpdateError as e:
        cu, code_err = None, e
    if cu and not cu.needs_installer:
        return "code", cu
    try:
        rel = check(cfg)
    except UpdateError as e:
        logger.warning("No se pudo buscar el instalador nuevo: %s", e)
        rel = None
    if rel:
        return "installer", rel
    if cu and cu.needs_installer:
        raise UpdateError(tr("La versión {v} necesita el instalador completo, que todavía no está publicado.", v=cu.version))
    if code_err and not cu:
        raise code_err
    return None
