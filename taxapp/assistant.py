"""Asistente de IA / AI assistant: Claude, ChatGPT (OpenAI), Gemini y servicios compatibles con OpenAI (Ollama local,
LM Studio, OpenRouter, Groq, DeepSeek...).

- Sin dependencias externas: llamadas HTTPS con urllib.
- Privacidad: el contexto enviado NO incluye SSN/ITIN, nombres, direccion, ZIP, telefono, email ni EIN; solo montos,
  estado/condado y datos necesarios para responder (ver build_context()).
- Las claves API se guardan cifradas con DPAPI de Windows (solo su usuario de Windows puede descifrarlas).
"""
from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

from . import data_loader
from .i18n import _, N_, tr, get_language
from .models import TaxReturn

# ---------------------------------------------------------------------------- proveedores
PROVIDERS: Dict[str, dict] = {
    "anthropic": {"label": "Claude (Anthropic)", "model": "claude-sonnet-5-5",
                  "models": ["claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"],
                  "base_url": "https://api.anthropic.com", "needs_key": True, "web": True,
                  "env": "ANTHROPIC_API_KEY", "key_url": "https://platform.claude.com/settings/keys"},
    "openai": {"label": "ChatGPT (OpenAI)", "model": "gpt-5.5", "models": ["gpt-5.5", "gpt-6-astra"],
               "base_url": "https://api.openai.com/v1", "needs_key": True, "web": True,
               "env": "OPENAI_API_KEY", "key_url": "https://platform.openai.com/api-keys"},
    "gemini": {"label": "Gemini (Google)", "model": "gemini-3.8-flash", "models": ["gemini-3.8-flash", "gemini-4-argon"],
               "base_url": "https://generativelanguage.googleapis.com/v1beta", "needs_key": True, "web": True,
               "env": "GEMINI_API_KEY", "key_url": "https://aistudio.google.com/apikey"},
    "ollama": {"label": N_("Ollama (local, gratis)"), "model": "llama3.2", "models": ["llama3.2", "qwen2.5", "mistral"],
               "base_url": "http://localhost:11434/v1", "needs_key": False, "web": False,
               "env": "", "key_url": "https://ollama.com/download"},
    "compatible": {"label": N_("Otro compatible con OpenAI"), "model": "", "models": [],
                   "base_url": "https://openrouter.ai/api/v1", "needs_key": True, "web": False,
                   "env": "", "key_url": ""},
}
ANTHROPIC_VERSION = "2023-06-01"
TIMEOUT = 90


class AIError(Exception):
    pass


# ---------------------------------------------------------------------------- configuracion y claves
@dataclass
class AIConfig:
    provider: str = "anthropic"
    model: str = ""
    base_url: str = ""
    keys: Dict[str, str] = field(default_factory=dict)   # proveedor -> clave cifrada
    include_data: bool = True
    web_search: bool = False
    max_tokens: int = 1500

    def effective_model(self) -> str:
        return self.model or PROVIDERS[self.provider]["model"]

    def effective_base_url(self) -> str:
        return (self.base_url or PROVIDERS[self.provider]["base_url"]).rstrip("/")

    def get_key(self, provider: str = None) -> str:
        p = provider or self.provider
        enc = self.keys.get(p, "")
        if enc:
            try:
                return unprotect(enc)
            except Exception:  # noqa: BLE001
                return ""
        env = PROVIDERS.get(p, {}).get("env")
        return os.environ.get(env, "") if env else ""

    def set_key(self, key: str, provider: str = None):
        p = provider or self.provider
        if key:
            self.keys[p] = protect(key.strip())
        else:
            self.keys.pop(p, None)

    def is_ready(self) -> bool:
        if self.provider not in PROVIDERS:
            return False
        if self.provider == "compatible" and not (self.effective_model() and self.effective_base_url()):
            return False
        return (not PROVIDERS[self.provider]["needs_key"]) or bool(self.get_key())

    def supports_web(self) -> bool:
        return PROVIDERS.get(self.provider, {}).get("web", False)


def _config_path():
    return data_loader.user_dir() / "ai_config.json"


