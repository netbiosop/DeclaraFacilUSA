"""DeclaraFacil USA - punto de entrada / entry point.

Uso / Usage:
    python main.py                   -> abre la aplicacion / opens the app (menu principal / main menu)
    python main.py --pruebas|--test  -> pruebas / tests
    python main.py --lang en|es      -> elegir idioma / choose language (se guarda / saved)

Programa instalado (.exe): este archivo es la "base" fija. El codigo de la aplicacion (taxapp/), las tablas (data/),
la guia (docs/) y los iconos (assets/) se pueden actualizar archivo por archivo desde GitHub; las versiones
descargadas se guardan en %LOCALAPPDATA%\\DeclaraFacilUSA\\codigo\\<version> y aqui se elige cual usar. Si una version
nueva no arranca, se vuelve sola a la anterior.
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
FROZEN = bool(getattr(sys, "frozen", False))
if not FROZEN:
    sys.path.insert(0, BASE)


# ---------------------------------------------------------------------------- arranque con codigo actualizado
def _store():
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "DeclaraFacilUSA", "codigo")


def _read_version(root):
    try:
        with open(os.path.join(root, "taxapp", "__init__.py"), encoding="utf-8") as f:
            txt = f.read()
        v = re.search(r'__version__\s*=\s*"([^"]+)"', txt)
        b = re.search(r'__base__\s*=\s*"([^"]+)"', txt)
        return (v.group(1) if v else "0"), (b.group(1) if b else "0")
    except OSError:
        return "0", "0"


def _vt(v):
    n = [int(x) for x in re.findall(r"\d+", v or "")][:4]
    return tuple(n + [0] * (3 - min(3, len(n))))


def _load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(path, st):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(st, f, indent=1)
    except OSError:
        pass


def choose_code_root():
    """Devuelve la carpeta de codigo a usar (actualizada o la que viene con el programa)."""
    if not FROZEN:
        return BASE, None
    bundled = getattr(sys, "_MEIPASS", BASE)
    base_ver, _b = _read_version(bundled)
    os.environ["DECLARAFACIL_BASE_VERSION"] = base_ver
    store = _store()
    state_file = os.path.join(store, "estado.json")
    st = _load_state(state_file)
    note = None
    active = st.get("active")
    if active and st.get("trial"):
        if int(st.get("attempts", 0)) >= 1:          # la vez anterior no llego a confirmar que funciona
            st.setdefault("bad", []).append(active)
            note = active
            st.update(active=st.get("previous"), previous=None, trial=False, attempts=0)
            active = st["active"]
        else:
            st["attempts"] = int(st.get("attempts", 0)) + 1
        _save_state(state_file, st)
    if active:
        root = os.path.join(store, active)
        ver, need_base = _read_version(root)
        ok = (os.path.exists(os.path.join(root, ".completo")) and _vt(ver) > _vt(base_ver)
              and _vt(need_base) <= _vt(base_ver))
        if ok:
            return root, note
    return bundled, note


def use_code_root(root):
    """Hace que 'import taxapp' cargue desde la carpeta elegida (antes que la copia interna del .exe)."""
    import importlib.abc
    import importlib.machinery

    class _CodeFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name == "taxapp":
                return importlib.machinery.PathFinder.find_spec(name, [root])
            if name.startswith("taxapp."):
                return importlib.machinery.PathFinder.find_spec(name, path)
            return None

    sys.meta_path.insert(0, _CodeFinder())
    sys.dont_write_bytecode = True
    os.environ["DECLARAFACIL_CODE_ROOT"] = root


def _rollback_now(root):
    """El codigo actualizado fallo al cargar: marcarlo como malo y reiniciar con el anterior."""
    store = _store()
    state_file = os.path.join(store, "estado.json")
    st = _load_state(state_file)
    st.setdefault("bad", []).append(os.path.basename(root))
    st.update(active=st.get("previous"), previous=None, trial=False, attempts=0)
    _save_state(state_file, st)
    import subprocess
    subprocess.Popen([sys.executable] + sys.argv[1:])
    sys.exit(0)


# ---------------------------------------------------------------------------- programa
def run_tests():
    import unittest
    suite = unittest.defaultTestLoader.discover(os.path.join(BASE, "tests"))
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)


def main():
    if "--pruebas" in sys.argv or "--test" in sys.argv:
        run_tests()
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("ERROR: Tkinter no esta disponible / is not available. Instale / Install Python from "
              "https://www.python.org/downloads/ ('tcl/tk and IDLE' option).")
        sys.exit(1)
    if sys.platform.startswith("win"):
        try:  # texto nitido en pantallas de alta resolucion
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
        try:  # icono propio en la barra de tareas (no el de Python)
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DeclaraFacilUSA.App")
        except Exception:  # noqa: BLE001
            pass
    root, rolled_back = choose_code_root()
    updated = FROZEN and root != getattr(sys, "_MEIPASS", BASE)
    if updated:
        use_code_root(root)
    if rolled_back:
        os.environ["DECLARAFACIL_ROLLBACK"] = rolled_back
    try:
        if "--lang" in sys.argv:
            i = sys.argv.index("--lang")
            if i + 1 < len(sys.argv):
                from taxapp import i18n
                i18n.set_language(sys.argv[i + 1].lower())
        from taxapp.gui.app import main as run_gui
    except Exception:  # noqa: BLE001
        if updated:
            _rollback_now(root)
        raise
    run_gui()


if __name__ == "__main__":
    main()
