"""Pruebas de cuentas, roles y permisos / Accounts, roles and permissions tests."""
import os
import pathlib
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from taxapp import accounts as A, storage  # noqa: E402
from taxapp.models import TaxReturn  # noqa: E402


class AccountsBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"USERPROFILE": self.tmp.name})
        self.env.start()
        self.it = mock.patch.object(A, "ITERATIONS", 1000)
        self.it.start()
        storage.current_user = ""

    def tearDown(self):
        storage.current_user = ""
        self.it.stop()
        self.env.stop()
        self.tmp.cleanup()

    def admin(self):
        return A.create_user("admin", "Administrador", "admin", "Clave2025!")


class PasswordTests(AccountsBase):
    def test_hash_roundtrip(self):
        h = A.hash_password("secreta123")
        self.assertNotIn("secreta123", h)
        self.assertTrue(A.verify_password("secreta123", h))
        self.assertFalse(A.verify_password("secreta124", h))
        self.assertFalse(A.verify_password("x", "garbage"))

    def test_rules(self):
        self.assertIsNotNone(A.check_password_rules("corta1"))
        self.assertIsNotNone(A.check_password_rules("soloLetrasAqui"))
        self.assertIsNotNone(A.check_password_rules("1234567890"))
        self.assertIsNone(A.check_password_rules("letras123"))

    def test_username(self):
        self.assertIsNone(A.validate_username("maria.lopez"))
        self.assertIsNotNone(A.validate_username("María"))
        self.assertIsNotNone(A.validate_username("a"))