def load_config() -> AIConfig:
    try:
        d = json.loads(_config_path().read_text(encoding="utf-8"))
        cfg = AIConfig(**{k: v for k, v in d.items() if k in AIConfig.__dataclass_fields__})
        if cfg.provider not in PROVIDERS:
            cfg.provider = "anthropic"
        return cfg
    except (OSError, ValueError, TypeError):
        return AIConfig()


def save_config(cfg: AIConfig):
    _config_path().write_text(json.dumps(asdict(cfg), indent=1), encoding="utf-8")


# DPAPI (Windows) — cifra con la cuenta del usuario; fuera de Windows se usa base64 (solo ofuscacion).
def _dpapi(data: bytes, encrypt: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if encrypt else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0x01, ctypes.byref(blob_out)):
        raise OSError("DPAPI")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def protect(secret: str) -> str:
    if sys.platform.startswith("win"):
        try:
            return "dpapi:" + base64.b64encode(_dpapi(secret.encode("utf-8"), True)).decode()
        except Exception:  # noqa: BLE001
            pass
    return "b64:" + base64.b64encode(secret.encode("utf-8")).decode()


def unprotect(stored: str) -> str:
    if stored.startswith("dpapi:"):
        return _dpapi(base64.b64decode(stored[6:]), False).decode("utf-8")
    if stored.startswith("b64:"):
        return base64.b64decode(stored[4:]).decode("utf-8")
    return stored


# ---------------------------------------------------------------------------- contexto (sin datos personales)
def _m(v) -> str:
    return f"${v:,.0f}"


