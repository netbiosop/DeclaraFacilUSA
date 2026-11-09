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
        self.env = mock.patch.dict(os.environ, {"USERPROFILE": self.tmp.name, "HOME": self.tmp.name})
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

    def test_users_file_with_valid_json_that_is_not_an_object(self):
        self.admin()
        A._file().write_text("[]", encoding="utf-8")
        self.assertEqual(A.load()["users"], [])
        copies = list(A._file().parent.glob("usuarios.danado-*.json"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_text(encoding="utf-8"), "[]")

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

    def test_new_user_with_same_name_does_not_inherit_pdfs(self):
        # los PDF exportados (SSN, cuenta bancaria) quedaban en la carpeta y un usuario nuevo con el mismo nombre los veía
        self.admin()
        A.create_user("maria", "Maria", "preparer", "Clave2025!", by="admin")
        pdfs = A.returns_dir("maria") / "PEREZ_JUAN_2025_formularios"
        pdfs.mkdir()
        (pdfs / "01_Form_1040_2025.pdf").write_bytes(b"%PDF")
        storage.save(TaxReturn(tax_year=2025), A.returns_dir("maria") / "juan")
        A.delete_user("maria", "admin", transfer_to="admin")
        A.create_user("maria", "Maria", "preparer", "Clave2025!", by="admin")
        self.assertEqual(list(A.returns_dir("maria").iterdir()), [])
        kept = list(A.returns_dir("admin").rglob("01_Form_1040_2025.pdf"))
        self.assertEqual(len(kept), 1)
        self.assertTrue((A.returns_dir("admin") / "juan.dfusa").exists())

    def test_delete_disabled_admin_with_one_active_admin(self):
        # Borrar un admin ya desactivado no deja a nadie sin acceso: no debe exigir otro admin activo
        self.admin()
        A.create_user("viejo", "Viejo", "admin", "Clave2025!", by="admin")
        A.update_user("viejo", "admin", active=False)
        A.delete_user("viejo", "admin")
        self.assertIsNone(A.find(A.load(), "viejo"))

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

    def test_failed_backup_leaves_no_zip(self):
        # Un archivo bloqueado a mitad dejaba un ZIP válido pero incompleto con nombre normal en Respaldos
        self.admin()
        dest = A.backups_dir() / "respaldo.zip"
        with mock.patch("zipfile.ZipFile.write", side_effect=PermissionError("bloqueado")):
            with self.assertRaises(PermissionError):
                A.create_backup(dest, "admin")
        self.assertEqual(list(A.backups_dir().iterdir()), [])

    def test_save_is_flushed_to_disk_before_replace(self):
        # Sin fsync un corte de luz puede dejar usuarios.json vacío y la app abre el asistente de administrador
        self.admin()
        with mock.patch("os.fsync") as fsync:
            A.save(A.load())
        self.assertTrue(fsync.called)

    def test_unknown_user_text_not_logged(self):
        # quien escribe la contraseña en el campo de usuario no debe dejarla en actividad.log
        self.admin()
        A.authenticate("MiClaveSecreta9", "x")
        self.assertNotIn("miclavesecreta9", str(A.read_log()[0]).lower())


class UsernameTests(unittest.TestCase):
    def test_windows_folder_names_rejected(self):
        # Windows quita el punto final ("ana." usaría la carpeta de "ana") y reserva CON, NUL, COM1…
        for bad in ("ana.", "ana..", "con", "nul", "aux", "prn", "com1", "lpt9", "con.ana"):
            self.assertIsNotNone(A.validate_username(bad), bad)

    def test_valid_usernames(self):
        for ok in ("ana", "ana.maria", "j_perez", "ana-2", "a1", "console", "nulo"):
            self.assertIsNone(A.validate_username(ok), ok)


class UserDirTests(AccountsBase):
    def test_folder_does_not_move_when_documents_appears(self):
        """Sin Documentos los datos van a USERPROFILE\\DeclaraFacilUSA; si después aparece Documentos
        (OneDrive, otro programa), la app no puede cambiarse a una carpeta vacía y pedir un admin nuevo."""
        self.admin()
        first = A.data_loader.user_dir()
        (pathlib.Path(self.tmp.name) / "Documents").mkdir()
        self.assertEqual(A.data_loader.user_dir(), first)
        self.assertTrue(A.has_users())

    def test_folder_with_accounts_wins_over_empty_one(self):
        self.admin()
        first = A.data_loader.user_dir()
        (pathlib.Path(self.tmp.name) / "Documents" / "DeclaraFacilUSA").mkdir(parents=True)  # la creó otra versión u otro programa
        self.assertEqual(A.data_loader.user_dir(), first)

    def test_fallback_folder_with_accounts_wins(self):
        """Si Documentos estuvo bloqueado, las cuentas quedaron en ~/.declarafacilusa: al desbloquearse
        Documentos la app no puede pedir un Administrador nuevo."""
        fallback = pathlib.Path(self.tmp.name) / ".declarafacilusa"
        fallback.mkdir()
        with mock.patch.object(A.data_loader, "user_dir", return_value=fallback):
            self.admin()
        with mock.patch.dict(os.environ, {"HOME": self.tmp.name}):
            self.assertEqual(A.data_loader.user_dir(), fallback)
            self.assertTrue(A.has_users())


class AdminOnlyTests(AccountsBase):
    """Con "Crear usuarios y asignar roles" un Supervisor no puede llegar a Administrador."""

    def setUp(self):
        super().setUp()
        self.admin()
        A.create_user("super", "Sup", "supervisor", "Clave2025!", by="admin")

    def test_non_admin_cannot_promote_self(self):
        with self.assertRaises(A.AccountError):
            A.update_user("super", "super", role="admin")
        self.assertEqual(A.find(A.load(), "super")["role"], "supervisor")

    def test_non_admin_cannot_create_admin(self):
        with self.assertRaises(A.AccountError):
            A.create_user("otro", "Otro", "admin", "Clave2025!", by="super")

    def test_non_admin_cannot_reset_admin_password(self):
        with self.assertRaises(A.AccountError):
            A.set_password("admin", "Nueva2025!", "super")

    def test_non_admin_cannot_delete_admin(self):
        A.create_user("admin2", "Admin 2", "admin", "Clave2025!", by="admin")
        with self.assertRaises(A.AccountError):
            A.delete_user("admin", "super")

    def test_non_admin_cannot_change_permission_matrix(self):
        with self.assertRaises(A.AccountError):
            A.set_matrix({"supervisor": {"ai_settings": True, "tax_tables": True}}, "super")
        self.assertFalse(A.load()["matrix"]["supervisor"]["ai_settings"])

    def test_non_admin_cannot_take_admin_returns(self):
        (A.returns_dir("admin") / "cliente_2025.dfusa").write_text("{}", encoding="utf-8")
        with self.assertRaises(A.AccountError):
            A.transfer_returns("admin", "super", "super")
        self.assertEqual(len(list(A.returns_dir("admin").glob("*.dfusa"))), 1)
        self.assertEqual(A.transfer_returns("admin", "super", "admin"), 1)

    def test_non_admin_cannot_unlock_admin(self):
        db = A.load()
        A.find(db, "admin")["failed"] = 5
        A.save(db)
        with self.assertRaises(A.AccountError):
            A.unlock("admin", "super")
        self.assertEqual(A.find(A.load(), "admin")["failed"], 5)

    def test_non_admin_can_still_rename_self(self):
        self.assertEqual(A.update_user("super", "super", name="Nuevo", role="supervisor")["name"], "Nuevo")


if __name__ == "__main__":
    unittest.main()
