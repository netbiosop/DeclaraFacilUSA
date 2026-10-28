"""Pruebas del asistente de IA (sin red: urlopen simulado) / AI assistant tests (no network: mocked urlopen)."""
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

from taxapp import assistant as ai, i18n  # noqa: E402
from taxapp.engine import compute_all  # noqa: E402
from taxapp.models import TaxReturn, Person, Address, Dependent, W2  # noqa: E402


class FakeResp:
    def __init__(self, data):
        self.data = json.dumps(data).encode()

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def sample_return():
    r = TaxReturn(tax_year=2025, filing_status="mfj")
    r.taxpayer = Person(first_name="Juanito", last_name="Perezoso", ssn="123-45-6789", dob="1980-05-01")
    r.spouse = Person(first_name="Anabela", ssn="987-65-4321", dob="1958-01-01")
    r.address = Address(street="742 Evergreen Terrace", city="Baltimore", state="MD", zip="21201",
                        county="Baltimore City", phone="410-555-0199", email="juanito@example.com")
    r.dependents = [Dependent(first_name="Leonardo", ssn="111-22-3333", dob="2015-03-03")]
    r.w2s = [W2(employer="ACME Widgets", ein="12-3456789", box1_wages=85000, box2_fed_withheld=7000, state="MD",
                box17_state_withheld=3000)]
    return r


def cfg_for(provider, **kw):
    c = ai.AIConfig(provider=provider, **kw)
    c.set_key("sk-test-123")
    return c


class RedactionTests(unittest.TestCase):
    def test_no_personal_identifiers(self):
        r = sample_return()
        p = ai.system_prompt(r, compute_all(r), "Ingresos")
        for bad in ("Juanito", "Perezoso", "123-45-6789", "987-65", "Anabela", "Evergreen", "21201", "410-555",
                    "example.com", "ACME", "12-3456789", "Leonardo", "111-22"):
            self.assertNotIn(bad, p)
        for good in ("state MD", "Baltimore City", "$85,000", "Filing status: mfj", "Ages at year end: 45, 68"):
            self.assertIn(good, p)

    def test_without_data(self):
        r = sample_return()
        p = ai.system_prompt(r, compute_all(r), "", include_data=False)
        self.assertNotIn("$85,000", p)
        self.assertIn("chose not to share", p)

    def test_no_return(self):
        self.assertIn("No return is open", ai.system_prompt(None, None, ""))

    def test_language(self):
        prev = i18n.get_language()
        try:
            i18n.set_language("en", save=False)
            self.assertIn("Reply in English", ai.system_prompt(None, None, ""))
            i18n.set_language("es", save=False)
            self.assertIn("Reply in Spanish", ai.system_prompt(None, None, ""))
        finally:
            i18n.set_language(prev, save=False)

    def test_year_facts(self):
        self.assertIn("$31,500", ai.year_facts(2025))
        self.assertIn("$32,200", ai.year_facts(2026))