def build_context(ret: Optional[TaxReturn], res: Optional[dict], section: str = "") -> str:
    """Resumen de la declaracion para la IA, en ingles (los modelos razonan mejor con terminos del IRS).
    Excluye: nombres, SSN/ITIN, direccion, ZIP, telefono, email, EIN y nombres de empleadores."""
    if ret is None:
        return "No return is open. Answer general U.S. tax questions."
    y = ret.tax_year
    L = []
    L.append(f"Tax year: {y} (filed in {y + 1}). Filing status: {ret.filing_status}.")
    ages = [a for a in (ret.taxpayer_age(), ret.spouse_age()) if a is not None]
    if ages:
        L.append("Ages at year end: " + ", ".join(str(a) for a in ages) + ".")
    flags = []
    if ret.taxpayer.blind:
        flags.append("taxpayer blind")
    if ret.taxpayer.can_be_claimed:
        flags.append("can be claimed as a dependent")
    if not ret.taxpayer.valid_ssn_for_work:
        flags.append("taxpayer has no SSN valid for work (ITIN)")
    if flags:
        L.append("Flags: " + "; ".join(flags) + ".")
    a = ret.address
    L.append(f"Residence: state {a.state or '?'}, county {a.county or '?'}, local jurisdiction {a.locality or 'none'}"
             f"{', works in ' + a.work_locality if a.work_locality else ''}; months in state {a.months_in_state}.")
    if ret.dependents:
        deps = []
        for i, d in enumerate(ret.dependents, 1):
            deps.append(f"#{i} age {d.age(y)}, relationship '{d.relationship}', {d.months_lived} months, "
                        f"SSN {'yes' if d.has_ssn else 'no'}{', student' if d.full_time_student else ''}"
                        f"{', disabled' if d.disabled else ''}")
        L.append("Dependents: " + " | ".join(deps) + ".")
    for i, w in enumerate(ret.w2s, 1):
        L.append(f"W-2 #{i} ({'spouse' if w.owner == 'conyuge' else 'taxpayer'}): box1 {_m(w.box1_wages)}, box2 "
                 f"{_m(w.box2_fed_withheld)}, box12 401k {_m(w.box12_401k)}, state {w.state}, box17 {_m(w.box17_state_withheld)},"
                 f" box19 {_m(w.box19_local_withheld)}.")
    inc = ret.income
    nz = {k: v for k, v in vars(inc).items() if isinstance(v, (int, float)) and v}
    if nz:
        L.append("Other income fields (non-zero): " + ", ".join(f"{k}={_m(v)}" for k, v in nz.items()) + ".")
    dd = {k: v for k, v in vars(ret.deductions).items() if isinstance(v, (int, float)) and not isinstance(v, bool) and v}
    L.append(f"Deduction mode: {ret.deductions.mode}." + (" Deduction inputs: " + ", ".join(f"{k}={_m(v)}" for k, v in dd.items()) + "." if dd else ""))
    cr = ret.credits
    cnz = {k: v for k, v in vars(cr).items() if isinstance(v, (int, float)) and not isinstance(v, bool) and v}
    if cnz or cr.students:
        L.append("Credit inputs: " + ", ".join(f"{k}={v}" for k, v in cnz.items())
                 + (f"; students: {[(s.credit, _m(s.expenses)) for s in cr.students]}" if cr.students else "") + ".")
    pnz = {k: v for k, v in vars(ret.payments).items() if v}
    if pnz:
        L.append("Payments: " + ", ".join(f"{k}={_m(v)}" for k, v in pnz.items()) + ".")
    se = {k: v for k, v in vars(ret.state_extras).items() if isinstance(v, (int, float)) and v}
    if se:
        L.append("State adjustments: " + ", ".join(f"{k}={_m(v)}" for k, v in se.items()) + ".")
    if res:
        f, s, lo = res["federal"], res["state"], res["local"]
        L.append("APP RESULTS (computed by DeclaraFacil USA's engine):")
        L.append(f"Federal: total income {_m(f['total_income'])}, AGI {_m(f['agi'])}, "
                 f"{'itemized' if f['itemize'] else 'standard'} deduction {_m(f['deduction'])} "
                 f"(standard available {_m(f['standard_deduction'])}, itemized {_m(f['itemized_net'])}), "
                 f"Schedule 1-A {_m(f['sched1a']['total'])} {dict((k, round(v)) for k, v in f['sched1a'].items())}, "
                 f"QBI {_m(f['qbi'])}, taxable income {_m(f['taxable_income'])}, tax {_m(f['tax'])}, AMT {_m(f['amt'])}, "
                 f"credits {dict((k, round(v) if isinstance(v, float) else v) for k, v in f['credits'].items())}, "
                 f"other taxes {_m(f['other_taxes']['total'])}, total tax {_m(f['total_tax'])}, payments "
                 f"{_m(f['payments']['total'])}, {'refund' if f['balance'] >= 0 else 'owed'} {_m(abs(f['balance']))}, "
                 f"marginal rate {f['marginal_rate'] * 100:.0f}%.")
        if s.get("name"):
            L.append(f"State {s['name']}: taxable {_m(s.get('taxable_income', 0))}, tax {_m(s['tax'])}, "
                     f"{'refund' if s['balance'] >= 0 else 'owed'} {_m(abs(s['balance']))}.")
        if lo["items"]:
            L.append("Local: " + "; ".join(f"{i['name']} {i['rate']} = {_m(i['tax'])}" for i in lo["items"]) + ".")
        notes = f.get("notes", []) + s.get("notes", [])[:6]
        if notes:
            L.append("Engine notes: " + " | ".join(notes))
    if section:
        L.append(f"The user is currently on the '{section}' screen of the app.")
    return "\n".join(L)


def year_facts(year: int) -> str:
    f = data_loader.federal(year)
    sd = f["standard_deduction"]
    return (f"Key {year} federal figures (IRS inflation adjustments as amended by the One Big Beautiful Bill Act, P.L. 119-21): "
            f"standard deduction single/MFS ${sd['single']:,}, MFJ ${sd['mfj']:,}, HOH ${sd['hoh']:,}; additional 65+/blind "
            f"${f['additional_std']['married']:,} married / ${f['additional_std']['unmarried']:,} unmarried; child tax credit "
            f"${f['ctc']['per_child']:,} (refundable up to ${f['ctc']['refundable_max']:,}); SALT cap ${f['salt']['cap']:,}; "
            f"Schedule 1-A 2025-2028: tips up to $25,000, overtime premium up to $12,500/$25,000 MFJ, car loan interest up to "
            f"$10,000, senior deduction $6,000 per person 65+; max EITC (3+ kids) ${f['eitc']['3']['max']:,}; Social Security wage "
            f"base ${f['se']['ss_wage_base']:,}.")


