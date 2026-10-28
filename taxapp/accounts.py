"""Cuentas de usuario, roles y permisos / User accounts, roles and permissions.

- Archivo: Documentos\\DeclaraFacilUSA\\usuarios.json
- Contrasenas: PBKDF2-HMAC-SHA256 con sal aleatoria (nunca se guarda la contrasena).
- Roles (de mayor a menor): admin > supervisor > preparer > viewer; permisos editables por el administrador.
- Bloqueo tras N intentos fallidos; registro de actividad (actividad.log, JSON por linea).
- Cada usuario tiene su carpeta: Declaraciones\\<usuario>\\

Nota: esto controla el acceso dentro de la aplicacion; no cifra los archivos en el disco.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import data_loader
from .i18n import N_, _, tr

logger = logging.getLogger(__name__)

ITERATIONS = 240_000
ROLES = ["admin", "supervisor", "preparer", "viewer"]
ROLE_LABELS = {"admin": N_("Administrador"), "supervisor": N_("Supervisor"), "preparer": N_("Preparador"),
               "viewer": N_("Consulta")}
ROLE_HELP = {
    "admin": N_("Control total: usuarios, permisos, ajustes generales, claves de IA y tablas de impuestos."),
    "supervisor": N_("Ve y revisa las declaraciones de todos; exporta; ve respaldos y el registro."),
    "preparer": N_("Crea y edita sus propias declaraciones, exporta y usa la IA."),
    "viewer": N_("Solo puede ver sus declaraciones, sin editar ni exportar."),
}
PERMS = [
    ("view_own", N_("Ver sus declaraciones")),
    ("edit", N_("Crear y editar declaraciones")),
    ("view_all", N_("Ver declaraciones de todos")),
    ("export", N_("Exportar PDF / HTML")),
    ("use_ai", N_("Usar el asistente de IA")),
    ("ai_settings", N_("Claves y proveedor de IA")),
    ("tax_tables", N_("Tablas de impuestos y condados")),
    ("global_style", N_("Tema para todos los usuarios")),
    ("manage_users", N_("Crear usuarios y asignar roles")),
    ("backups", N_("Respaldos y registro de actividad")),
    ("updates", N_("Instalar actualizaciones del programa")),
]
PERM_KEYS = [k for k, _l in PERMS]
DEFAULT_MATRIX = {
    "admin": {k: True for k in PERM_KEYS},
    "supervisor": {"view_own": True, "edit": True, "view_all": True, "export": True, "use_ai": True,
                   "ai_settings": False, "tax_tables": False, "global_style": False, "manage_users": False, "backups": True,
                   "updates": False},
    "preparer": {"view_own": True, "edit": True, "view_all": False, "export": True, "use_ai": True,
                 "ai_settings": False, "tax_tables": False, "global_style": False, "manage_users": False, "backups": False,
                 "updates": False},
    "viewer": {"view_own": True, "edit": False, "view_all": False, "export": False, "use_ai": False,
               "ai_settings": False, "tax_tables": False, "global_style": False, "manage_users": False, "backups": False,
               "updates": False},
}
DEFAULT_SETTINGS = {"max_attempts": 5, "lock_minutes": 15, "min_password": 8, "idle_minutes": 0,
                    "force_style": False, "global_prefs": None, "remember_user": True, "last_user": "",
                    "preparer": None, "forms_editable": False}
PREPARER_FIELDS = ("name", "ptin", "firm", "firm_address", "firm_phone", "firm_ein", "self_employed")
DEFAULT_PREFS = {"theme": "A", "accent": "", "font": "", "size": "normal", "language": "",
                 "meter": "", "ai_docked": None, "autosave": 5}
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,31}$")


class AccountError(Exception):
    pass


# ---------------------------------------------------------------------------- almacenamiento
def _file() -> Path:
    return data_loader.user_dir() / "usuarios.json"


def _log_file() -> Path:
    return data_loader.user_dir() / "actividad.log"


# Marca de una lista cargada vacía porque el archivo no se pudo leer (bloqueado por el antivirus o la
# sincronización): guardarla borraría todas las cuentas, así que save() la rechaza.
_UNREADABLE = "_unreadable"
_UNREADABLE_MSG = N_("No se pudo leer la lista de usuarios. Cierre otros programas que la usen e intente de nuevo.")


def _empty() -> dict:
    return {"version": 1, "users": [], "matrix": copy.deepcopy(DEFAULT_MATRIX), "settings": dict(DEFAULT_SETTINGS)}


def _keep_damaged(p: Path, err: Exception):
    """Copia un usuarios.json ilegible antes de que el asistente de inicio lo reemplace por uno nuevo."""
    backup = p.with_name(f"usuarios.danado-{datetime.now():%Y%m%d-%H%M%S}.json")
    try:
        content = p.read_bytes()
        if any(prev.read_bytes() == content for prev in p.parent.glob("usuarios.danado-*.json")):
            return  # esta versión dañada ya tiene su copia
        shutil.copy2(p, backup)
        logger.error("usuarios.json ilegible (%s); se guardó una copia en %s", err, backup)
    except OSError as e:
        logger.error("usuarios.json ilegible (%s) y no se pudo copiar: %s", err, e)


def load() -> dict:
    p = _file()
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _empty()
    except ValueError as e:
        _keep_damaged(p, e)
        return _empty()
    except OSError as e:
        logger.error("No se pudo leer usuarios.json: %s", e)
        return {**_empty(), _UNREADABLE: True}
    d.setdefault("users", [])
    m = d.setdefault("matrix", {})
    for r in ROLES:
        m.setdefault(r, {})
        for k in PERM_KEYS:
            m[r].setdefault(k, DEFAULT_MATRIX[r][k])
    m["admin"] = {k: True for k in PERM_KEYS}     # el administrador siempre tiene todo
    s = d.setdefault("settings", {})
    for k, v in DEFAULT_SETTINGS.items():
        s.setdefault(k, v)
    for u in d["users"]:
        u.setdefault("prefs", {})
        u.setdefault("active", True)
        u.setdefault("failed", 0)
        u.setdefault("locked_until", "")
    return d


def save(db: dict):
    if db.get(_UNREADABLE):
        raise AccountError(_(_UNREADABLE_MSG))
    p = _file()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def has_users() -> bool:
    return bool(load()["users"])


# ---------------------------------------------------------------------------- contrasenas
def hash_password(password: str, iterations: int = None) -> str:
    it = iterations or ITERATIONS
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, it)
    return f"pbkdf2_sha256${it}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, it, salt, dk = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt), int(it))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


def check_password_rules(password: str, db: dict = None) -> Optional[str]:
    n = int((db or load())["settings"].get("min_password", 8))
    if len(password) < n:
        return tr("La contraseña debe tener al menos {n} caracteres.", n=n)
    if password.isdigit() or password.isalpha():
        return _("La contraseña debe combinar letras y números o símbolos.")
    return None


def normalize_username(name: str) -> str:
    return (name or "").strip().lower()


def validate_username(name: str) -> Optional[str]:
    if not USERNAME_RE.match(name):
        return _("Usuario inválido: use 2 a 32 letras minúsculas, números, punto, guion o guion bajo.")
    return None


# ---------------------------------------------------------------------------- usuarios
def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def find(db: dict, username: str) -> Optional[dict]:
    username = normalize_username(username)
    for u in db["users"]:
        if u["username"] == username:
            return u
    return None


def public(u: dict) -> dict:
    """Copia del usuario sin el hash de la contrasena (para la sesion)."""
    return {k: v for k, v in u.items() if k != "password"}


def active_admins(db: dict) -> int:
    return sum(1 for u in db["users"] if u["role"] == "admin" and u.get("active", True))


def create_user(username: str, name: str, role: str, password: str, by: str = "", db: dict = None) -> dict:
    db = db or load()
    username = normalize_username(username)
    err = validate_username(username) or check_password_rules(password, db)
    if err:
        raise AccountError(err)
    if role not in ROLES:
        raise AccountError(_("Rol inválido."))
    if find(db, username):
        raise AccountError(tr("Ya existe el usuario '{u}'.", u=username))
    first = not db["users"]
    u = {"username": username, "name": (name or username).strip(), "role": role, "password": hash_password(password),
         "active": True, "failed": 0, "locked_until": "", "created": _now(), "last_login": "", "prefs": {},
         "must_change": False}
    db["users"].append(u)
    save(db)
    returns_dir(username)
    if first:
        _migrate_legacy_returns(username)
    log("user_created", by or username, f"{username} ({role})")
    return public(u)


def update_user(username: str, by: str, name: str = None, role: str = None, active: bool = None) -> dict:
    db = load()
    u = find(db, username)
    if not u:
        raise AccountError(_("Usuario no encontrado."))
    demoting = (role is not None and role != "admin") or active is False
    if u["role"] == "admin" and u.get("active", True) and demoting and active_admins(db) <= 1:
        raise AccountError(_("Debe quedar al menos un Administrador activo."))
    if name is not None:
        u["name"] = name.strip() or u["username"]
    if role is not None:
        if role not in ROLES:
            raise AccountError(_("Rol inválido."))
        u["role"] = role
    if active is not None:
        u["active"] = bool(active)
        if active:
            u["failed"], u["locked_until"] = 0, ""
    save(db)
    log("user_updated", by, f"{username}: role={u['role']} active={u['active']}")
    return public(u)


def delete_user(username: str, by: str, transfer_to: str = None):
    db = load()
    u = find(db, username)
    if not u:
        raise AccountError(_("Usuario no encontrado."))
    if normalize_username(username) == normalize_username(by):
        raise AccountError(_("No puede eliminar su propia cuenta."))
    if u["role"] == "admin" and active_admins(db) <= 1:
        raise AccountError(_("Debe quedar al menos un Administrador activo."))
    if transfer_to:
        transfer_returns(username, transfer_to, by)
    db["users"].remove(u)
    save(db)
    log("user_deleted", by, username)


def set_password(username: str, new_password: str, by: str, current: str = None, must_change: bool = False):
    db = load()
    u = find(db, username)
    if not u:
        raise AccountError(_("Usuario no encontrado."))
    if current is not None and not verify_password(current, u["password"]):
        raise AccountError(_("La contraseña actual no es correcta."))
    err = check_password_rules(new_password, db)
    if err:
        raise AccountError(err)
    u["password"] = hash_password(new_password)
    u["failed"], u["locked_until"] = 0, ""
    u["must_change"] = bool(must_change)
    save(db)
    log("password_changed" if by == u["username"] else "password_reset", by, username)


def authenticate(username: str, password: str) -> Tuple[Optional[dict], str]:
    """Devuelve (usuario, "") o (None, mensaje)."""
    db = load()
    if db.get(_UNREADABLE):
        return None, _(_UNREADABLE_MSG)
    u = find(db, username)
    generic = _("Usuario o contraseña incorrectos.")
    if not u:
        log("login_failed", normalize_username(username), "unknown user")
        return None, generic
    if not u.get("active", True):
        log("login_failed", u["username"], "disabled")
        return None, _("Esta cuenta está desactivada. Hable con el administrador.")
    now = datetime.now()
    if u.get("locked_until"):
        try:
            until = datetime.fromisoformat(u["locked_until"])
        except ValueError:
            until = now
        if until > now:
            mins = max(1, int((until - now).total_seconds() // 60) + 1)
            return None, tr("Cuenta bloqueada por intentos fallidos. Intente en {m} min o pida ayuda al administrador.", m=mins)
        u["locked_until"], u["failed"] = "", 0
    if not verify_password(password, u["password"]):
        u["failed"] = int(u.get("failed", 0)) + 1
        s = db["settings"]
        left = int(s["max_attempts"]) - u["failed"]
        if left <= 0:
            u["locked_until"] = (now + timedelta(minutes=int(s["lock_minutes"]))).isoformat(timespec="seconds")
            u["failed"] = 0
            save(db)
            log("account_locked", u["username"], "")
            return None, tr("Demasiados intentos. Cuenta bloqueada {m} minutos.", m=s["lock_minutes"])
        save(db)
        log("login_failed", u["username"], "bad password")
        return None, generic + " " + tr("Intentos restantes: {n}.", n=left)
    u["failed"], u["locked_until"], u["last_login"] = 0, "", _now()
    db["settings"]["last_user"] = u["username"] if db["settings"].get("remember_user", True) else ""
    save(db)
    log("login", u["username"], "")
    return public(u), ""


def unlock(username: str, by: str):
    db = load()
    u = find(db, username)
    if u:
        u["failed"], u["locked_until"] = 0, ""
        save(db)
        log("user_unlocked", by, username)


def is_locked(u: dict) -> bool:
    try:
        return bool(u.get("locked_until")) and datetime.fromisoformat(u["locked_until"]) > datetime.now()
    except ValueError:
        return False


# ---------------------------------------------------------------------------- permisos y ajustes
def can(user: Optional[dict], perm: str, db: dict = None) -> bool:
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    m = (db or load())["matrix"]
    return bool(m.get(user.get("role"), {}).get(perm, False))


def set_matrix(matrix: Dict[str, Dict[str, bool]], by: str):
    db = load()
    for r in ROLES:
        if r == "admin":
            continue
        for k in PERM_KEYS:
            db["matrix"][r][k] = bool(matrix.get(r, {}).get(k, db["matrix"][r][k]))
        if db["matrix"][r]["edit"]:
            db["matrix"][r]["view_own"] = True
    save(db)
    log("permissions_changed", by, "")


def settings() -> dict:
    return dict(load()["settings"])


def update_settings(by: str, **kw):
    db = load()
    changed = {k: v for k, v in kw.items() if k in DEFAULT_SETTINGS and db["settings"].get(k) != v}
    if not changed:
        return
    db["settings"].update(changed)
    save(db)
    if set(changed) - {"last_user"}:
        log("settings_changed", by, ", ".join(sorted(changed)))


def prefs_for(username: str) -> dict:
    """Preferencias efectivas: las globales si el administrador impuso un estilo; si no, las del usuario."""
    db = load()
    u = find(db, username) or {}
    p = dict(DEFAULT_PREFS)
    p.update(u.get("prefs") or {})
    s = db["settings"]
    if s.get("force_style") and s.get("global_prefs"):
        for k in ("theme", "accent", "font", "size"):
            if k in s["global_prefs"]:
                p[k] = s["global_prefs"][k]
    return p


def save_prefs(username: str, **kw):
    db = load()
    u = find(db, username)
    if u:
        u.setdefault("prefs", {}).update({k: v for k, v in kw.items() if k in DEFAULT_PREFS})
        save(db)


def set_global_style(by: str, enabled: bool, prefs: dict = None):
    db = load()
    db["settings"]["force_style"] = bool(enabled)
    if prefs is not None:
        db["settings"]["global_prefs"] = {k: prefs.get(k) for k in ("theme", "accent", "font", "size")}
    save(db)
    log("global_style", by, "on" if enabled else "off")


# ---------------------------------------------------------------------------- carpetas de declaraciones
def returns_root() -> Path:
    d = data_loader.user_dir() / "Declaraciones"
    d.mkdir(parents=True, exist_ok=True)
    return d


def returns_dir(username: str) -> Path:
    d = returns_root() / normalize_username(username)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _migrate_legacy_returns(username: str):
    """Declaraciones de versiones anteriores (sin usuarios) pasan a la carpeta del primer administrador."""
    root = returns_root()
    dest = returns_dir(username)
    for f in root.glob("*.dfusa"):
        target = dest / f.name
        if not target.exists():
            shutil.move(str(f), str(target))


def can_access_path(user: dict, path) -> bool:
    try:
        p = Path(path).resolve()
    except OSError:
        return False
    if can(user, "view_all"):
        return True
    own = returns_dir(user["username"]).resolve()
    return own == p.parent or own in p.parents


def list_returns(user: dict) -> List[dict]:
    """Declaraciones visibles para el usuario: [{path, owner, name, modified}]."""
    if can(user, "view_all"):
        dirs = [d for d in returns_root().iterdir() if d.is_dir()]
    else:
        dirs = [returns_dir(user["username"])]
    out = []
    for d in dirs:
        for f in d.glob("*.dfusa"):
            try:
                mt = datetime.fromtimestamp(f.stat().st_mtime)
            except OSError:
                continue
            out.append({"path": str(f), "owner": d.name, "name": f.name, "modified": mt})
    out.sort(key=lambda x: x["modified"], reverse=True)
    return out


def transfer_returns(src: str, dst: str, by: str) -> int:
    a, b = returns_dir(src), returns_dir(dst)
    n = 0
    for f in list(a.glob("*.dfusa")):
        target = b / f.name
        i = 2
        while target.exists():
            target = b / f"{f.stem}_{i}{f.suffix}"
            i += 1
        shutil.move(str(f), str(target))
        n += 1
    log("returns_transferred", by, f"{src} -> {dst}: {n}")
    return n


# ---------------------------------------------------------------------------- registro y respaldos
def log(event: str, user: str, detail: str = ""):
    try:
        with open(_log_file(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"time": _now(), "user": user, "event": event, "detail": detail}, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning("No se pudo anotar en el registro de actividad (%s): %s", event, e)


EVENT_LABELS = {
    "login": N_("Inicio de sesión"), "logout": N_("Cierre de sesión"), "login_failed": N_("Intento fallido"),
    "account_locked": N_("Cuenta bloqueada"), "user_created": N_("Usuario creado"), "user_updated": N_("Usuario modificado"),
    "user_deleted": N_("Usuario eliminado"), "user_unlocked": N_("Usuario desbloqueado"),
    "password_changed": N_("Contraseña cambiada"), "password_reset": N_("Contraseña restablecida"),
    "permissions_changed": N_("Permisos modificados"), "settings_changed": N_("Ajustes generales modificados"),
    "global_style": N_("Estilo global"), "returns_transferred": N_("Declaraciones transferidas"),
    "return_saved": N_("Declaración guardada"), "return_opened": N_("Declaración abierta"),
    "return_exported": N_("Declaración exportada"), "backup_created": N_("Respaldo creado"),
    "idle_logout": N_("Cierre por inactividad"),
    "update_installed": N_("Actualización iniciada"),
    "forms_generated": N_("Formularios del IRS generados"),
}


def read_log(limit: int = 300) -> List[dict]:
    try:
        lines = _log_file().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in reversed(lines[-limit:]):
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def create_backup(dest, by: str) -> Path:
    """ZIP con declaraciones, usuarios, configuracion y registro."""
    base = data_loader.user_dir()
    dest = Path(dest)
    if dest.suffix.lower() != ".zip":
        dest = dest.with_suffix(".zip")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in base.rglob("*"):
            if p.is_file() and p.resolve() != dest.resolve() and p.suffix.lower() not in (".tmp",) \
                    and "Respaldos" not in p.relative_to(base).parts:
                z.write(p, p.relative_to(base))
    log("backup_created", by, dest.name)
    return dest


def backups_dir() -> Path:
    d = data_loader.user_dir() / "Respaldos"
    d.mkdir(parents=True, exist_ok=True)
    return d
