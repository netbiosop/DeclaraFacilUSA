"""Pruebas de actualizaciones (sin red) / Updater tests (no network)."""
import hashlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from taxapp import updater as U  # noqa: E402

EXE = b"MZ" + b"x" * 5000
SHA = hashlib.sha256(EXE).hexdigest()


class Resp:
    def __init__(self, data: bytes, headers=None):
        self.buf = io.BytesIO(data)
        self.headers = headers or {"Content-Length": str(len(data))}

    def read(self, n=-1):
        return self.buf.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def release_json(tag="v9.1.0", with_sha=True):
    assets = [{"name": f"Instalar_DeclaraFacilUSA_{tag[1:]}.exe", "size": len(EXE),
               "url": "https://api.github.com/repos/o/r/releases/assets/1",
               "browser_download_url": f"https://github.com/o/r/releases/download/{tag}/Instalar_DeclaraFacilUSA_{tag[1:]}.exe"}]
    if with_sha:
        assets.append({"name": assets[0]["name"] + ".sha256", "size": 80,
                       "url": "https://api.github.com/repos/o/r/releases/assets/2",
                       "browser_download_url": assets[0]["browser_download_url"] + ".sha256"})
    return {"tag_name": tag, "name": f"DeclaraFacil USA {tag}", "body": "## Novedades\n- **Algo** nuevo",
            "published_at": "2027-01-10T12:00:00Z", "html_url": f"https://github.com/o/r/releases/tag/{tag}",
            "assets": assets}


def fake_urlopen(rel):
    def _open(req, timeout=None, context=None):
        url = req.full_url if hasattr(req, "full_url") else req
        if url.endswith("/releases/latest"):
            return Resp(json.dumps(rel).encode())
        if url.endswith(".sha256"):
            return Resp(f"{SHA}  file.exe\n".encode())
        if url.endswith(".exe"):
            return Resp(EXE)
        raise AssertionError(url)
    return _open


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"USERPROFILE": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()


class VersionTests(unittest.TestCase):
    def test_parse_and_compare(self):
        self.assertEqual(U.parse_version("v1.4"), (1, 4, 0))
        self.assertEqual(U.parse_version("1.3.10"), (1, 3, 10))
        self.assertTrue(U.is_newer("v1.3.10", "1.3.9"))
        self.assertFalse(U.is_newer("1.3.0", "1.3.0"))
        self.assertFalse(U.is_newer("v1.2.9", "1.3.0"))

    def test_notes_text(self):
        r = U.Release("1", "v1", "n", "## Título\n- **Uno**\n* dos", "", "")
        self.assertEqual(U.notes_text(r), "Título\n• Uno\n• dos")


class ConfigTests(Base):
    def test_defaults_and_token(self):
        cfg = U.load_config()
        self.assertEqual(cfg.repo, "netbiosop/DeclaraFacilUSA")
        cfg.set_token("ghp_secreto")
        self.assertNotIn("ghp_secreto", cfg.token)
        U.save_config(cfg)
        self.assertEqual(U.load_config().get_token(), "ghp_secreto")

    def test_bad_repo(self):
        with self.assertRaises(U.UpdateError):
            U.latest_release(U.UpdateConfig(repo="sin-barra"))