SYSTEM_PROMPT = """You are the tax assistant inside DeclaraFacil USA, a desktop app that prepares and estimates U.S. federal, \
state and local (county/city) income tax returns for tax years 2025 and 2026.

Rules:
- Reply in {language}. Be concise and practical; use short paragraphs or bullets.
- Use the user's return data and the app results below. Do not ask for or repeat SSNs, names or addresses.
- Prefer the key figures provided here over your training data (tax law changed with the One Big Beautiful Bill Act of 2025).
- When you recommend entering a value, name the app screen and field (screens: Personal information; Address, state and \
county; Dependents; Income (tabs W-2, Interest and dividends, Investments, Self-employment, Retirement and Social Security, \
Unemployment and other, Tips and overtime); Deductions (Adjustments, New deductions Schedule 1-A, Itemized); Credits; \
Payments; State return; Local taxes; Review; Summary).
- If something looks wrong or inconsistent in the numbers, say so and explain why.
- If you are not sure, say so and point to the official IRS or state source (form and instructions).
- You are not a CPA or attorney; for complex or high-stakes situations recommend a tax professional or IRS VITA (free).
{web}

{facts}

USER RETURN (personal identifiers removed):
{context}"""


def system_prompt(ret, res, section, include_data=True, web=False) -> str:
    year = ret.tax_year if ret else 2026
    lang = "Spanish" if get_language() == "es" else "English"
    ctx = build_context(ret, res, section) if include_data else "The user chose not to share return data."
    return SYSTEM_PROMPT.format(language=lang, facts=year_facts(year), context=ctx,
                                web="- You may search the web; prefer irs.gov and official state sites and cite sources."
                                if web else "")


# Acciones rapidas (texto que se envia como pregunta del usuario)
QUICK_ACTIONS = [
    (N_("Explicar esta sección"), N_("Explícame la sección '{section}' de la app: qué debo ingresar aquí, qué formularios "
                                     "necesito y errores comunes, usando mis datos actuales.")),
    (N_("Revisar mi declaración"), N_("Revisa mi declaración completa: busca errores, valores inconsistentes, datos faltantes "
                                      "y riesgos de auditoría. Da una lista priorizada de qué corregir y en qué pantalla.")),
    (N_("Explicar mi resultado"), N_("Explícame por qué obtengo este reembolso o saldo a pagar (federal, estatal y local), "
                                     "paso a paso desde el ingreso hasta el resultado.")),
    (N_("¿Qué me falta para ahorrar?"), N_("¿Qué deducciones o créditos podría estar dejando pasar según mi situación? "
                                           "Indica cuánto podrían valer y qué tendría que ingresar.")),
    (N_("Simular cambios"), N_("¿Qué cambios legales (aportes a IRA/HSA, estado civil, itemizar, retenciones W-4) mejorarían "
                               "mi resultado de este año o del próximo? Estima el efecto.")),
]


def field_question(label: str, help_text: str = "", section: str = "") -> str:
    q = tr("Explícame el campo '{f}' de la pantalla '{s}': qué es, de qué formulario sale (casilla), cómo se calcula, "
           "si el valor que tengo parece correcto y cómo afecta mis impuestos.", f=label, s=section)
    if help_text:
        q += "\n" + tr("(Ayuda de la app: {h})", h=help_text)
    return q


# ---------------------------------------------------------------------------- llamadas HTTP
def _post(url: str, payload: dict, headers: dict, timeout=TIMEOUT) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
    ctx = ssl.create_default_context() if url.startswith("https") else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
            msg = json.loads(body).get("error", {})
            msg = msg.get("message", msg) if isinstance(msg, dict) else msg
        except Exception:  # noqa: BLE001
            msg = body[:300]
        if e.code in (401, 403):
            raise AIError(tr("Clave API inválida o sin permiso ({c}). Revise la configuración de IA.", c=e.code)) from e
        if e.code == 429:
            raise AIError(_("Límite de uso o saldo agotado en su cuenta del proveedor (429). Intente más tarde.")) from e
        if e.code == 404:
            raise AIError(tr("Modelo o dirección no encontrados (404): {m}", m=msg)) from e
        raise AIError(tr("Error del proveedor ({c}): {m}", c=e.code, m=msg)) from e
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError) or "timed out" in str(e.reason):
            raise AIError(_("El servicio de IA tardó demasiado en responder.")) from e
        raise AIError(tr("No se pudo conectar con el servicio de IA: {e}", e=e.reason)) from e
    except (TimeoutError, OSError) as e:   # socket.timeout (Python 3.9) es OSError
        if "timed out" in str(e) or isinstance(e, TimeoutError):
            raise AIError(_("El servicio de IA tardó demasiado en responder.")) from e
        raise AIError(tr("No se pudo conectar con el servicio de IA: {e}", e=e)) from e
    except ValueError as e:
        raise AIError(tr("Respuesta inesperada del proveedor: {m}", m=e)) from e


