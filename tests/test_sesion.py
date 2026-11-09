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
    def test_failed_calculation_does_not_keep_previous_client_result(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
            from taxapp import accounts
            from taxapp.gui import app as A
            accounts.create_user("admin", "Admin", "admin", "Secreta123")
            win = A.App()
            self.addCleanup(win.destroy)
            user, _err = accounts.authenticate("admin", "Secreta123")
            win.login_ok(user)
            win.new_return(2025)
            win.recalc_now()
            self.assertIsNotNone(win.result)
            with mock.patch.object(A, "compute_all", side_effect=ValueError("archivo dañado")), \
                    mock.patch.object(A, "messagebox"), \
                    mock.patch.object(A.filedialog, "asksaveasfilename") as save_dialog:
                win._export("html")
            self.assertIsNone(win.result)
            save_dialog.assert_not_called()

    def test_shortcut_ignored_while_modal_dialog_is_open(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
            from taxapp import accounts
            from taxapp.gui import app as A
            accounts.create_user("admin", "Admin", "admin", "Secreta123")
            win = A.App()
            self.addCleanup(win.destroy)
            user, _err = accounts.authenticate("admin", "Secreta123")
            win.login_ok(user)
            action = mock.Mock()
            with mock.patch.object(win, "grab_current", return_value=win):
                win._shortcut(action)
            action.assert_not_called()
            with mock.patch.object(win, "grab_current", return_value=None):
                win._shortcut(action)
            action.assert_called_once()

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

    def test_new_return_clears_ai_chat_of_previous_client(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
            from taxapp import accounts
            from taxapp.gui import app as A
            from taxapp.gui.assistant import AssistantWindow
            accounts.create_user("admin", "Admin", "admin", "Secreta123")
            win = A.App()
            self.addCleanup(win.destroy)
            user, _err = accounts.authenticate("admin", "Secreta123")
            win.login_ok(user)
            win.new_return(2025)
            win.assistant_win = AssistantWindow(win)
            win.assistant_win.panel.history = [{"role": "user", "content": "cliente A"}]
            win.dirty = False
            win.new_return(2025)
            self.assertEqual(win.assistant_win.panel.history, [])

            panel = win.assistant_win.panel
            panel.history = [{"role": "user", "content": "cliente A"}]
            panel.busy = True
            win.dirty = False
            win.new_return(2025)
            panel._done("ok", "respuesta para A", [])
            self.assertEqual(panel.history, [])
            self.assertFalse(panel.busy)


if __name__ == "__main__":
    unittest.main()