class CheckDownloadTests(Base):
    def test_check_newer_and_download(self):
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen(release_json())):
            rel = U.check(U.UpdateConfig(repo="o/r"), save=False)
            self.assertIsNotNone(rel)
            self.assertEqual((rel.version, rel.sha256, rel.size), ("9.1.0", SHA, len(EXE)))
            seen = []
            path = U.download(rel, U.UpdateConfig(repo="o/r"), progress=lambda g, t: seen.append((g, t)),
                              dest_dir=pathlib.Path(self.tmp.name))
        self.assertEqual(path.read_bytes(), EXE)
        self.assertEqual(seen[-1], (len(EXE), len(EXE)))

    def test_same_version_is_none(self):
        from taxapp import __version__
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen(release_json("v" + __version__))):
            self.assertIsNone(U.check(U.UpdateConfig(repo="o/r"), save=False))

    def test_bad_hash_rejected(self):
        rel = U.Release("9.1.0", "v9.1.0", "n", "", "", "", asset_name="Instalar_DeclaraFacilUSA_9.1.0.exe",
                        asset_download_url="https://x/Instalar_DeclaraFacilUSA_9.1.0.exe", size=len(EXE), sha256="0" * 64)
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen({})):
            with self.assertRaises(U.UpdateError):
                U.download(rel, U.UpdateConfig(repo="o/r"), dest_dir=pathlib.Path(self.tmp.name))
        self.assertFalse((pathlib.Path(self.tmp.name) / rel.asset_name).exists())

    def test_missing_installer_asset(self):
        rj = release_json()
        rj["assets"] = []
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen(rj)):
            rel = U.latest_release(U.UpdateConfig(repo="o/r"))
        with self.assertRaises(U.UpdateError):
            U.download(rel, U.UpdateConfig(repo="o/r"))

    def test_http_errors(self):
        for code in (404, 403):
            err = urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(b"{}"))
            with mock.patch("urllib.request.urlopen", side_effect=err):
                with self.assertRaises(U.UpdateError) as cm:
                    U.check(U.UpdateConfig(repo="o/r"), save=False)
                self.assertTrue(str(cm.exception))
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            with self.assertRaises(U.UpdateError):
                U.check(U.UpdateConfig(repo="o/r"), save=False)

    def test_private_repo_redirect_without_token(self):
        """Repositorio privado: la clave va a api.github.com y NO al servidor de descarga."""
        cfg = U.UpdateConfig(repo="o/r")
        cfg.set_token("ghp_x")
        calls = []

        class Opener:
            def open(self, req, timeout=None):
                calls.append(("api", req.full_url, req.get_header("Authorization")))
                raise urllib.error.HTTPError(req.full_url, 302, "Found", {"Location": "https://objects.example/exe"}, None)

        def plain(req, timeout=None, context=None):
            calls.append(("cdn", req.full_url, req.get_header("Authorization")))
            return Resp(EXE)
        rel = U.Release("9.1.0", "v9.1.0", "n", "", "", "", asset_name="Instalar_DeclaraFacilUSA_9.1.0.exe",
                        asset_api_url="https://api.github.com/repos/o/r/releases/assets/1", size=len(EXE))
        with mock.patch("urllib.request.build_opener", return_value=Opener()), \
                mock.patch("urllib.request.urlopen", side_effect=plain):
            p = U.download(rel, cfg, dest_dir=pathlib.Path(self.tmp.name))
        self.assertEqual(p.read_bytes(), EXE)
        self.assertEqual(calls[0], ("api", "https://api.github.com/repos/o/r/releases/assets/1", "Bearer ghp_x"))
        self.assertEqual(calls[1], ("cdn", "https://objects.example/exe", None))

    def test_install_command(self):
        with mock.patch.object(U.sys, "platform", "win32"), mock.patch("subprocess.Popen") as pop:
            with mock.patch.object(U.subprocess, "Popen") as pop2:
                U.install(pathlib.Path("C:/t/Instalar.exe"))
        args = (pop2.call_args or pop.call_args)[0][0]
        self.assertIn("/SILENT", args)
        self.assertIn("/CLOSEAPPLICATIONS", args)


if __name__ == "__main__":
    unittest.main()


# ============================================================================ actualizacion por archivos
import importlib.util  # noqa: E402
import shutil  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


GEN = load_module("generar_manifiesto", ROOT / "herramientas" / "generar_manifiesto.py")


def make_tree(base: pathlib.Path, version="1.4.0", extra=b"x = 1\n"):
    (base / "taxapp").mkdir(parents=True)
    (base / "taxapp" / "__init__.py").write_text(f'__version__ = "{version}"\n__base__ = "1.4.0"\n', encoding="utf-8")
    (base / "taxapp" / "mod.py").write_bytes(extra)
    (base / "data").mkdir()
    (base / "data" / "t.json").write_text("{}", encoding="utf-8")
    (base / "taxapp" / "__pycache__").mkdir()
    (base / "taxapp" / "__pycache__" / "x.pyc").write_bytes(b"junk")


