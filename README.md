# DeclaraFácil USA

**Español** | [English](#english)

Aplicación de escritorio para Windows (Python + Tkinter), **bilingüe español / inglés**, que prepara y estima declaraciones
de impuestos de EE.UU. **federales, estatales (50 estados + DC) y locales (condados y ciudades)** para los años fiscales
**2025 y 2026**, con un flujo de entrevista paso a paso inspirado en TurboTax y en IRS Direct File.

> Es un estimador y preparador de declaraciones. No es asesoría fiscal y no presenta electrónicamente al IRS:
> genera los formularios oficiales llenos en PDF para firmar y enviar por correo.

## Requisitos
- Windows 10/11 y Python 3.9+ desde https://www.python.org/downloads/ (marque "Add python.exe to PATH")
- `pypdf` para llenar los formularios oficiales del IRS (`pip install pypdf`; `ejecutar_windows.bat` lo instala solo).
- Opcional: `reportlab` para el resumen en PDF (`pip install reportlab`); sin él se exporta HTML imprimible.

## Formularios oficiales del IRS (v1.5)
En la sección **Formularios del IRS** (después de *Resumen*):
1. **Responder preguntas (guiado)**: una pregunta a la vez, solo lo que los formularios necesitan y falta (SSN,
   depósito directo, datos del negocio, pagadores del Anexo B, proveedores de cuidado, etc.).
2. **Generar formularios finales**: primero pregunta si desea un **borrador** con marca de agua
   "BORRADOR - NO PRESENTAR" para revisarlo; luego genera los finales para firmar.
3. Resultado en `Documentos\DeclaraFacilUSA\Declaraciones\<usuario>\<Apellido_Nombre>_<año>_formularios\`:
   un PDF por formulario, el archivo **COMPLETO** en el orden de adjuntos del IRS, el comprobante **1040-V** si hay
   saldo a pagar y la hoja **LEAME_Instrucciones_de_envio.pdf** con la dirección del IRS para su estado y qué firmar.

Idioma: con *Español* se usan las versiones oficiales del IRS en español (1040(SP), 1040-SR(SP), Anexos 1, 1-A, 2,
3, 8812, C, EIC y SE, en `data/formularios/<año>/es/`); los demás formularios solo existen en inglés.

Formularios: 1040 / 1040-SR; Anexos 1, 1-A, 2, 3, A, B, C, D, SE, 8812, EIC; Formularios 8949, 8863, 2441, 8880,
8995, 8889, 6251, 8959, 8960; 1040-V. Los PDF en blanco del IRS van incluidos en `data/formularios/<año>/` y el mapa
de campos en `data/formularios/<año>.json` (se genera y valida con `herramientas/mapear_formularios.py`). Los
formularios de 2026 se agregarán cuando el IRS los publique (diciembre-enero). Datos del preparador pagado (PTIN,
empresa): *Configuración → Ajustes generales*.

## Cómo ejecutar
1. Descomprima la carpeta `DeclaraFacilUSA`.
2. Doble clic en `ejecutar_windows.bat` (o `python main.py`).
3. Pruebas: `python main.py --pruebas`

## Instalador para otras PC (sin Python)
En **esta** PC (la que tiene Python y el código) haga doble clic en **`crear_instalador_windows.bat`**. El archivo:
1. crea el programa con PyInstaller (instala PyInstaller solo; si falta Python intenta instalarlo con winget);
2. busca **Inno Setup 6** (gratis) y, si no está, lo instala con winget (o se descarga de https://jrsoftware.org/isdl.php);
3. genera **`instalador_salida\Instalar_DeclaraFacilUSA_<versión>.exe`**.

Copie **ese único archivo** a cualquier PC con Windows 10/11 (64 bits) y ejecútelo: no necesita Python ni nada más.
El instalador crea el acceso directo en el escritorio y en el menú Inicio, abre la app al terminar, se desinstala desde
"Agregar o quitar programas" y las versiones nuevas se instalan encima. Por defecto se instala solo para el usuario
actual, sin permisos de administrador. Las declaraciones y usuarios (`Documentos\DeclaraFacilUSA`) no se borran.

`crear_exe_windows.bat` solo crea la carpeta del programa (exe + `_internal`) en
`%LOCALAPPDATA%\DeclaraFacilUSA_build\dist\DeclaraFacilUSA\` (fuera de OneDrive, que bloquea los archivos temporales);
para usarla en otra PC hay que copiar la carpeta **completa**.

## Actualizaciones automáticas (GitHub)
El código está en **https://github.com/netbiosop/DeclaraFacilUSA** (configurable en `data/actualizaciones.json` o en
**Configuración › Actualizaciones**). El programa instalado tiene dos partes:
- **Base** (el `.exe` con Python y librerías): se instala una vez con el instalador.
- **Código y tablas** (`taxapp/`, `data/`, `docs/`, `assets/`): se actualizan **archivo por archivo**.

**Para publicar una mejora** (en esta PC):
1. Suba el número en `taxapp/__init__.py` (por ejemplo `1.4.0` → `1.4.1`) y escriba las novedades en
   `instalador/NOTAS_VERSION.md`.
2. Doble clic en **`publicar_actualizacion.bat`** y elija **[1] Rápida** (Enter). Genera el manifiesto
   `actualizacion.json` (huella SHA-256 de cada archivo) y sube el código a GitHub. Tarda segundos.
3. Solo si cambió Python o una librería, elija **[2] Completa**: además arma y publica el instalador.
   La primera vez se elige sola (todavía no hay instalador publicado).

La primera vez el script instala GitHub CLI y Git si faltan y le pide iniciar sesión en GitHub en el navegador.

**En las PC instaladas**: cuando un Administrador inicia sesión, la app compara su versión con GitHub. Si hay una
mejora, muestra las novedades y con **Actualizar ahora** descarga **solo los archivos que cambiaron** (verificando su
huella), los guarda en `%LOCALAPPDATA%\DeclaraFacilUSA\codigo\<versión>` y se reinicia. Si la versión nueva no
arranca, la app vuelve sola a la anterior. Si la mejora necesita una base nueva, ofrece el instalador completo.
Declaraciones, usuarios y configuración nunca se tocan.

## Idioma
- La primera vez usa el idioma de Windows (español si Windows está en español; inglés en otro caso).
- Cambie en cualquier momento: selector **Español | English** del menú principal o de la pantalla de inicio de sesión,
  **Configuración › Idioma** o el menú **Idioma / Language**. La declaración abierta se conserva. Cada usuario guarda su idioma.
- Todo se traduce: pantallas, ayudas, notas de cálculo, revisión, borrador PDF/HTML y la guía.
- Sus declaraciones (`.dfusa`) se abren en cualquiera de los dos idiomas.

## Usuarios, inicio de sesión y permisos (v1.3)
- **La primera vez** la aplicación pide crear la cuenta **Administrador**. Las declaraciones que ya tenía pasan a su carpeta.
- Después, cada vez que se abre, aparece **Iniciar sesión**. Tras 5 intentos fallidos la cuenta se bloquea 15 minutos
  (ajustable).
- El Administrador crea usuarios en **Configuración › Usuarios y permisos** y les asigna un rol:

| Rol | Puede |
|---|---|
| **Administrador** | Todo: usuarios y roles, permisos, ajustes generales y seguridad, claves de IA, tablas de impuestos, tema para todos |
| **Supervisor** | Ver, editar y exportar las declaraciones de todos; usar la IA; respaldos y registro |
| **Preparador** | Crear, editar y exportar sus propias declaraciones; usar la IA |
| **Consulta** | Solo ver sus declaraciones (modo solo lectura) |

- La tabla de permisos se puede ajustar por rol. Siempre queda al menos un Administrador activo.
- Desde la lista de usuarios: editar, restablecer contraseña (con cambio obligatorio al entrar), activar/desactivar,
  desbloquear, transferir declaraciones y eliminar.
- Cada usuario tiene su carpeta: `Documentos\DeclaraFacilUSA\Declaraciones\<usuario>\`.
- Contraseñas guardadas con PBKDF2-SHA256 (nunca en texto). Registro de actividad y respaldos ZIP en
  **Configuración › Respaldos y registro**. Cierre de sesión por inactividad opcional.
- Importante: esto controla el acceso dentro de la aplicación; proteja también su usuario de Windows con contraseña.

## Apariencia y configuración (v1.3)
- **Tres temas**: A · Verde moderno (tarjetas), B · Oscuro premium (barra lateral y resultado en vivo a la derecha),
  C · Guiado (paso a paso por etapas, con el asistente de IA fijo a la derecha).
- **Configuración › Apariencia**: tema, color principal (8 colores o cualquiera), tamaño de letra (4 tamaños) y tipo de
  letra. Botón para descargar fuentes modernas gratuitas (Google Fonts). El Administrador puede fijar un estilo para todos.
- **Configuración › Funciones**: dónde ver el resultado en vivo (arriba, panel derecho o nada), panel de IA fijo y
  guardado automático.

## Menú principal
Nueva declaración 2025 o 2026 · Abrir guardada · Continuar · Mis declaraciones · Estados y condados ·
Calculadora rápida · Asistente de IA · Guía · Configuración · Actualizar condados · Idioma · Cerrar sesión · Salir
(los botones se muestran según el permiso de cada rol).

Secciones de la declaración: personal, dirección/estado/condado, dependientes, ingresos, deducciones, créditos, pagos,
estatal, local, revisión y resumen/presentar.

## Asistente de IA (v1.2)
Chat integrado con **Claude (Anthropic)**, **ChatGPT (OpenAI)**, **Gemini (Google)**, **Ollama** (gratis, local) o
cualquier servicio compatible con OpenAI (OpenRouter, Groq, DeepSeek, LM Studio…). Sin librerías adicionales.
- Ábralo con el botón **🤖 Asistente IA** (barra superior), el menú principal, *Herramientas*, el panel fijo del tema C o **Ctrl+I**.
- **⚙ Configurar**: elija proveedor y modelo, pegue su clave API y pulse *Probar conexión*. Cada proveedor cobra por
  uso con su propia tarifa; Ollama no necesita clave (instálelo y ejecute `ollama pull llama3.2`).
- **El "?" azul de cada campo** le pregunta a la IA por ese campo (qué es, de qué casilla sale, si su valor parece correcto).
- Botones **Explicar esta sección con IA** (cada pantalla), **Revisar con IA** (Revisión) y **Explicar mi resultado** (Resumen),
  más acciones rápidas: buscar ahorros y simular cambios.
- **Buscar en la web** (Claude, ChatGPT, Gemini): la respuesta trae enlaces a las fuentes (irs.gov, sitios estatales).
- **Privacidad**: solo se envían montos, estado civil, edades, estado/condado y los resultados del cálculo. Nunca nombres,
  SSN/ITIN, dirección, ZIP, teléfono, email ni nombres/EIN de empleadores. Use *Ver datos enviados* para comprobarlo, o
  desmarque *Usar datos de mi declaración*. La clave se guarda cifrada con Windows (DPAPI) en
  `Documentos\DeclaraFacilUSA\ai_config.json`; también puede usar `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` o `GEMINI_API_KEY`.
- La IA puede equivocarse: los montos oficiales los calcula el motor de la app; verifique con los formularios del IRS.

---

## English

Windows desktop application (Python + Tkinter), **bilingual English / Spanish**, that prepares and estimates U.S.
**federal, state (all 50 states + DC) and local (county and city)** income tax returns for tax years **2025 and 2026**,
with a step-by-step interview inspired by TurboTax and IRS Direct File.

> It is an estimator and draft preparer. It is not tax advice and it does not e-file with the IRS.

### Requirements
- Windows 10/11 and Python 3.9+ from https://www.python.org/downloads/ (check "Add python.exe to PATH")
- Optional: `reportlab` for PDF export (`pip install reportlab`); without it, printable HTML is exported.

### How to run
1. Unzip the `DeclaraFacilUSA` folder.
2. Double-click `ejecutar_windows.bat` (or run `python main.py`).
3. Tests: `python main.py --test`

### Installer for other PCs (no Python needed)
On **this** PC (the one with Python and the source) double-click **`crear_instalador_windows.bat`**. It:
1. builds the program with PyInstaller (installs PyInstaller itself; if Python is missing it tries winget);
2. looks for **Inno Setup 6** (free) and installs it with winget if needed (or get it from https://jrsoftware.org/isdl.php);
3. produces **`instalador_salida\Instalar_DeclaraFacilUSA_<version>.exe`**.

Copy **that single file** to any Windows 10/11 (64-bit) PC and run it: no Python or anything else is needed. It adds
desktop and Start-menu shortcuts, opens the app when done, uninstalls from "Add or remove programs", and new versions
install over old ones. By default it installs for the current user only, without admin rights. Returns and users
(`Documents\DeclaraFacilUSA`) are never deleted.

`crear_exe_windows.bat` only builds the program folder (exe + `_internal`) in
`%LOCALAPPDATA%\DeclaraFacilUSA_build\dist\DeclaraFacilUSA\` (outside OneDrive, which locks temporary files); to use
it on another PC copy the **whole** folder.

### Automatic updates (GitHub)
The code lives at **https://github.com/netbiosop/DeclaraFacilUSA** (set in `data/actualizaciones.json` or in
**Settings › Updates**). The installed program has two parts:
- **Base** (the `.exe` with Python and libraries): installed once with the installer.
- **Code and tables** (`taxapp/`, `data/`, `docs/`, `assets/`): updated **file by file**.

**To publish an improvement** (on this PC):
1. Bump the number in `taxapp/__init__.py` (e.g. `1.4.0` → `1.4.1`) and write what's new in
   `instalador/NOTAS_VERSION.md`.
2. Double-click **`publicar_actualizacion.bat`** and choose **[1] Quick** (Enter). It generates the manifest
   `actualizacion.json` (SHA-256 of every file) and pushes the code to GitHub. Takes seconds.
3. Only if Python or a library changed, choose **[2] Full**: it also builds and publishes the installer. The first time
   it is chosen automatically (no installer published yet).

The first time, the script installs GitHub CLI and Git if needed and asks you to sign in to GitHub in the browser.

**On installed PCs**: when an Administrator signs in, the app compares its version with GitHub. If there is an
improvement it shows what's new, and **Update now** downloads **only the changed files** (verifying each fingerprint),
stores them in `%LOCALAPPDATA%\DeclaraFacilUSA\codigo\<version>` and restarts. If the new version fails to start, the
app goes back to the previous one by itself. If the improvement needs a new base, it offers the full installer.
Returns, users and settings are never touched.

### Language
- On first launch it follows the Windows display language (Spanish if Windows is in Spanish, English otherwise).
- Switch anytime: the **Español | English** selector on the main menu or the sign-in screen, **Settings › Language**,
  or the **Idioma / Language** menu. Your open return is kept. Each user keeps their own language.
- Everything is translated: screens, help tips, calculation notes, review findings, the PDF/HTML draft and the guide.
- Saved returns (`.dfusa`) open in either language.

### Users, sign-in and permissions (v1.3)
- **On first launch** the app asks you to create the **Administrator** account. Any existing returns move to its folder.
- After that, **Sign in** appears every time. After 5 failed attempts the account locks for 15 minutes (adjustable).
- The Administrator creates users in **Settings › Users and permissions** and gives each a role:

| Role | Can |
|---|---|
| **Administrator** | Everything: users and roles, permissions, general and security settings, AI keys, tax tables, theme for all |
| **Supervisor** | View, edit and export everyone's returns; use the AI; backups and activity log |
| **Preparer** | Create, edit and export their own returns; use the AI |
| **Viewer** | Only view their returns (read-only mode) |

- The permission table can be adjusted per role. At least one active Administrator always remains.
- From the user list: edit, reset password (with a forced change at sign-in), enable/disable, unlock, transfer returns
  and delete.
- Each user has a folder: `Documents\DeclaraFacilUSA\Declaraciones\<user>\`.
- Passwords are stored with PBKDF2-SHA256 (never as text). Activity log and ZIP backups under
  **Settings › Backups and log**. Optional sign-out after inactivity.
- Important: this controls access inside the app; also protect your Windows user with a password.

### Appearance and settings (v1.3)
- **Three themes**: A · Modern green (cards), B · Premium dark (sidebar and live result on the right),
  C · Guided (step by step by stage, with the AI assistant docked on the right).
- **Settings › Appearance**: theme, main color (8 presets or any color), text size (4 sizes) and font. A button downloads
  free modern fonts (Google Fonts). The Administrator can set one style for everyone.
- **Settings › Features**: where to show the live result (top, right panel or hidden), docked AI panel and autosave.

### Main menu
New 2025 or 2026 return · Open saved · Continue · My returns · States and counties · Quick calculator · AI assistant ·
Guide · Settings · Update counties · Language · Sign out · Exit (buttons appear according to each role's permissions).

Return sections: personal, address/state/county, dependents, income, deductions, credits, payments, state, local,
review and summary/filing.

### AI assistant (v1.2)
Built-in chat with **Claude (Anthropic)**, **ChatGPT (OpenAI)**, **Gemini (Google)**, **Ollama** (free, local) or any
OpenAI-compatible service (OpenRouter, Groq, DeepSeek, LM Studio…). No extra libraries.
- Open it with the **🤖 AI assistant** button (top bar), the main menu, *Tools*, the docked panel in theme C or **Ctrl+I**.
- **⚙ Settings**: pick provider and model, paste your API key and click *Test connection*. Each provider bills per use
  at its own rates; Ollama needs no key (install it and run `ollama pull llama3.2`).
- **The blue "?" next to every field** asks the AI about that field (what it is, which box it comes from, whether your
  value looks right).
- **Explain this section with AI** (every screen), **Review with AI** (Review) and **Explain my result** (Summary), plus
  quick actions to find savings and simulate changes.
- **Search the web** (Claude, ChatGPT, Gemini): answers include links to their sources (irs.gov, state sites).
- **Privacy**: only amounts, filing status, ages, state/county and the calculated results are sent. Never names,
  SSN/ITIN, street address, ZIP, phone, email or employer names/EINs. Use *View data sent* to check, or untick
  *Use my return data*. The key is stored encrypted by Windows (DPAPI) in `Documents\DeclaraFacilUSA\ai_config.json`;
  you can also use `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY`.
- AI can be wrong: the official amounts come from the app's engine; verify with the IRS forms.

### Official IRS forms (v1.5)
Section **IRS forms** (after *Summary*): answer the guided questions, generate a **draft** (watermarked) to review,
then the **final forms** to sign and mail. Output: one PDF per form, the **COMPLETE** file in IRS attachment order,
Form **1040-V** when you owe, and a mailing-instructions sheet with the IRS address for your state. Requires `pypdf`.
Forms: 1040 / 1040-SR; Schedules 1, 1-A, 2, 3, A, B, C, D, SE, 8812, EIC; Forms 8949, 8863, 2441, 8880, 8995, 8889,
6251, 8959, 8960; 1040-V. Blank IRS PDFs ship in `data/formularios/<year>/`; the field map is
`data/formularios/<year>.json` (built and validated by `herramientas/mapear_formularios.py`).

### Project structure
```
main.py                     Entry point
taxapp/i18n.py              Language switching: _(), tr(), saved preference
taxapp/lang_en.py           English UI catalog (key = Spanish source text)
taxapp/lang_en_data.py      English translations of the notes in data/*.json
taxapp/federal.py           Form 1040 and schedules
taxapp/state.py             State engine (50 states + DC)
taxapp/local.py             County and city taxes
taxapp/review.py            Error review
taxapp/reports.py           PDF/HTML draft
taxapp/assistant.py         AI providers, redacted context, encrypted keys
taxapp/accounts.py          Users, roles, permissions, lockout, activity log, backups
taxapp/updater.py           Automatic updates from GitHub Releases
taxapp/forms/               Official IRS forms: catalog, builders, PDF filling, guided questions, mailing
taxapp/gui/theme.py         Themes A/B/C, colors, fonts, ttk styles
taxapp/gui/login.py         Sign-in and first-run Administrator setup
taxapp/gui/home.py          Main menu in three styles, My returns
taxapp/gui/workspace.py     Interview workspace, progress, live result, docked AI
taxapp/gui/settings.py      Settings and administration
taxapp/gui/                 Tkinter UI
data/*.json                 Rates and rules by year (editable)
docs/INVESTIGACION.md       Research and guide (Spanish)
docs/RESEARCH_EN.md         Research and guide (English)
tests/                      Engine tests and translation-coverage tests
```

### Adding or changing text
Write the Spanish text in the code wrapped in `_("...")` (or `tr("... {x}", x=...)` with placeholders) and add the
English entry to `taxapp/lang_en.py`. `tests/test_i18n.py` fails if any string is missing a translation or if the
placeholders don't match.

### Privacy
Returns are stored only on your computer (`Documents\DeclaraFacilUSA\Declaraciones`) and include SSNs: protect those
files. The app only goes online if you ask it to download the county list or use the AI assistant (which sends
only the redacted summary described above to the provider you choose).