class KeyTests(unittest.TestCase):
    def test_roundtrip(self):
        enc = ai.protect("sk-secret")
        self.assertNotIn("sk-secret", enc)
        self.assertEqual(ai.unprotect(enc), "sk-secret")

    def test_env_fallback(self):
        c = ai.AIConfig(provider="openai")
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            self.assertEqual(c.get_key(), "env-key")
            self.assertTrue(c.is_ready())

    def test_ready(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(ai.AIConfig(provider="anthropic").is_ready())
            self.assertTrue(ai.AIConfig(provider="ollama").is_ready())
            self.assertFalse(ai.AIConfig(provider="compatible").is_ready())

    def test_save_load(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "ai_config.json"
            with mock.patch.object(ai, "_config_path", return_value=path):
                c = cfg_for("gemini", web_search=True)
                ai.save_config(c)
                self.assertNotIn("sk-test-123", path.read_text())
                c2 = ai.load_config()
                self.assertEqual((c2.provider, c2.web_search, c2.get_key()), ("gemini", True, "sk-test-123"))


class ProviderTests(unittest.TestCase):
    MSGS = [{"role": "user", "content": "hola"}]

    def call(self, cfg, response, web=False):
        with mock.patch("urllib.request.urlopen", return_value=FakeResp(response)) as m:
            out = ai.ask(cfg, "SYS", self.MSGS, web=web)
        req = m.call_args[0][0]
        return out, req, json.loads(req.data)

    def test_anthropic(self):
        resp = {"content": [{"type": "server_tool_use", "name": "web_search"},
                            {"type": "web_search_tool_result", "content": []},
                            {"type": "text", "text": "La deducción es $31,500.",
                             "citations": [{"url": "https://www.irs.gov/x", "title": "IRS"}]}]}
        (text, src), req, body = self.call(cfg_for("anthropic"), resp, web=True)
        self.assertEqual(text, "La deducción es $31,500.")
        self.assertEqual(src, [("IRS", "https://www.irs.gov/x")])
        self.assertEqual(req.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(req.get_header("X-api-key"), "sk-test-123")
        self.assertEqual(req.get_header("Anthropic-version"), "2023-06-01")
        self.assertEqual(body["model"], "claude-sonnet-5-5")
        self.assertEqual(body["system"], "SYS")
        self.assertEqual(body["tools"][0]["type"], "web_search_20250305")

    def test_openai(self):
        resp = {"output": [{"type": "web_search_call"},
                           {"type": "message", "content": [{"type": "output_text", "text": "Respuesta",
                            "annotations": [{"type": "url_citation", "url": "https://irs.gov/a", "title": "A"}]}]}]}
        (text, src), req, body = self.call(cfg_for("openai"), resp, web=True)
        self.assertEqual((text, src), ("Respuesta", [("A", "https://irs.gov/a")]))
        self.assertEqual(req.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(req.get_header("Authorization"), "Bearer sk-test-123")
        self.assertEqual(body["instructions"], "SYS")
        self.assertEqual(body["tools"], [{"type": "web_search"}])

    def test_gemini(self):
        resp = {"candidates": [{"content": {"parts": [{"text": "Hola "}, {"text": "mundo"}]},
                                "groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://x.gov", "title": "X"}}]}}]}
        (text, src), req, body = self.call(cfg_for("gemini"), resp, web=True)
        self.assertEqual((text, src), ("Hola mundo", [("X", "https://x.gov")]))
        self.assertIn("/models/gemini-3.8-flash:generateContent", req.full_url)
        self.assertEqual(req.get_header("X-goog-api-key"), "sk-test-123")
        self.assertEqual(body["tools"], [{"google_search": {}}])

    def test_ollama_no_web(self):
        resp = {"choices": [{"message": {"content": "ok local"}}]}
        (text, src), req, body = self.call(ai.AIConfig(provider="ollama"), resp, web=True)
        self.assertEqual(text, "ok local")
        self.assertEqual(req.full_url, "http://localhost:11434/v1/chat/completions")
        self.assertEqual(body["messages"][0], {"role": "system", "content": "SYS"})
        self.assertNotIn("tools", body)
        self.assertIsNone(req.get_header("Authorization"))

    def test_compatible_custom(self):
        c = cfg_for("compatible", model="deepseek-chat", base_url="https://api.deepseek.com/v1/")
        (text, _s), req, body = self.call(c, {"choices": [{"message": {"content": "x"}}]})
        self.assertEqual(req.full_url, "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(body["model"], "deepseek-chat")

    def test_not_ready(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ai.AIError):
                ai.ask(ai.AIConfig(provider="openai"), "s", self.MSGS)

    def test_http_errors(self):
        for code, needle in ((401, "401"), (429, "429"), (500, "invalid model")):
            err = urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(
                json.dumps({"error": {"message": "invalid model"}}).encode()))
            with mock.patch("urllib.request.urlopen", side_effect=err):
                with self.assertRaises(ai.AIError) as cm:
                    ai.ask(cfg_for("anthropic"), "s", self.MSGS)
                self.assertIn(needle, str(cm.exception))

    def test_network_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("sin red")):
            with self.assertRaises(ai.AIError):
                ai.ask(cfg_for("openai"), "s", self.MSGS)


class TimeoutTests(unittest.TestCase):
    def test_timeout(self):
        import socket
        with mock.patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            with self.assertRaises(ai.AIError) as cm:
                ai.ask(cfg_for("gemini"), "s", [{"role": "user", "content": "x"}])
        self.assertEqual(str(cm.exception), i18n._("El servicio de IA tardó demasiado en responder."))

    def test_bad_json(self):
        class Bad(FakeResp):
            def read(self):
                return b"<html>"
        with mock.patch("urllib.request.urlopen", return_value=Bad({})):
            with self.assertRaises(ai.AIError):
                ai.ask(cfg_for("openai"), "s", [{"role": "user", "content": "x"}])


class PromptTests(unittest.TestCase):
    def test_quick_actions_format(self):
        for label, prompt in ai.QUICK_ACTIONS:
            self.assertTrue(i18n.tr(prompt, section="Ingresos"))

    def test_field_question(self):
        q = ai.field_question("Salarios (casilla 1)", "Del W-2", "Ingresos")
        self.assertIn("Salarios (casilla 1)", q)
        self.assertIn("Del W-2", q)


class ContextAmountsTests(unittest.TestCase):
    def test_yes_no_fields_are_not_amounts(self):
        ret = TaxReturn()
        ctx = ai.build_context(ret, None)
        self.assertNotIn("material_participation", ctx)
        self.assertNotIn("Other income fields", ctx)
        ret.income.taxable_interest = 120
        self.assertIn("taxable_interest=$120", ai.build_context(ret, None))


if __name__ == "__main__":
    unittest.main()