class CodeUpdateTests(Base):
    def setUp(self):
        super().setUp()
        self.env2 = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.tmp.name})
        self.env2.start()
        self.cur = pathlib.Path(self.tmp.name) / "actual"
        make_tree(self.cur, "1.4.0")
        self.new = pathlib.Path(self.tmp.name) / "nuevo"
        make_tree(self.new, "1.4.1", extra=b"x = 2\n")
        self.man = GEN.build(self.new)
        self.root_patch = mock.patch.object(U, "current_root", return_value=self.cur)
        self.root_patch.start()
        self.ver_patch = mock.patch.object(U, "__version__", "1.4.0")
        self.ver_patch.start()

    def tearDown(self):
        self.ver_patch.stop()
        self.root_patch.stop()
        self.env2.stop()
        super().tearDown()

    def fake_fetch(self, fetched):
        sha = "a" * 40
        man = self.man

        def f(url, token="", accept="*/*"):
            fetched.append(url)
            if "/commits/" in url:
                return sha.encode()
            if url.endswith("/actualizacion.json"):
                return json.dumps(man).encode()
            rel = url.split(f"/{sha}/", 1)[1]
            return (self.new / rel).read_bytes()
        return f

    def test_manifest(self):
        self.assertEqual((self.man["version"], self.man["base"]), ("1.4.1", "1.4.0"))
        self.assertEqual(sorted(self.man["files"]), ["data/t.json", "taxapp/__init__.py", "taxapp/mod.py"])

    def test_check_and_apply_only_changed(self):
        fetched = []
        with mock.patch.object(U, "_fetch", side_effect=self.fake_fetch(fetched)):
            upd = U.check_code(U.UpdateConfig(repo="o/r"))
            self.assertEqual(sorted(upd.changed), ["taxapp/__init__.py", "taxapp/mod.py"])
            self.assertFalse(upd.needs_installer)
            fetched.clear()
            dest = U.apply_code(upd, U.UpdateConfig(repo="o/r"))
        self.assertEqual(sorted(u.rsplit("/", 2)[-2] + "/" + u.rsplit("/", 1)[-1] for u in fetched),
                         ["taxapp/__init__.py", "taxapp/mod.py"])           # data/t.json no se descargo
        self.assertEqual((dest / "taxapp" / "mod.py").read_bytes(), b"x = 2\n")
        self.assertTrue((dest / ".completo").exists())
        st = U.load_state()
        self.assertEqual((st["active"], st["trial"], st["attempts"]), ("1.4.1", True, 0))
        U.confirm_code_ok()
        self.assertFalse(U.load_state()["trial"])

    def test_bad_hash_aborts(self):
        self.man["files"]["taxapp/mod.py"]["sha256"] = "0" * 64
        with mock.patch.object(U, "_fetch", side_effect=self.fake_fetch([])):
            upd = U.check_code(U.UpdateConfig(repo="o/r"))
            with self.assertRaises(U.UpdateError):
                U.apply_code(upd, U.UpdateConfig(repo="o/r"))
        self.assertFalse((U.code_store() / "1.4.1").exists())

    def test_unsafe_paths_ignored(self):
        self.man["files"]["../../evil.py"] = {"sha256": "1" * 64, "size": 1}
        self.man["files"]["C:/x.py"] = {"sha256": "1" * 64, "size": 1}
        with mock.patch.object(U, "_fetch", side_effect=self.fake_fetch([])):
            upd = U.check_code(U.UpdateConfig(repo="o/r"))
        self.assertEqual(sorted(upd.files), ["data/t.json", "taxapp/__init__.py", "taxapp/mod.py"])

    def test_needs_installer_and_check_any(self):
        self.man["base"] = "2.0.0"
        with mock.patch.object(U, "_fetch", side_effect=self.fake_fetch([])), \
                mock.patch.object(U, "check", return_value=None):
            upd = U.check_code(U.UpdateConfig(repo="o/r"))
            self.assertTrue(upd.needs_installer)
            with self.assertRaises(U.UpdateError):
                U.check_any(U.UpdateConfig(repo="o/r"))
        self.man["base"] = "1.4.0"
        with mock.patch.object(U, "_fetch", side_effect=self.fake_fetch([])):
            kind, upd = U.check_any(U.UpdateConfig(repo="o/r"))
        self.assertEqual((kind, upd.version), ("code", "1.4.1"))

    def test_same_or_bad_version_none(self):
        self.man["version"] = "1.4.0"
        with mock.patch.object(U, "_fetch", side_effect=self.fake_fetch([])):
            self.assertIsNone(U.check_code(U.UpdateConfig(repo="o/r")))
        self.man["version"] = "1.4.1"
        U.save_state({"bad": ["1.4.1"]})
        with mock.patch.object(U, "_fetch", side_effect=self.fake_fetch([])):
            self.assertIsNone(U.check_code(U.UpdateConfig(repo="o/r")))


