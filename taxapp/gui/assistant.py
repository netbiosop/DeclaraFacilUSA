"""Ventana del asistente de IA (chat) y dialogo de configuracion / AI assistant window and settings dialog."""
from __future__ import annotations

import os
import queue
import re
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

from .. import APP_NAME, assistant as ai
from ..i18n import _, tr
from . import widgets
from .theme import icon, icon_font
from .widgets import COLORS, font, Tooltip

MAX_HISTORY = 16   # mensajes que se reenvian como contexto de la conversacion


def provider_label(code: str) -> str:
    return _(ai.PROVIDERS[code]["label"])


# ============================================================================ Configuracion
class AISettingsDialog(tk.Toplevel):
    def __init__(self, master, cfg: ai.AIConfig, on_saved=None):
        super().__init__(master)
        self.title(_("Configurar asistente de IA"))
        self.configure(bg=COLORS["card"])
        self.transient(master)
        self.resizable(True, False)
        self.cfg = cfg
        self.on_saved = on_saved
        # claves escritas en esta sesion del dialogo (por proveedor), sin cifrar todavia
        self.keys = {p: cfg.get_key(p) if cfg.keys.get(p) else "" for p in ai.PROVIDERS}
        self.models = {cfg.provider: cfg.model}
        self.urls = {cfg.provider: cfg.base_url}

        f = ttk.Frame(self, style="Card.TFrame", padding=16)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text=_("Elija el servicio de IA y pegue su clave API. Cada proveedor cobra por uso según su "
                            "propia tarifa (Ollama es gratis y funciona en su PC)."), style="CardMuted.TLabel",
                  wraplength=520, justify="left").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        codes = list(ai.PROVIDERS)
        self.codes = codes
        ttk.Label(f, text=_("Proveedor"), style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=4)
        self.prov = tk.StringVar(value=provider_label(cfg.provider))
        cb = ttk.Combobox(f, textvariable=self.prov, values=[provider_label(c) for c in codes], state="readonly", width=34)
        cb.grid(row=1, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._provider_changed())

        ttk.Label(f, text=_("Modelo"), style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=4)
        self.model = tk.StringVar()
        self.model_cb = ttk.Combobox(f, textvariable=self.model, width=34)
        self.model_cb.grid(row=2, column=1, sticky="w")

        ttk.Label(f, text=_("Clave API"), style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=4)
        self.key = tk.StringVar()
        self.key_entry = ttk.Entry(f, textvariable=self.key, show="•", width=46)
        self.key_entry.grid(row=3, column=1, sticky="we")
        self.show_key = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text=_("Mostrar"), variable=self.show_key,
                        command=lambda: self.key_entry.configure(show="" if self.show_key.get() else "•")).grid(row=3, column=2, padx=6)
        self.key_link = ttk.Label(f, text="", foreground=COLORS["info"], cursor="hand2", style="Card.TLabel")
        self.key_link.grid(row=4, column=1, sticky="w")
        self.key_link.bind("<Button-1>", lambda e: self._open_key_url())

        ttk.Label(f, text=_("Dirección del servicio"), style="Card.TLabel").grid(row=5, column=0, sticky="w", pady=4)
        self.url = tk.StringVar()
        ttk.Entry(f, textvariable=self.url, width=46).grid(row=5, column=1, sticky="we")
        ttk.Label(f, text=_("Normalmente no hace falta cambiarla (solo para Ollama u otros servicios compatibles)."),
                  style="CardMuted.TLabel", wraplength=420).grid(row=6, column=1, sticky="w")

        ttk.Label(f, text=_("Largo máximo de respuesta (tokens)"), style="Card.TLabel").grid(row=7, column=0, sticky="w", pady=4)
        self.max_tokens = tk.StringVar(value=str(cfg.max_tokens))
        ttk.Spinbox(f, from_=300, to=8000, increment=100, textvariable=self.max_tokens, width=8).grid(row=7, column=1, sticky="w")

        ttk.Label(f, text=_("Su clave se guarda cifrada con Windows (DPAPI) en Documentos\\DeclaraFacilUSA\\ai_config.json; "
                            "solo su usuario de Windows puede leerla. También puede usar las variables de entorno "
                            "ANTHROPIC_API_KEY, OPENAI_API_KEY o GEMINI_API_KEY."), style="CardMuted.TLabel",
                  wraplength=520, justify="left").grid(row=8, column=0, columnspan=3, sticky="w", pady=(12, 4))
        self.status = ttk.Label(f, text="", style="Card.TLabel", wraplength=520)
        self.status.grid(row=9, column=0, columnspan=3, sticky="w", pady=4)

        bar = ttk.Frame(f, style="Card.TFrame")
        bar.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Button(bar, text=_("Probar conexión"), command=self._test).pack(side="left")
        ttk.Button(bar, text=_("Cancelar"), command=self.destroy).pack(side="right", padx=4)
        ttk.Button(bar, text=_("Guardar"), style="Accent.TButton", command=self._save).pack(side="right", padx=4)
        self.current = cfg.provider
        self._load_provider(cfg.provider)
        self.bind("<Escape>", lambda e: self.destroy())
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def _code(self) -> str:
        lbl = self.prov.get()
        for c in self.codes:
            if provider_label(c) == lbl:
                return c
        return "anthropic"

    def _stash(self):
        self.keys[self.current] = self.key.get().strip()
        self.models[self.current] = self.model.get().strip()
        self.urls[self.current] = self.url.get().strip()

    def _load_provider(self, code):
        p = ai.PROVIDERS[code]
        self.model_cb.configure(values=p["models"])
        self.model.set(self.models.get(code) or p["model"])
        self.url.set(self.urls.get(code) or p["base_url"])
        self.key.set(self.keys.get(code, ""))
        self.key_entry.configure(state="normal")
        if p["key_url"]:
            self.key_link.configure(text=tr("Obtener clave o instalar: {u}", u=p["key_url"]))
        else:
            self.key_link.configure(text=_("Ej.: OpenRouter, Groq, DeepSeek, LM Studio (http://localhost:1234/v1)"))
        env = p.get("env")
        hint = ""
        if not self.keys.get(code) and env and os.environ.get(env):
            hint = tr("Se usará la clave de la variable de entorno {v}.", v=env)
        if not p["needs_key"]:
            hint = _("No necesita clave. Instale Ollama y ejecute: ollama pull llama3.2")
        self.status.configure(text=hint, foreground=COLORS["muted"])
        self.current = code

    def _provider_changed(self):
        self._stash()
        self._load_provider(self._code())

    def _open_key_url(self):
        u = ai.PROVIDERS[self._code()]["key_url"]
        if u:
            webbrowser.open(u)

    def _build_cfg(self) -> ai.AIConfig:
        self._stash()
        code = self._code()
        p = ai.PROVIDERS[code]
        cfg = ai.AIConfig(provider=code, keys=dict(self.cfg.keys), include_data=self.cfg.include_data,
                          web_search=self.cfg.web_search)
        model = self.models.get(code, "")
        cfg.model = "" if model == p["model"] else model
        url = self.urls.get(code, "")
        cfg.base_url = "" if url.rstrip("/") == p["base_url"].rstrip("/") else url
        try:
            cfg.max_tokens = max(200, min(16000, int(self.max_tokens.get())))
        except ValueError:
            cfg.max_tokens = 1500
        for c, k in self.keys.items():
            if k:
                cfg.set_key(k, c)
            elif c in self.keys and c in cfg.keys and not k:
                cfg.keys.pop(c, None)
        return cfg

    def _test(self):
        cfg = self._build_cfg()
        self.status.configure(text=_("Probando…"), foreground=COLORS["muted"])
        q = queue.Queue()

        def work():
            try:
                txt = ai.test_connection(cfg)
                q.put((True, tr("Conexión correcta con {p} ({m}). Respuesta: {t}", p=provider_label(cfg.provider),
                                m=cfg.effective_model(), t=txt[:60])))
            except Exception as e:  # noqa: BLE001
                q.put((False, str(e)))
        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                ok, msg = q.get_nowait()
            except queue.Empty:
                if self.winfo_exists():
                    self.after(150, poll)
                return
            if self.winfo_exists():
                self.status.configure(text=("✔ " if ok else "✖ ") + msg, foreground=COLORS["refund"] if ok else COLORS["owe"])
        poll()

    def _save(self):
        cfg = self._build_cfg()
        try:
            ai.save_config(cfg)
        except OSError as e:
            messagebox.showerror(APP_NAME, str(e), parent=self)
            return
        if self.on_saved:
            self.on_saved(cfg)
        self.destroy()