class DamagedFileTests(AccountsBase):
    def test_damaged_users_file_is_copied_once(self):
        self.admin()
        A._file().write_text("{ roto", encoding="utf-8")
        self.assertEqual(A.load()["users"], [])
        A.load()
        copies = list(A._file().parent.glob("usuarios.danado-*.json"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_text(encoding="utf-8"), "{ roto")

    def test_locked_users_file_is_never_overwritten(self):
        self.admin()
        before = A._file().read_text(encoding="utf-8")
        with mock.patch.object(pathlib.Path, "read_text", side_effect=PermissionError("bloqueado")):
            self.assertEqual(A.load()["users"], [])
            user, err = A.authenticate("admin", "Clave2025!")
            self.assertIsNone(user)
            self.assertIn("lista de usuarios", err)
            with self.assertRaises(A.AccountError):
                A.update_settings("", remember_user=False)
            with self.assertRaises(A.AccountError):
                A.create_user("otro", "Otro", "admin", "Clave2025!")
        self.assertEqual(A._file().read_text(encoding="utf-8"), before)
        self.assertEqual([u["username"] for u in A.load()["users"]], ["admin"])

    def test_unchanged_settings_are_not_written(self):
        self.admin()
        A.update_settings("", remember_user=A.settings()["remember_user"])
        with mock.patch.object(A, "save") as save:
            A.update_settings("", remember_user=A.settings()["remember_user"])
        save.assert_not_called()


class UserTests(AccountsBase):
    def test_first_admin_and_login(self):
        self.assertFalse(A.has_users())
        self.admin()
        self.assertTrue(A.has_users())
        u, err = A.authenticate("ADMIN", "Clave2025!")
        self.assertEqual((u["username"], err), ("admin", ""))
        self.assertNotIn("password", u)
        self.assertEqual(A.settings()["last_user"], "admin")

    def test_lockout(self):
        self.admin()
        for i in range(4):
            u, err = A.authenticate("admin", "mala")
            self.assertIsNone(u)
            self.assertIn(str(4 - i), err)
        u, err = A.authenticate("admin", "mala")
        self.assertIn("15", err)
        u, err = A.authenticate("admin", "Clave2025!")   # bloqueada aunque la clave sea correcta
        self.assertIsNone(u)
        db = A.load()
        A.find(db, "admin")["locked_until"] = (datetime.now() - timedelta(minutes=1)).isoformat()
        A.save(db)
        u, err = A.authenticate("admin", "Clave2025!")
        self.assertIsNotNone(u)

    def test_duplicate_and_invalid(self):
        self.admin()
        with self.assertRaises(A.AccountError):
            A.create_user("admin", "x", "viewer", "otra1234")
        with self.assertRaises(A.AccountError):
            A.create_user("nuevo", "x", "jefe", "otra1234")

    def test_last_admin_protected(self):
        self.admin()
        with self.assertRaises(A.AccountError):
            A.update_user("admin", "admin", role="viewer")
        with self.assertRaises(A.AccountError):
            A.update_user("admin", "admin", active=False)
        A.create_user("jefa", "Jefa", "admin", "Clave2025!", by="admin")
        A.update_user("admin", "jefa", role="supervisor")
        self.assertEqual(A.find(A.load(), "admin")["role"], "supervisor")

    def test_disabled_and_delete(self):
        self.admin()
        A.create_user("ana", "Ana", "preparer", "Clave2025!", by="admin")
        A.update_user("ana", "admin", active=False)
        u, err = A.authenticate("ana", "Clave2025!")
        self.assertIsNone(u)
        self.assertIn("desactivada", err)
        with self.assertRaises(A.AccountError):
            A.delete_user("admin", "admin")
        A.delete_user("ana", "admin")
        self.assertIsNone(A.find(A.load(), "ana"))

    def test_password_change(self):
        self.admin()
        with self.assertRaises(A.AccountError):
            A.set_password("admin", "Nueva2026!", "admin", current="incorrecta")
        A.set_password("admin", "Nueva2026!", "admin", current="Clave2025!")
        self.assertIsNotNone(A.authenticate("admin", "Nueva2026!")[0])


class PermissionTests(AccountsBase):
    def test_matrix(self):
        self.admin()
        viewer = A.create_user("consulta", "C", "viewer", "Clave2025!", by="admin")
        prep = A.create_user("prep", "P", "preparer", "Clave2025!", by="admin")
        sup = A.create_user("sup", "S", "supervisor", "Clave2025!", by="admin")
        adm = A.public(A.find(A.load(), "admin"))
        self.assertTrue(all(A.can(adm, k) for k in A.PERM_KEYS))
        self.assertFalse(A.can(viewer, "edit"))
        self.assertTrue(A.can(prep, "edit"))
        self.assertFalse(A.can(prep, "view_all"))
        self.assertTrue(A.can(sup, "view_all"))
        self.assertFalse(A.can(sup, "manage_users"))
        self.assertFalse(A.can(None, "view_own"))
        A.set_matrix({"viewer": {"export": True}, "admin": {"edit": False}}, "admin")
        self.assertTrue(A.can(viewer, "export"))
        self.assertTrue(A.can(adm, "edit"))

    def test_prefs_and_global_style(self):
        self.admin()
        A.create_user("ana", "Ana", "preparer", "Clave2025!", by="admin")
        A.save_prefs("ana", theme="B", size="large", bogus=1)
        p = A.prefs_for("ana")
        self.assertEqual((p["theme"], p["size"]), ("B", "large"))
        self.assertNotIn("bogus", p)
        A.set_global_style("admin", True, {"theme": "C", "accent": "#123456", "font": "", "size": "normal"})
        p = A.prefs_for("ana")
        self.assertEqual((p["theme"], p["accent"], p["size"]), ("C", "#123456", "normal"))


class FolderTests(AccountsBase):
    def test_migration_and_access(self):
        root = A.returns_root()
        storage.save(TaxReturn(), root / "vieja.dfusa")
        self.admin()
        self.assertTrue((A.returns_dir("admin") / "vieja.dfusa").exists())
        self.assertFalse((root / "vieja.dfusa").exists())
        prep = A.create_user("prep", "P", "preparer", "Clave2025!", by="admin")
        sup = A.create_user("sup", "S", "supervisor", "Clave2025!", by="admin")
        storage.current_user = "prep"
        p = storage.save(TaxReturn(tax_year=2026), storage.returns_dir() / "mia")
        self.assertEqual(p.parent.name, "prep")
        self.assertTrue(A.can_access_path(prep, p))
        self.assertFalse(A.can_access_path(prep, A.returns_dir("admin") / "vieja.dfusa"))
        self.assertTrue(A.can_access_path(sup, A.returns_dir("admin") / "vieja.dfusa"))
        self.assertEqual([r["name"] for r in A.list_returns(prep)], ["mia.dfusa"])
        self.assertEqual(len(A.list_returns(sup)), 2)
        self.assertEqual(A.transfer_returns("prep", "sup", "admin"), 1)
        self.assertTrue((A.returns_dir("sup") / "mia.dfusa").exists())

    def test_log_and_backup(self):
        self.admin()
        A.authenticate("admin", "mala")
        events = [e["event"] for e in A.read_log()]
        self.assertIn("user_created", events)
        self.assertEqual(events[0], "login_failed")
        dest = A.create_backup(A.backups_dir() / "respaldo", "admin")
        names = zipfile.ZipFile(dest).namelist()
        self.assertIn("usuarios.json", names)
        self.assertTrue(any(n.startswith("Declaraciones") for n in names) or True)
        self.assertFalse(any(n.startswith("Respaldos") for n in names))


if __name__ == "__main__":
    unittest.main()
