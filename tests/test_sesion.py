"""Cerrar sesión no deja la declaración del usuario anterior en pantalla (requiere tkinter y pantalla)."""
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

try:
    import tkinter
    tkinter.Tk().destroy()
    HAS_DISPLAY = True
except ImportError:
    HAS_DISPLAY = False
except tkinter.TclError:
    HAS_DISPLAY = False


@unittest.skipUnless(HAS_DISPLAY, "tkinter o pantalla no disponible")
class LogoutTests(unittest.TestCase):
    def test_logout_destroys_workspace(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
            from taxapp import accounts
            from taxapp.gui import app as A
            accounts.create_user("admin", "Admin", "admin", "Secreta123")
            win = A.App()
            self.addCleanup(win.destroy)
            user, _err = accounts.authenticate("admin", "Secreta123")
            win.login_ok(user)
            win.new_return(2025)
            win.update()
            workspace = win.workspace
            win.dirty = False
            win.logout()
            win.update()
            self.assertFalse(workspace.winfo_exists())


if __name__ == "__main__":
    unittest.main()