class BootstrapTests(Base):
    """main.choose_code_root: elige el codigo actualizado y vuelve atras si no arranco."""

    def setUp(self):
        super().setUp()
        self.env2 = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.tmp.name})
        self.env2.start()
        self.main = load_module("main_boot", ROOT / "main.py")
        self.bundled = pathlib.Path(self.tmp.name) / "meipass"
        make_tree(self.bundled, "1.4.0")
        self.store = pathlib.Path(self.main._store())
        make_tree(self.store / "1.4.1", "1.4.1")
        (self.store / "1.4.1" / ".completo").write_text("1.4.1")
        self.state = self.store / "estado.json"
        self.state.write_text(json.dumps({"active": "1.4.1", "previous": None, "trial": True, "attempts": 0}))
        self.main.FROZEN = True
        sys._MEIPASS = str(self.bundled)

    def tearDown(self):
        del sys._MEIPASS
        self.env2.stop()
        super().tearDown()

    def test_uses_updated_then_rolls_back(self):
        root, note = self.main.choose_code_root()
        self.assertEqual((pathlib.Path(root).name, note), ("1.4.1", None))
        self.assertEqual(json.loads(self.state.read_text())["attempts"], 1)
        root, note = self.main.choose_code_root()                 # no confirmo -> volver a la base
        self.assertEqual((pathlib.Path(root), note), (self.bundled, "1.4.1"))
        st = json.loads(self.state.read_text())
        self.assertEqual((st["active"], st["bad"]), (None, ["1.4.1"]))

    def test_confirmed_stays(self):
        self.state.write_text(json.dumps({"active": "1.4.1", "trial": False}))
        for _ in range(3):
            root, note = self.main.choose_code_root()
            self.assertEqual(pathlib.Path(root).name, "1.4.1")

    def test_older_than_base_ignored(self):
        (self.bundled / "taxapp" / "__init__.py").write_text('__version__ = "1.5.0"\n', encoding="utf-8")
        self.state.write_text(json.dumps({"active": "1.4.1", "trial": False}))
        root, _n = self.main.choose_code_root()
        self.assertEqual(pathlib.Path(root), self.bundled)

    def test_incomplete_ignored(self):
        (self.store / "1.4.1" / ".completo").unlink()
        self.state.write_text(json.dumps({"active": "1.4.1", "trial": False}))
        root, _n = self.main.choose_code_root()
        self.assertEqual(pathlib.Path(root), self.bundled)

    def test_finder_loads_updated_package(self):
        root = self.store / "1.4.1"
        code = ("import sys; sys.path.insert(0, %r); import main_boot_x as m; m.use_code_root(%r); "
                "import taxapp, taxapp.mod; print(taxapp.__version__, taxapp.mod.x)")
        shutil.copy(ROOT / "main.py", pathlib.Path(self.tmp.name) / "main_boot_x.py")
        import subprocess
        out = subprocess.run([sys.executable, "-c", code % (self.tmp.name, str(root))], capture_output=True, text=True,
                             cwd=str(ROOT))
        self.assertEqual(out.stdout.strip(), "1.4.1 1", out.stderr)
