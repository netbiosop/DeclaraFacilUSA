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

    def test_guided_questions_not_opened_when_calculation_fails(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
            from taxapp import accounts
            from taxapp.gui import app as A
            from taxapp.gui import forms_view as F
            accounts.create_user("admin", "Admin", "admin", "Secreta123")
            win = A.App()
            self.addCleanup(win.destroy)
            user, _err = accounts.authenticate("admin", "Secreta123")
            win.login_ok(user)
            win.new_return(2025)
            win.show_workspace("forms")
            win.update()
            view = win.workspace.screens["forms"]
            with mock.patch.object(A, "compute_all", side_effect=ValueError("dañado")), \
                    mock.patch.object(A, "messagebox") as box, mock.patch.object(F, "GuidedQuestions") as wizard:
                view.open_wizard()
            wizard.assert_not_called()
            box.showerror.assert_called_once()

    def test_shortcut_ignored_while_modal_dialog_is_open(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
            from taxapp import accounts
            from taxapp.gui import app as A
            accounts.create_user("admin", "Admin", "admin", "Secreta123")
            win = A.App()
            self.addCleanup(win.destroy)
            user, _err = accounts.authenticate("admin", "Secreta123")
            win.login_ok(user)
            win.update()
            action = mock.Mock()
            win.grab_set()
            win._shortcut(action)
            action.assert_not_called()
            win.grab_release()
            win._shortcut(action)
            action.assert_called_once()

    def test_open_or_new_refused_while_edit_dialog_is_open_without_grab(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
            from taxapp import accounts
            from taxapp.models import W2
            from taxapp.gui import app as A
            from taxapp.gui import widgets as W
            accounts.create_user("admin", "Admin", "admin", "Secreta123")
            win = A.App()
            self.addCleanup(win.destroy)
            user, _err = accounts.authenticate("admin", "Secreta123")
            win.login_ok(user)
            win.new_return(2025)
            client_a = win.ret
            dialog = W.Dialog(win, "W-2", W2(), lambda f: None, lambda o: client_a.w2s.append(o))
            win.update()
            dialog.grab_release()  # p. ej. el ✦ de la IA suelta el grab para usar el asistente
            with mock.patch.object(A, "messagebox"):
                win._shortcut(lambda: win.new_return(2025))
            self.assertIs(win.ret, client_a)
            dialog.destroy()
            win._shortcut(lambda: win.new_return(2025))
            self.assertIsNot(win.ret, client_a)

    def test_final_button_after_draft_checks_required_data(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
            from taxapp import accounts
            from taxapp.gui import app as A
            from taxapp.gui import forms_view as F
            accounts.create_user("admin", "Admin", "admin", "Secreta123")
            win = A.App()
            self.addCleanup(win.destroy)
            user, _err = accounts.authenticate("admin", "Secreta123")
            win.login_ok(user)
            win.new_return(2025)  # sin SSN ni dirección: faltan datos obligatorios
            win.show_workspace("forms")
            win.update()
            view = win.workspace.screens["forms"]
            view.last = mock.Mock(draft=True)
            with mock.patch.object(F, "PackageDialog") as package:
                view._show_last()
            on_final = package.call_args.kwargs["on_final"]
            with mock.patch.object(F, "messagebox") as box, mock.patch.object(view, "generate") as generate:
                box.askyesno.return_value = False
                on_final()
            generate.assert_not_called()
            box.askyesno.assert_called_once()

    def test_final_button_of_previous_client_does_nothing_after_switching(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
            from taxapp import accounts
            from taxapp.gui import app as A
            from taxapp.gui import forms_view as F
            accounts.create_user("admin", "Admin", "admin", "Secreta123")
            win = A.App()
            self.addCleanup(win.destroy)
            user, _err = accounts.authenticate("admin", "Secreta123")
            win.login_ok(user)
            win.new_return(2025)
            win.show_workspace("forms")
            win.update()
            view = win.workspace.screens["forms"]
            view.last = mock.Mock(draft=True)
            with mock.patch.object(F, "PackageDialog") as package:
                view._show_last()
            on_final = package.call_args.kwargs["on_final"]
            win.new_return(2026)
            with mock.patch.object(F, "messagebox") as box, mock.patch.object(view, "generate") as generate:
                on_final()
            generate.assert_not_called()
            box.askyesno.assert_not_called()

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