# ============================================================================ Panel de chat
class AssistantPanel(tk.Frame):
    """Chat con la IA. Se usa dentro de su propia ventana o acoplado a la derecha del espacio de trabajo."""

    def __init__(self, parent, app, compact=False):
        super().__init__(parent, bg=COLORS["card"])
        self.app = app
        self.compact = compact
        self.cfg = ai.load_config()
        self.history = []          # [{"role","content"}]
        self.busy = False
        self.q = queue.Queue()
        self.link_n = 0
        c = COLORS
        pad = 10 if compact else 14

        head = tk.Frame(self, bg=c["card"], padx=pad, pady=10)
        head.pack(fill="x")
        badge = tk.Label(head, text=icon("ai"), font=icon_font(14), bg=c["tint"], fg=c["tint_fg"], width=2, pady=2)
        badge.pack(side="left")
        titles = tk.Frame(head, bg=c["card"])
        titles.pack(side="left", padx=8)
        tk.Label(titles, text=_("Asistente de IA"), bg=c["card"], fg=c["text"], font=font(12, "bold")).pack(anchor="w")
        self.prov_lbl = tk.Label(titles, text="", bg=c["card"], fg=c["muted"], font=font(9))
        self.prov_lbl.pack(anchor="w")
        ttk.Button(head, text=_("Nueva conversación") if not compact else icon("refresh"), command=self.clear,
                   width=3 if compact else None).pack(side="right", padx=(4, 0))
        if not compact:
            ttk.Button(head, text=_("⚙ Configurar"), command=self.open_settings).pack(side="right")
        else:
            ttk.Button(head, text=icon("settings"), width=3, command=self.open_settings).pack(side="right")
        ttk.Separator(self).pack(fill="x")

        opts = ttk.Frame(self, style="Card.TFrame", padding=(pad, 6))
        opts.pack(fill="x")
        self.use_data = tk.BooleanVar(value=self.cfg.include_data)
        self.web = tk.BooleanVar(value=self.cfg.web_search)
        c1 = ttk.Checkbutton(opts, text=_("Usar datos de mi declaración (sin datos personales)"), variable=self.use_data,
                             command=self._save_opts)
        c1.pack(side="top" if compact else "left", anchor="w")
        Tooltip(c1, _("Se envían montos, estado civil, edades, estado y condado. NUNCA se envían nombres, SSN/ITIN, "
                      "dirección, ZIP, teléfono, email ni nombres o EIN de empleadores."))
        row2 = ttk.Frame(opts, style="Card.TFrame")
        row2.pack(side="top" if compact else "left", fill="x", padx=(0 if compact else 12, 0))
        self.web_cb = ttk.Checkbutton(row2, text=_("Buscar en la web"), variable=self.web, command=self._save_opts)
        self.web_cb.pack(side="left")
        Tooltip(self.web_cb, _("La IA busca en internet (irs.gov y sitios estatales) y muestra las fuentes. "
                               "Disponible con Claude, ChatGPT y Gemini; puede costar un poco más."))
        lk = ttk.Label(row2, text=_("Ver datos enviados"), foreground=c["info"], cursor="hand2", style="Card.TLabel")
        lk.pack(side="right" if not compact else "left", padx=(12, 0))
        lk.bind("<Button-1>", lambda e: self.show_payload())

        qa = tk.Frame(self, bg=c["card"], padx=pad, pady=4)
        qa.pack(fill="x")
        per_row = 2 if compact else 5
        for i, (label, _prompt) in enumerate(ai.QUICK_ACTIONS):
            b = ttk.Button(qa, text=_(label), command=lambda n=i: self.quick(n))
            b.grid(row=i // per_row, column=i % per_row, sticky="ew", padx=(0, 4), pady=2)
        for col in range(per_row):
            qa.columnconfigure(col, weight=1)

        mid = tk.Frame(self, bg=c["card"], padx=pad)
        mid.pack(fill="both", expand=True)
        self.txt = tk.Text(mid, wrap="word", relief="flat", background=c["bg"], foreground=c["text"], font=font(10),
                           padx=12, pady=10, spacing1=2, spacing3=2, cursor="arrow", highlightthickness=0, borderwidth=0)
        vsb = ttk.Scrollbar(mid, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.txt.pack(side="left", fill="both", expand=True)
        t = self.txt
        t.tag_configure("you", foreground=c["primary"], font=font(10, "bold"), spacing1=10)
        t.tag_configure("user", foreground=c["text"], lmargin1=12, lmargin2=12, background=c["tint"])
        t.tag_configure("ai", foreground=c["info"], font=font(10, "bold"), spacing1=10)
        t.tag_configure("b", font=font(10, "bold"))
        t.tag_configure("h", font=font(11, "bold"), foreground=c["primary"])
        t.tag_configure("bullet", lmargin1=10, lmargin2=24)
        t.tag_configure("code", font=("Consolas", widgets.font(10)[1]), background=c["surface"])
        t.tag_configure("muted", foreground=c["muted"], font=font(9))
        t.tag_configure("err", foreground=c["owe"])
        t.tag_configure("src", foreground=c["info"], underline=True, font=font(9))
        t.tag_bind("src", "<Enter>", lambda e: t.configure(cursor="hand2"))
        t.tag_bind("src", "<Leave>", lambda e: t.configure(cursor="arrow"))

        bottom = tk.Frame(self, bg=c["card"], padx=pad, pady=8)
        bottom.pack(fill="x")
        box = tk.Frame(bottom, bg=c["input"], highlightthickness=1, highlightbackground=c["input_border"],
                       highlightcolor=c["accent"])
        box.pack(fill="x")
        self.entry = tk.Text(box, height=3, wrap="word", font=font(10), relief="flat", borderwidth=0, padx=8, pady=6,
                             background=c["input"], foreground=c["text"], insertbackground=c["text"], highlightthickness=0)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._enter)
        self.send_btn = ttk.Button(box, text=icon("send") if compact else _("Enviar"), style="Accent.TButton",
                                   command=self.send, width=3 if compact else None)
        self.send_btn.pack(side="left", padx=6, pady=6, fill="y")
        foot = tk.Frame(self, bg=c["card"], padx=pad)
        foot.pack(fill="x", pady=(0, 8))
        self.status = ttk.Label(foot, text="", style="CardMuted.TLabel")
        self.status.pack(side="left")
        ttk.Label(foot, text=_("Enter = enviar • Shift+Enter = nueva línea. La IA puede equivocarse: verifique con el IRS."),
                  style="CardMuted.TLabel", wraplength=300 if compact else 700, justify="left").pack(
            side="top" if compact else "right", anchor="w")

        self.refresh_provider()
        self._welcome()
        self.after(100, self._poll)

    # ---------------------------------------------------------------- estado
    def refresh_provider(self):
        c = self.cfg
        if c.is_ready():
            self.prov_lbl.configure(text=f"{provider_label(c.provider)} • {c.effective_model()}")
        else:
            self.prov_lbl.configure(text=_("Sin configurar"))
        self.web_cb.state(["!disabled"] if c.supports_web() else ["disabled"])

    def _save_opts(self):
        self.cfg.include_data = bool(self.use_data.get())
        self.cfg.web_search = bool(self.web.get())
        try:
            ai.save_config(self.cfg)
        except OSError:
            pass

    def open_settings(self):
        if not self.app.can("ai_settings"):
            messagebox.showinfo(APP_NAME, _("Solo el administrador puede cambiar el proveedor y las claves de IA."),
                                parent=self.winfo_toplevel())
            return

        def saved(cfg):
            cfg.include_data, cfg.web_search = self.cfg.include_data, self.cfg.web_search
            self.cfg = cfg
            self.refresh_provider()
            self._write(_("Configuración guardada.") + "\n", "muted")
        AISettingsDialog(self.winfo_toplevel(), self.cfg, saved)

    def _welcome(self):
        self._write(_("Hola. Puedo explicar campos y formularios, revisar su declaración, explicar su resultado y "
                      "buscar deducciones o créditos que le falten. Pregunte lo que quiera sobre impuestos de EE.UU.") + "\n", "")
        self._write(_("Consejo: el signo ? azul junto a cada campo me pregunta por ese campo.") + "\n", "muted")
        if not self.cfg.is_ready():
            self._write("\n" + _("Para empezar, configure un proveedor (Claude, ChatGPT, Gemini u Ollama gratis) con "
                                 "el botón ⚙ Configurar.") + "\n", "err")

    def clear(self):
        if self.busy:
            return
        self.history = []
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self._welcome()

    # ---------------------------------------------------------------- texto
    def _write(self, s, tag=""):
        self.txt.configure(state="normal")
        self.txt.insert("end", s, tag)
        self.txt.configure(state="disabled")
        self.txt.see("end")

    def _render_md(self, text):
        """Markdown basico: titulos, viñetas, **negrita** y `codigo`."""
        self.txt.configure(state="normal")
        for line in text.splitlines():
            base = ()
            m = re.match(r"^\s{0,3}#{1,6}\s+(.*)", line)
            if m:
                self.txt.insert("end", m.group(1).replace("**", "") + "\n", "h")
                continue
            m = re.match(r"^(\s*)[-*•]\s+(.*)", line)
            if m:
                self.txt.insert("end", "  " * (len(m.group(1)) // 2) + "• ", "bullet")
                line, base = m.group(2), ("bullet",)
            for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", line):
                if part.startswith("**") and part.endswith("**") and len(part) > 4:
                    self.txt.insert("end", part[2:-2], base + ("b",))
                elif part.startswith("`") and part.endswith("`") and len(part) > 2:
                    self.txt.insert("end", part[1:-1], base + ("code",))
                elif part:
                    self.txt.insert("end", part, base)
            self.txt.insert("end", "\n", base)
        self.txt.configure(state="disabled")
        self.txt.see("end")

    def _sources(self, sources):
        if not sources:
            return
        self._write(_("Fuentes:") + "\n", "muted")
        self.txt.configure(state="normal")
        for title, url in sources:
            self.link_n += 1
            tag = f"src{self.link_n}"
            self.txt.insert("end", "  ↗ " + (title or url)[:90] + "\n", ("src", tag))
            self.txt.tag_bind(tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
        self.txt.configure(state="disabled")

    # ---------------------------------------------------------------- contexto
    def section_name(self) -> str:
        return self.app.section_name()

    def _system(self):
        res = self.app.result if self.app.ret else None
        return ai.system_prompt(self.app.ret, res, self.section_name(), include_data=bool(self.use_data.get()),
                                web=bool(self.web.get()) and self.cfg.supports_web())

    def show_payload(self):
        w = tk.Toplevel(self.winfo_toplevel())
        w.title(_("Datos que se envían a la IA"))
        w.geometry("760x560")
        t = tk.Text(w, wrap="word", font=("Consolas", 9), padx=10, pady=8)
        t.pack(fill="both", expand=True)
        t.insert("end", _("Esto es exactamente lo que se envía como instrucciones al proveedor, junto con sus preguntas:")
                 + "\n\n" + self._system())
        t.configure(state="disabled")

    # ---------------------------------------------------------------- envio
    def _enter(self, e):
        if e.state & 0x0001:   # Shift
            return None
        self.send()
        return "break"

    def quick(self, n):
        label, prompt = ai.QUICK_ACTIONS[n]
        self.ask(tr(prompt, section=self.section_name()))

    def ask(self, question: str):
        if self.busy:
            self.status.configure(text=_("Espere a que termine la respuesta actual…"))
            return
        self.entry.delete("1.0", "end")
        self.entry.insert("1.0", question)
        self.send()

    def send(self):
        if self.busy:
            return
        q = self.entry.get("1.0", "end").strip()
        if not q:
            return
        if not self.cfg.is_ready():
            self._write("\n" + _("Configure primero un proveedor de IA (⚙ Configurar).") + "\n", "err")
            self.open_settings()
            return
        if self.app.ret:
            self.app.recalc_now()
        self.entry.delete("1.0", "end")
        self._write("\n" + _("Usted") + "\n", "you")
        self._write(q + "\n", "user")
        self.history.append({"role": "user", "content": q})
        msgs = self.history[-MAX_HISTORY:]
        if msgs[0]["role"] != "user":
            msgs = msgs[1:]
        system, cfg, web = self._system(), self.cfg, bool(self.web.get())
        self.busy = True
        self.send_btn.state(["disabled"])
        self.status.configure(text=tr("{p} está pensando…", p=provider_label(cfg.provider))
                              + (" " + _("(buscando en la web)") if web and cfg.supports_web() else ""))

        def work():
            try:
                self.q.put(("ok",) + ai.ask(cfg, system, msgs, web=web))
            except Exception as e:  # noqa: BLE001
                self.q.put(("err", str(e), []))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, text, sources = self.q.get_nowait()
                self._done(kind, text, sources)
        except queue.Empty:
            pass
        try:
            if self.winfo_exists():
                self.after(150, self._poll)
        except tk.TclError:
            pass

    def _done(self, kind, text, sources):
        self.busy = False
        self.send_btn.state(["!disabled"])
        self.status.configure(text="")
        self._write("\n" + _("Asistente") + f" ({provider_label(self.cfg.provider)})\n", "ai")
        if kind == "ok":
            text = text or _("(respuesta vacía)")
            self.history.append({"role": "assistant", "content": text})
            self._render_md(text)
            self._sources(sources)
        else:
            self.history.pop()   # no dejar la pregunta sin respuesta en el historial
            self._write("⚠ " + text + "\n", "err")


# ============================================================================ Ventana independiente
class AssistantWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.title(_("Asistente de IA") + " — " + APP_NAME)
        self.geometry("780x780")
        self.minsize(560, 480)
        self.configure(bg=COLORS["card"])
        self.panel = AssistantPanel(self, app)
        self.panel.pack(fill="both", expand=True)
        self.panel.entry.focus_set()

    def ask(self, question):
        self.panel.ask(question)

    def quick(self, n):
        self.panel.quick(n)

    def open_settings(self):
        self.panel.open_settings()