def ask(cfg: AIConfig, system: str, messages: List[dict], web: bool = False) -> Tuple[str, List[Tuple[str, str]]]:
    """Envia la conversacion. messages: [{"role": "user"|"assistant", "content": str}].
    Devuelve (texto, [(titulo, url), ...])."""
    if not cfg.is_ready():
        raise AIError(_("Configure un proveedor de IA y su clave API en 'Configurar IA'."))
    p = cfg.provider
    model = cfg.effective_model()
    base = cfg.effective_base_url()
    key = cfg.get_key()
    web = web and cfg.supports_web()

    if p == "anthropic":
        payload = {"model": model, "max_tokens": cfg.max_tokens, "system": system, "messages": messages}
        if web:
            payload["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
        d = _post(f"{base}/v1/messages", payload, {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION})
        texts, sources = [], []
        for b in d.get("content", []):
            if b.get("type") == "text":
                texts.append(b.get("text", ""))
                for c in b.get("citations") or []:
                    if c.get("url"):
                        sources.append((c.get("title") or c["url"], c["url"]))
        return "".join(texts).strip(), _dedupe(sources)

    if p == "openai":
        payload = {"model": model, "instructions": system, "max_output_tokens": cfg.max_tokens,
                   "input": [{"role": m["role"], "content": m["content"]} for m in messages]}
        if web:
            payload["tools"] = [{"type": "web_search"}]
        d = _post(f"{base}/responses", payload, {"Authorization": f"Bearer {key}"})
        texts, sources = [], []
        for item in d.get("output", []):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        texts.append(c.get("text", ""))
                        for an in c.get("annotations") or []:
                            if an.get("type") == "url_citation":
                                sources.append((an.get("title") or an.get("url"), an.get("url")))
        if not texts and d.get("output_text"):
            texts.append(d["output_text"])
        return "\n".join(texts).strip(), _dedupe(sources)

    if p == "gemini":
        contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                    for m in messages]
        payload = {"system_instruction": {"parts": [{"text": system}]}, "contents": contents,
                   "generationConfig": {"maxOutputTokens": cfg.max_tokens}}
        if web:
            payload["tools"] = [{"google_search": {}}]
        d = _post(f"{base}/models/{model}:generateContent", payload, {"x-goog-api-key": key})
        cands = d.get("candidates") or []
        if not cands:
            raise AIError(tr("Respuesta vacía del proveedor: {m}", m=json.dumps(d.get("promptFeedback", {}))[:200]))
        c0 = cands[0]
        text = "".join(pt.get("text", "") for pt in c0.get("content", {}).get("parts", []))
        sources = [(ch["web"].get("title") or ch["web"]["uri"], ch["web"]["uri"])
                   for ch in (c0.get("groundingMetadata") or {}).get("groundingChunks", []) if ch.get("web", {}).get("uri")]
        return text.strip(), _dedupe(sources)

    # OpenAI-compatible (Ollama, LM Studio, OpenRouter, Groq, DeepSeek...): Chat Completions
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    payload = {"model": model, "max_tokens": cfg.max_tokens,
               "messages": [{"role": "system", "content": system}] + messages}
    d = _post(f"{base}/chat/completions", payload, headers, timeout=180 if p == "ollama" else TIMEOUT)
    try:
        return (d["choices"][0]["message"]["content"] or "").strip(), []
    except (KeyError, IndexError) as e:
        raise AIError(tr("Respuesta inesperada del proveedor: {m}", m=str(d)[:200])) from e


def _dedupe(sources):
    seen, out = set(), []
    for t, u in sources:
        if u and u not in seen:
            seen.add(u)
            out.append((t, u))
    return out[:8]


def test_connection(cfg: AIConfig) -> str:
    text, _s = ask(cfg, "Reply with exactly: OK", [{"role": "user", "content": "ping"}])
    return text
