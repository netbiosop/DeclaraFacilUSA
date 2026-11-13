# Registro de revisiones (antislop + Thermos)

Lo lee y lo actualiza la revisión nocturna antes de revisar. Cada revisión agrega una entrada arriba del historial.
- **Decisiones vigentes**: cosas que se dejaron así a propósito. No se "corrigen" ni se reportan como hallazgo
  salvo que haya una razón nueva; si la hay, se explica.
- **Pendientes**: problemas conocidos que necesitan una decisión del dueño o un trabajo más grande.
- **Historial**: qué se encontró, cómo se corrigió y en qué rama o pull request.

## Decisiones vigentes
- `main.py` es la base fija del instalador: no se modifica en correcciones de código. Las actualizaciones de
  `taxapp/`, `data/`, `docs/` y `assets/` corren sobre la base `__base__` (1.5.1). No usar módulos de Python que esa
  base no incluya (por ejemplo `logging.handlers`); ante la duda, revisar `crear_exe_windows.bat`.
- `except tk.TclError: pass` para ventanas o widgets ya cerrados se deja: es el comportamiento esperado de Tk.
- `main.py` hace `import tkinter` solo para comprobar que existe; no es un import sin uso.
- `SettingsWindow.build_*` se llaman con `getattr(self, "build_" + section)`; `redirect_request` en `updater.py` es
  un método que llama urllib. No son código muerto.
- Montos de impuestos que cambian por año van en `data/federal_<año>.json` / `data/states_<año>.json`; tasas y edades
  de la ley, como constantes con nombre en `federal.py`. Todo cambio de cálculo lleva prueba y debe dar los mismos
  resultados que antes salvo que la corrección sea justamente el cálculo.
- `actualizacion.json` lo regenera `publicar_actualizacion.bat`; las correcciones no lo tocan.
- El número de versión (`taxapp/__init__.py`) lo sube el dueño al publicar; las correcciones no lo tocan.
- `publicar_actualizacion.bat` publica la carpeta local del dueño encima de `main`: los cambios fusionados en GitHub
  deben llevarse a esa carpeta antes de publicar.
- `except Exception` con `logger.exception` en `gui/app.py` (abrir, calcular, exportar…) y `forms_view.py`: registran y
  evitan que la app se cierre; se dejan. `HomeA`/`HomeB`/`HomeC` (`home.py`) se eligen por tema: no son código muerto.
- Edades: `Dependent.age` cuenta al 31-dic por aniversario (Rev. Rul. 2003-72, CTC/EITC/cuidado y el crédito AZ);
  `age_at_year_end` (contribuyente y cónyuge) sigue con la regla del día anterior (65 años, HSA 55).
- Parentesco del dependiente: se guarda la clave en español de `RELATIONSHIPS`; `_CHILD_RELATION_RE` (`models.py`) usa
  palabras completas en inglés para archivos con texto libre ("son" por subcadena aceptaba "Otra persona del hogar").
- `usuarios.json` que no se puede leer (bloqueo, no daño) se carga vacío con la marca `_unreadable` y `save()` se niega
  a escribirlo; un `AccountError` que llega a un callback de Tk queda en `errores.log` (no se perdió nada).
- `data_loader.user_dir()`: gana la carpeta (Documentos o USERPROFILE) que ya tiene `usuarios.json`, después la que
  exista; solo se crea si no hay ninguna. No volver a elegir por "existe Documentos" en cada llamada.
- `updater.save_config` guarda solo lo que difiere de `data/actualizaciones.json`. Un cambio de repositorio en `data/`
  debe publicarse en una versión posterior a la 2026-11-03 (las PC que ya guardaron `repo` lo conservan hasta que
  coincida con el publicado).
- `user_dir()` también reconoce `~/.declarafacilusa` (la carpeta de respaldo si Documentos está bloqueado) cuando tiene
  `usuarios.json`.
- `login_failed` de un usuario que no existe se anota con usuario vacío a propósito: lo escrito puede ser la contraseña
  puesta en el campo equivocado (`actividad.log` lo ven Supervisores y va en los respaldos).
- Al eliminar un usuario, lo que queda en su carpeta (PDF exportados) pasa a `<quien recibe>/<usuario>_eliminado_<fecha>/`
  con `rename` (todo o nada); `list_returns` no lo muestra como declaración, `can_access_path` sí lo permite a quien lo recibe.
- Ventanas que escriben en la declaración llevan `edits_return = True` (`Dialog`, `GuidedQuestions`): `open_file`/`new_return`
  se niegan mientras haya una abierta, aunque haya perdido el grab (el ✦ de la IA lo suelta a propósito). Una ventana nueva
  que escriba en `app.ret` debe llevar la marca. `PackageDialog` no la lleva: su botón de finales solo actúa si sigue
  abierta la declaración del borrador (`_final_button`).
- El `main.py` de la base 1.5.1 solo importa `taxapp.i18n` y `taxapp.gui.app.main`: se pueden quitar funciones internas
  de `updater` sin romper la base.
- Escritura atómica: `data_loader.write_atomic(path, texto)` (.tmp + fsync + replace) para usuarios.json, declaraciones,
  `estado.json`, `ai_config.json`, `actualizaciones.json`, `config.json` (idioma), condados y recientes. `main.py`
  `_save_state` escribe aparte porque es la base fija (ver Pendientes). Exportar HTML y `.completo` siguen con `write_text`.
- `data_loader.read_json(path, default)`: un JSON válido de otro tipo que `default` (p. ej. `[]` donde se espera `{}`) se
  anota y se toma como `default`, igual que uno dañado.
- Diálogos de edición de filas (dependientes, W-2, `ListEditor`) reemplazan por identidad con `gui/lists.replace_row`: si la
  fila se borró con el diálogo abierto (el "?" de la IA suelta el grab), Aceptar la vuelve a agregar en vez de perderla.
- Texto de los PDF: `pdf._cp1252` quita el acento a las letras que no están en Windows-1252 (Ễ→E, Đ→D); las que no tienen
  forma sin acento (chino, emoji) siguen saliendo "?". El logger `pypdf` queda en ERROR porque sus avisos citan nombres.

## Pendientes
- `taxapp/state.py` `_ss_subtraction`: umbrales estatales de Seguro Social (CT, MN, NM, RI, VT, WV) escritos en código e
  iguales para 2025 y 2026; MN y RI se ajustan cada año. Moverlos a `states_<año>.json` con valores 2026 verificados y
  pruebas por estado.
- `taxapp/gui/screens.py` (~1.050 líneas) y `taxapp/lang_en.py` (~1.500 líneas) conviene dividirlos.
- La interfaz no se prueba con el Python de la nube (sin Tkinter), pero sí con `uv venv --python 3.12 --python-preference only-managed` y `xvfb-run -a python -m unittest discover tests` (`pypdf` por `PYTHONPATH`).
- **QSS (alta, cambia resultados)**: `federal.pick()` pasa por `sk()` y trata a QSS como MFJ en todos los umbrales de
  reducción (EITC `federal.py:~495`, CTC, Medicare adicional, base del Seguro Social, préstamo estudiantil, AOTC/LLC,
  QBI, Schedule 1-A, CDCC 2026). La ley da el umbral conjunto solo a MFJ; QSS sí comparte tramos, deducción estándar,
  ganancias de capital, AMT y NIIT (agregar `"qss": 250000` a `niit.threshold`). Ej. 2025, 2 hijos, salario $40k:
  EITC QSS $5,145 vs HOH $3,646. `forms/build.py` f8863 ya usa el límite de "other" para QSS: formulario y cálculo no
  coinciden. Verificar tabla por tabla, corregir con pruebas por estado civil; afecta declaraciones QSS guardadas.
  `state.py:93,155` cuenta 2 personas para QSS: revisar por estado.
- Línea 16 del 1040 y EIC con fórmula en vez de la Tax Table (franjas de $50) cuando el ingreso tributable < $100,000:
  diferencias de $0–6 que el IRS corrige con aviso (`federal.py:46-105`).
- Oficina en casa (método simplificado) puede crear/aumentar pérdida del Anexo C; la Rev. Proc. 2013-13 la limita al
  ingreso bruto menos otros gastos (`models.py:~290`, `build.py:~449`).
- Actualizador: si falta el `.sha256` (o falla su descarga) se instala sin verificar y el diálogo dice "Descarga
  verificada" (`updater.py:~200,252`). Decidir si se rechaza. La versión del manifiesto se usa como nombre de carpeta sin
  validar (`updater.py:~384`, solo explotable por quien controla el repo).
- Tras una vuelta atrás automática, el proceso hijo hereda `DECLARAFACIL_CODE_ROOT` de la versión mala y
  `data_loader.app_dir()` la sigue usando; tampoco se fija `DECLARAFACIL_ROLLBACK`. Corregible en `restart()` (env sin
  `DECLARAFACIL_*`) por actualización; la parte de `data_loader` del instalador solo con un instalador nuevo.
- Medicare adicional: si la casilla 5 del W-2 está vacía se usa la casilla 1 (`federal.py:132,516`).
- Montos aún escritos en código: `build.py:617` (cuidado de dependientes 2500/5000, ¿cambia en 2026?), `screens.py:346,525`,
  `gui/tools.py:175`, `assistant.py:243-244`, `review.py:131` (IRA 7500), edades en `models.py`; textos de ayuda con montos
  de 2025 en `screens.py:637-731`; años 2025/2026 fijos en la interfaz en vez de `SUPPORTED_YEARS`. Montos estatales
  además de `_ss_subtraction` en todo `state.py` (MO, OR, AL, CT, IL, OH, MD, NM, AZ, CA, VT, UT).
- Cálculos que cambian montos y hay que verificar con la ley antes de tocar (revisión 2026-11-01):
  MFS que vivió separado los últimos 6 meses no recibe EITC (`federal.py:~478`, ARPA §32(d)(2)(B)); beneficios de
  cuidado del empleador: se resta el bruto y no lo excluido, y el 2441 no descuenta L30 (`federal.py:~376`,
  `build.py:~624`); interés de inversión sin el límite del 4952 (`federal.py:~277`); WA ganancias >$1M al 9 % (¿9,9 %
  por SB 5813?) en `states_2025/2026.json`; mínimo QBI 2026 de $400 sin exigir participación material y antes del
  tope (`federal.py:~319`); edad <13 del 2441 por aniversario (verificar Pub. 503).
- Anexo B: el límite de $1,500 está 5 veces (`questions.py:142-151`, `build.py:146`) y `build.py` también lo genera por
  `foreign_trust`, pero entonces la pregunta desaparece. Decidir la condición y una sola `needs_schedule_b()`.
- `earned_tp` (2441) se calcula igual en `federal.py:~378` y `build.py:~613`: devolverlo en el resultado.
- Cálculos que cambian montos, encontrados el 2026-11-02 (verificar con la ley/Pub. antes de tocar):
  recién nacido/fallecido en el año con `months_lived` ≤ 6 pierde CTC/EITC (Pub. 501: cuenta todo el año; ¿regla en
  código o texto de ayuda?, `models.py:~128`); `qualifies_care` sin `months_lived` ni parentesco (§21(b)(1), padre no
  custodio, `models.py:~140`); quien `can_be_claimed` recibe CTC/ODC/ACTC (§152(b)(1); el AOTC usa "otro lo reclama",
  `federal.py:~440`); MFS que vivió separado todo el año usa base $0 del Seguro Social (`federal.py:~180`, falta el
  campo); Maine sin `hoh` en `states_2025/2026.json` (usa la de soltero) y AZ 2026 `hoh` = soltero.
- `clean_money_text`: "1.500,50" → 1.5005 y "45.000" → 45 (formato con punto de miles). Decidir cómo leer "12.345".
- Cierre por inactividad (`gui/app.py:~454`): con una declaración nueva sin guardar la sesión nunca se cierra y los datos
  quedan a la vista. ¿Autoguardar en `recuperado_<fecha>.dfusa` o pantalla de bloqueo?
- Asistente de IA: `include_data=True` por defecto envía montos de la declaración al proveedor sin consentimiento del
  cliente (IRC §7216 para preparadores). Decidir aviso/consentimiento.
- Actualizador: las tablas `data/*.json` que el admin edita (la pantalla lo invita) se reemplazan sin aviso en cada
  actualización de código (`updater.py:~397`). "Actualización cancelada" (`gui/updates.py:~135`) se muestra cuando
  `apply_code()` ya dejó la versión nueva activa para el próximo arranque.
- Formularios: al volver a generar quedan en la carpeta PDF de la vez anterior (Anexo C, 1040-V con otro saldo)
  (`forms/__init__.py:~111`). Borrar archivos del usuario es decisión del dueño.
- `gui/theme.py:~150` `except Exception` silencioso al leer fuentes (y guarda un conjunto vacío para siempre); Tk no
  se puede probar en la nube.
- Duplicación que conviene unir (resultados iguales): aritmética del 1-A/8812/2441 recalculada en `build.py`; gastos
  del Anexo C escritos dos veces (`build.py:~442`, `models.py:~310`); `_get_json`/`_fetch` del actualizador con
  encabezados distintos; edad 65 y 55 sin constante en 9 sitios (`SENIOR_AGE`, `HSA_CATCHUP_AGE`); `compute_federal`
  (~485 líneas) por secciones.
- Impuesto local del lugar de trabajo (`local.py:~120`) con la tasa de residente y sin crédito: Columbus/Cleveland
  $50k → $2,500 (real ~$1,250, Columbus acredita hasta 2,5 %); no residente en Detroit 2,4 % en vez de 1,2 % y suma
  intereses/dividendos. Falta `nonresident_rate` en `local_<año>.json` y el crédito de OH. Cambia montos: verificar tasas.
- ODC $500 para un dependiente que no vive en EE. UU. (`federal.py:~442`): §24(h)(4) exige ciudadano/nacional/residente;
  la casilla `lived_in_us` no es eso. ¿Campo de ciudadanía/residencia? Cambia montos.
- Cerrar la app en los 5 s tras actualizar (`gui/app.py:73`, `after(5000, confirm_code_ok)`) marca la versión como mala
  para siempre. Llamar también `confirm_code_ok()` en `quit_app()` (interfaz: no se prueba en la nube).
- Encontrados el 2026-11-08 (cambian montos o deciden el dueño):
  - Residente parcial: el impuesto local no se prorratea (`local.py:51`, el estatal sí en `state.py:301`). MD Montgomery $80k, 6 meses: estatal $1,718, condado $2,350 (esperado ~$1,175). Verificar por estado.
  - NIIT no resta la pérdida de capital de hasta $3,000 (`federal.py:469`, `build.py:885`; 8960 línea 5a). MFJ $300k, intereses $20k, dividendos $10k, línea 7 −$3,000: $1,140 vs $1,026. Verificar Reg. §1.1411-4.
  - "Deducciones itemizadas estatales" se ignora sin aviso en estados con deducción federal (CO, MO…; `state.py:177-206`, `screens.py:804`). ¿Avisar o aplicarla?
  - Interfaz (corregibles, probar con Xvfb): monto inválido en un diálogo se guarda como 0 (`widgets.py:192,332`); Tab por un campo vacío marca "cambios sin guardar" (`widgets.py:200`).
  - Limpieza con resultados iguales: claves del resultado sin lector (`federal.py:541-587`, `state.py:312`); `_load_user` en `accounts.py` (3 copias); `_to_bytes` en `forms/pdf.py` (4 copias); tasa `override_rate` 2 veces y claves `kind`/`note` en `local.py`; `_require_repo` en `updater.py`; `TaxReturn.app_version` e `Instance.label` sin uso; cabecera de borrador repetida en `reports.py`; `std_is_credit` sin lector en `states_*.json`; envoltorios y estilos sin uso en `gui/` (`ask_ai_field(widget)`, `_after_change`, `Screens._changed`, `Surface.TFrame`, `Menu.TButton`).
- Inicio de sesión: un usuario inexistente responde distinto y más rápido (sin PBKDF2) que uno existente ("Intentos
  restantes: N") → revela qué usuarios existen. ¿Mismo mensaje y mismo cálculo?
- "Ajustes generales y seguridad" (intentos, minutos de bloqueo, largo de contraseña) los cambia quien tenga
  `manage_users` (`gui/settings.py:29`, `accounts.update_settings`). ¿Solo Administrador?
- Duplicación menor: `storage.returns_dir()` arma a mano `accounts.returns_dir()`; `gui/app.py` `_activity` =
  `reset_idle_timer` y `_open_folder` solo llama a `_open_path`; User-Agent `DeclaraFacilUSA/...` en `counties.py` y 3
  veces en `updater.py`; números sueltos `0.94/0.88` (`layout.py`), `[:8]` recientes (`storage.py`), `30_000` (`app.py`).
- Propuestas de estructura: una sola función para tareas en segundo plano en `ui.py` (hoy 8 copias), `ListEditor` para
  dependientes/W-2/locales en `screens.py`, unificar estado civil→clave, `ask_ai_action` por clave y no por posición.
- Encontrados el 2026-11-04 (cambian montos o necesitan la interfaz):
  - Pérdida de capital arrastrada: un solo campo y siempre se resta del corto plazo (`federal.py:136`, `build.py:541`,
    `screens.py:431`). Con arrastre de largo plazo grava de más (ej. 2025: $350). ¿Campo aparte para la línea 14 del Anexo D?
  - Pensilvania (y el EIT local de `local.py:49`) usa la casilla 1 del W-2; PA grava los aportes al 401(k) (casilla 16,
    `box16_state_wages`, se pide pero no se usa). Verificar la regla de PA y del EIT.
  - W-2 del cónyuge en MFS/soltero: la revisión ya lo marca como error, pero el cálculo lo sigue sumando
    (`federal.py:121`, `state.py:101`, `local.py:49,132`). ¿Filtrarlo también en el cálculo?
  - Carpetas de usuarios eliminados antes del 2026-11-04 siguen en `Declaraciones/<usuario>/` y un usuario nuevo con ese
    nombre las ve. ¿Archivarlas al crear el usuario?
  - "Guardar como" `Garcia.Maria` dos veces pisa `Garcia.Maria.dfusa` sin preguntar: el diálogo comprueba el nombre sin
    extensión (`gui/app.py:~370`). Pedir confirmación si `p + ".dfusa"` existe.
  - `gui/settings.py:237` descarga de fuentes con `except Exception` sin `logger.exception` (interfaz).
  - Limpieza con resultados iguales: `models.py` conversión a número repetida en 10 `__post_init__` (dos con listas a
    mano); `build.py:517,934` vuelve a leer como texto un monto ya formateado (`_num`; puede cambiar $1 por redondeo);
    regla "el 1040-SR no lleva su última página" en `forms/__init__.py:105` y `build.py:272`; caso especial `"s3"` en
    el bucle de `build.py:162`; números sin nombre en `build.py` (2210 1000, 1116 300/600, 8283 500, 8949 11 filas,
    Anexo B 14/15, Anexo C 9/8).
- Encontrados el 2026-11-05 (cambian montos o necesitan la interfaz; verificar con la ley antes de tocar):
  - Estados que parten de la deducción federal (CO, ID, MT, ND, IA, NM vía `uses_federal_deduction`; DC y MO vía
    `std_from_federal`, `state.py:177-184`): si se itemiza, la deducción incluye el propio impuesto estatal (SALT) y no
    se suma de vuelta. Ej. 2025 MFJ $200k, casilla 17 $9,000: CO −$396, ID −$477, MO −$423, NM −$441, DC −$765. CO/ID/
    MO/NM/DC exigen el ajuste; confirmar MT, ND, IA. Propuesta: `addback_state_income_tax` por estado en `states_<año>.json`.
  - Utah, crédito del contribuyente (`state.py:287`): resta todo el SALT (también propiedad o ventas), no solo el impuesto
    estatal sobre la renta (TC-40 línea 10). Ej. MFJ $45k con $6,000 de propiedad: crédito igual que con $0.
  - Cabeza de familia como soltero en reducciones de CA (`state.py:257`, sin HOH ni MFS), UT (`ut_phase_base`, `:289`) y
    WI (`wi_std_phase`, `:203`). Ej. CA 2025 HOH $300k: crédito por exención $370 en vez de ~$610.
  - Calculadora rápida (`gui/tools.py:177`): "Ingreso neto estimado" no suma créditos reembolsables (EITC/ACTC). Ej. 2026
    HOH $25k con 2 hijos: neto $23,087, real ~$33,545. Corrección de una línea, pero es interfaz Tk.
  - Umbral de "sin pago": la línea 37 se imprime desde $0.50 pero `forms/__init__.py:180` y `mailing.py:50` usan ≥ 1.
  - Borrador (`reports.py`): faltan filas de `other_adjustments` (Anexo 1) y `other_nonref`/`other_refundable`; la fila
    "Desempleo, reembolsos estatales, juegos y otros" (`L["8"] - profit`) puede mostrar $0.01 por redondeo.
  - Sin verificar: direcciones del IRS por estado en `forms/mailing.py` (AL/GA/NC/SC/TN con Austin) y la codificación del
    archivo del Censo en `counties.py` (sin acceso a irs.gov/census.gov desde la nube).
  - Limpieza con resultados iguales: lista de estados para combos 3 veces (`gui/tools.py:32,132`, `screens.py:209`);
    `max_tokens` 1500 repetido y límites 200–16000 en código vs 300–8000 en pantalla (`gui/assistant.py:83,158`);
    autoguardado 5/60 a mano (`gui/settings.py:289,299`); 2210 `1000`/`0.9` sin nombre en `review.py:~150`;
    `counties._all` con lector JSON propio; margen `0.6 * inch` 6 veces en `reports.py`.

- Encontrados el 2026-11-09 (deciden el dueño o cambian montos):
  - "Participación material" del Anexo C no afecta el cálculo: con "No" y pérdida se resta completa sin límite pasivo (§469, Form 8582) ni aviso (`questions.py:197`, `screens.py:472`, `build.py:439`; `federal.py` no lo usa). Mínimo: aviso en `review.py` si `profit < 0 and not material_participation`. Limitar la pérdida cambia montos.
  - Clientes homónimos comparten carpeta de PDF (`forms/__init__.py:73`, `Garcia_Maria_2025_formularios`): la segunda pisa los finales de la primera y un Anexo C con SSN queda mezclado. Propuesta: nombrar con el stem del `.dfusa`.
  - Autoguardado sin control de mtime ni instancia única (`gui/app.py:~389`, `storage.py`): dos ventanas sobre la misma declaración, gana la última. Propuesta: guardar mtime al abrir (un mutex chocaría con `updater.restart`).
  - `.dfusa`, PDF y respaldos ZIP (SSN, cuentas) sin cifrar en Documentos; si OneDrive respalda esa carpeta suben a la nube (`accounts.py:9`). ¿Carpeta fuera de Documentos, aviso o cifrado?
  - Limpieza menor: contraseña temporal repetida (`gui/settings.py:774,815`), bloque "Notas" (`screens.py:308`, `gui/tools.py:102`), `view_frame` (`gui/app.py:125,135`), `after(150)` (`gui/assistant.py:190,494`).

- Encontrados el 2026-11-10 (limpieza con resultados iguales, sin urgencia): parámetros que nadie pasa `mpos(zero)` y
  `header(name_key, ssn_key)` (`build.py:36,108`), `lang_toggle(bg)` (`ui.py:251`, además `bg` sin uso), `ListEditor(factory)`,
  `_help_icon(column)`, `scroll(padding)`, `settings.field(width)`, `ui.card(border)`; atributos sin lector
  `SettingsView.section`, `Pill.title`, `ListEditor.kind`, `self.students` (`screens.py:731`); `"*.dfusa"` 7 veces aunque
  existe `storage.EXT`; `accounts.authenticate` repetido en las dos ramas de `login.py:148,155`; `timeout=60` de
  `updater.download()` sin nombre; `layout._num` lee `padx` en tupla `(0, 10)` como 0 (la etiqueta puede salir ~10 px más
  ancha); `release_json(with_sha)` en `tests/test_updater.py`.

- Encontrados el 2026-11-11 (deciden el dueño o necesitan la interfaz):
  - `accounts.can()` sin `db` relee `usuarios.json` en cada comprobación (`App.can`, ~35 sitios): con el archivo bloqueado un
    momento, `_empty()` da los permisos por defecto (un Supervisor puede ganar permisos). ¿Matriz fija al iniciar sesión (lo que
    dice `settings.py:505`)? Hoy un permiso quitado se aplica al momento.
  - `gui/login.py:151`: `update_settings("", remember_user=…)` corre antes de autenticar (también en intentos fallidos). Guardarlo
    tras un `authenticate` correcto (Tk).
  - Casilla 3 del W-2 vacía → `box1` como salario de Seguro Social en el Anexo SE (`federal.py:128`): empleado público sin SS
    (casillas 3 y 4 en 0) + Anexo C $180k paga $6,216 menos. Igual que el pendiente de Medicare: qué significa una casilla vacía.
  - Transferir o eliminar un usuario con una de sus declaraciones abierta (`gui/settings.py:493,850`): `app.path` sigue en la
    carpeta vieja y el autoguardado la recrea. Negarse o actualizar la ruta (Tk).
  - `casualty_loss` en negativo resta de las itemizadas (mismo patrón que la pérdida arrastrada; `federal.py:285`, `build.py:385`).
  - Aviso de IRA (`review.py:132`) con la edad al 31-dic: quien cumple 59 en el año no recibe el aviso de 59½.
  - La pregunta del estado rechaza "tx" con el mensaje genérico en vez de pasarlo a mayúsculas (`forms_view.py:438`).
  - Limpieza: `except Exception` amplio en `counties.py:361` y `gui/app.py:569` (sin `from` ni traceback); `catalog.py` repite
    `ORDER`/`SHORT`/`FILE_NAMES` que ya están en el JSON (`"seq"` sin lector); "Recargar tablas" (`gui/settings.py:603`) no limpia
    `catalog._load` ni `counties._all` (→ `data_loader.reload()`); `tests/test_sesion.py` repite la preparación 8 veces sin
    parchear `ITERATIONS`; fechas 15-abr/15-oct en `gui/ui.py:283` además de `deadline` en `federal_<año>.json`.

- `main.py` `_save_state` (base fija): escribe `estado.json` con `open("w")` sin fsync ni replace; un corte de luz tras
  `_rollback_now` puede perder la lista "bad". Corregirlo exige un instalador nuevo (main.py no se toca en correcciones).
- `gui/forms_view.py:261`: la generación de PDF en otro hilo lee `self.ret` en vivo mientras el usuario puede seguir
  editando; propuesta `copy.deepcopy(self.ret)` al empezar (Tkinter, no se puede probar a fondo aquí).
- `forms/questions.py:55` `_ssn_ok` solo mira el formato ("000-00-0000" cuenta como completo); `review.valid_ssn` es más
  estricto. Usarlo cambia qué falta para los formularios finales: decide el dueño.
- `review.py:165`: la revisión muestra notas federales y locales pero no las estatales (`st["notes"]`).
- Estructura: DPAPI (`protect`/`unprotect`) vive en `assistant.py` y lo usa el actualizador; `forms/build.py` (958 líneas)
  pasa de 1.000 con el próximo formulario; `state.py:213-260` cadena de `if "XX_…" in special`; `assistant.ask` un `if` por
  proveedor. Anexo A 2026 (`build.py:382`): con el piso de 0,5 % avisaría "supera el límite" sin pasarlo (sin PDF 2026 aún).

- Encontrados el 2026-11-13 (cambian montos o limpieza; no se corrigieron):
  - Utah resta la exención por dependiente del ingreso y además la usa en el crédito del contribuyente (`state.py:263` y
    `:286-288`). 2025 soltero UT $60k con 2 dependientes: neto $1,868.57 vs ~$2,052.71 esperado. Verificar con el TC-40
    antes de tocar (cambia montos).
  - `summary["total_tax"]` (`engine.py:25`) sin lector; `gui/tools.py:177` rehace la misma suma.
  - `wait_visibility()` + `grab_set()` copiado 5 veces: un `ui.make_modal(win)`.
  - `App.findings()` (`gui/app.py:467-470`): el respaldo `recalc_now` si no hay resultado es inalcanzable y, si corriera,
    `review(ret, None)` lanzaría TypeError. Quitarlo o usar `result_or_warn()`.
  - Confirmación "La revisión encontró {n} error(es)…" duplicada (`gui/app.py:515`, `forms_view.py:229`).
  - `herramientas/generar_manifiesto.py:46,60` repite la rama (`main`) y el nombre `actualizacion.json` que `updater` tiene
    como `BRANCH`/`MANIFEST`; la regex de versión está copiada en 3 archivos.
  - `herramientas/mapear_formularios.py`: `zip()` sin `strict=True` en las listas de campos (una lista más corta pierde
    campos sin aviso).
  - La prueba nueva del borrador PDF se omite en el venv de Xvfb (reportlab de Python 3.13 por `PYTHONPATH`, su PIL no
    carga en 3.12); corre con `python3 -m pytest`.

## Historial
### 2026-11-13 — revisión nocturna (PR #2, rama `revision-nocturna`; `main` sin cambios)
- `gui/screens.py:381,603`, `gui/lists.py:160`: los diálogos de edición guardaban el índice; con el "?" de la IA (suelta el
  grab, `gui/app.py:705`) se podía borrar otra fila y Aceptar pisaba la equivocada o daba IndexError → `replace_row` por
  identidad. `forms/questions.py:92` (SSN del dependiente por índice) → apunta al dependiente. Prueba Xvfb y `test_forms.py`.
- `gui/app.py:229`: cambiar idioma dentro de la declaración → KeyError 'appearance' y pantalla vacía → `_rebuild()` sin
  `section`. Prueba Xvfb.
- `models.py:566`: `.dfusa` viejos con "tx" → `TaxReturn.from_dict` pasa el estado a mayúsculas. Prueba en `test_engine.py`.
- `reports.py:208,218`: el borrador PDF imprimía "■■c Nguy■n" → `_cp1252` en filas y pie. Prueba con pypdf.
- `data_loader.read_json`: `[]` en config/ai_config/actualizaciones.json cerraba la app al arrancar → devuelve `default`.
- `updater.py:97`, `i18n.py:73`, `counties.py:76`, `storage.py:74` sin fsync ni replace → `write_atomic`.
- `updater.py:257-262`: descarga cortada o incompleta dejaba el `.exe` truncado → se borra; `apply_code` borra `<ver>.tmp`
  si `_raw_file` falla. `forms/mailing.py:51`: clave `"group"` sin lector, quitada.
- Revisión del propio cambio (ponytail-review): línea en blanco en `gui/lists.py`; prueba de reportlab omitible.
- Pruebas: 162 → 169 pasan (18 omitidas sin pantalla; con Xvfb, 178 → 187 con 1 omitida). Pendientes nuevos arriba.
### 2026-11-12 — revisión nocturna (PR #2, rama `revision-nocturna`; `main` sin cambios)
- `forms/pdf.py:98,194,296`: un nombre como "Nguyễn Đức" salía `NGUY?N ??C` en el 1040 final y pypdf anotaba el nombre en
  `errores.log` (va en los respaldos) → `_cp1252` en `_prepare`/`_pdf_str` y logger `pypdf` en ERROR. Prueba en `test_forms.py`.
- `gui/screens.py:331,537`, `gui/lists.py:110`: en Solo lectura el doble clic abría el diálogo de edición y cambiaba `app.ret`
  (el siguiente cálculo y los formularios lo usaban) → `edit`/`edit_w2`/`ListEditor.edit` salen si `app.readonly`. Prueba Xvfb.
- `updater.py:324`, `assistant.py:115`: `estado.json` y `ai_config.json` sin fsync ni replace → `data_loader.write_atomic`,
  que ahora usan también accounts y storage (antes había cuatro copias). Prueba en `test_updater.py`.
- Limpieza: comparación encadenada en `review.py:128`, `SSN_RE`/ZIP duplicados en `questions.py`, `num_people()` en
  `local.py`, variable sin usar en `home.py`, comentario 0.6/0.62 em en `pdf.py`.
- Revisión del propio cambio (ponytail-review + Thermos): guardado atómico en un solo lugar; `main.py` queda en Pendientes.
- Pruebas: 160 → 162 pasan (16 omitidas sin pantalla; con Xvfb, 178). Pendientes nuevos arriba.
### 2026-11-11 — revisión nocturna (PR #2, rama `revision-nocturna`; `main` sin cambios)
- `forms/questions.py:101`: la pregunta del estado aceptaba "tx"/"XX" → `KeyError` en la pantalla de dirección (`screens.py:282`)
  y estado $0 sin error → se valida contra `states_info()` y la pregunta reaparece si el guardado es inválido.
- `federal.py:136`: pérdida arrastrada escrita "(3,000)" (−3000) se sumaba como ganancia (+$720 en el ejemplo) mientras el
  Anexo D imprimía pérdida (`mpos`) → `abs()`. 1.500 declaraciones aleatorias con valores positivos: resultados idénticos.
- `accounts.py:587`: `create_backup` con `with_suffix` convertía "Respaldo_oficina.2026" en "Respaldo_oficina.zip" y pisaba ese
  respaldo → `with_name(name + ".zip")`. Quitada la excepción `last_user` de `update_settings` (nadie la pasa).
- Limpieza: `getattr(app, "readonly")` en `gui/lists.py`; prueba de que `CODE_DIRS` es igual en `updater.py` y `generar_manifiesto.py`.
- Revisión del propio cambio (ponytail-review + Thermos): prueba movida a `FederalTests`.
- Pruebas: 156 → 160 pasan (15 omitidas sin pantalla). Pendientes nuevos arriba.
### 2026-11-10 — revisión nocturna (PR #2, rama `revision-nocturna`; `main` sin cambios)
- `federal.py:267,279`, `build.py:373`: con AGI negativo el piso médico sumaba y los topes de donaciones restaban (Anexo A
  L3 "(750)", L14 "(9,000)", deducción negativa; CO/ID/MO/NM/DC cobraban de más) → base `max(0, AGI)`. 6.000 declaraciones
  aleatorias: solo cambian las 196 con AGI < 0 y solo la deducción (impuesto federal igual). Prueba en `test_engine.py`.
- `gui/app.py`: el bloqueo de Ctrl+O/Ctrl+N dependía del grab, que se pierde al cerrar un `Dialog` abierto desde las preguntas
  guiadas o con el ✦ de la IA → se abría otro cliente y el diálogo (W-2, número de cuenta) escribía los datos de A en B →
  `_editor_open()` (ver Decisiones). Prueba con Xvfb.
- `gui/forms_view.py`: "Todo correcto: generar finales" del paquete tras un borrador saltaba los datos obligatorios y la
  confirmación de errores → `_final_ready()`; y tras cambiar de cliente actuaba sobre el nuevo → `_final_button()`.
- Limpieza: `fmt_money(signed)`, `compute_state(code)`, `Form.text(upper, show)`, `_right_pad`, `_get_text`/`_download_bytes`,
  regex doble en `generar_manifiesto.py`.
- Revisión del propio cambio (ponytail-review + Thermos): botón de finales de otro cliente (arriba), nombre `agi_pct_base`.
- Pruebas: 155 → 156 pasan (15 omitidas sin pantalla; con Xvfb, 171). Pendientes nuevos arriba.
### 2026-11-09 — revisión nocturna (PR #2, rama `revision-nocturna`; `main` sin cambios)
- `gui/app.py:recalc_now` un cálculo fallido conservaba el resultado del cliente anterior y exportar/generar lo usaba con el nombre del actual → `self.result = None`, `result_or_warn()` en exportar, generar y preguntas guiadas (Xvfb, `test_sesion.py`).
- `gui/app.py:65` Ctrl+N/Ctrl+O atravesaban diálogos modales y el W-2 abierto caía en otra declaración → `_shortcut`.
- `forms/build.py:193` 1040 marcaba "No" a activos digitales con venta cripto en el Anexo D → Sí si hay venta digital. `forms/pdf.py:31` EIN con guion impreso como SSN (2441, 8995) → se respeta lo escrito, `_fmt_ein` en 8995. `build.py:608` cuarta persona del 2441 desaparecía → hoja adicional.
- `storage.py`, `accounts.py` sin `fsync` antes de `replace` (corte → archivo vacío; con `usuarios.json` el asistente crea un admin) → `write_durable`. `accounts.create_backup` fallo a mitad dejaba ZIP válido e incompleto → `.tmp` + `replace`.
- `updater.py:_get_json` reenviaba la clave a otro host → `_resolve`.
- Limpieza: atributos, estilos e iconos sin uso, `skip()`, docstring de `key_dates`, constantes de tiempos y bloques.
- Revisión del propio cambio: asistente sin resultado, `grab_current()` con combobox abierto (`tk.call("grab","current")`).
- Pruebas: 149 → 155 pasan (12 omitidas sin pantalla; con Xvfb, 167). Sin cambios de cálculo. Pendientes nuevos arriba.
### 2026-11-08 — revisión nocturna (PR #2, rama `revision-nocturna`; `main` sin cambios)
- `gui/app.py:117` cerrar sesión dejaba el Workspace (nombre, SSN) visible al siguiente usuario → no se pone en None antes de destruir (prueba con Xvfb en `test_sesion.py`).
- `gui/app.py`, `gui/assistant.py`: el chat con el cliente A seguía al abrir B y se enviaba al proveedor → `forget_client()` (también descarta la respuesta en camino).
- `gui/assistant.py:325` marcar una opción borraba la clave de IA recién guardada → relee la configuración.
- `accounts.py:126` `usuarios.json` con `[]` impedía abrir la app → camino de archivo dañado. `models.py`/`widgets.py`: "nan"/"inf" como montos → rechazados. `review.py`: aviso si 1099-R tiene bruto y no tributable.
- `updater.py` `_fetch` reenviaba la clave de GitHub a otro host → `_resolve` (la conserva si el host no cambia).
- Limpieza: `Release.extra`, `hash_password(iterations)`, doble orden en `forms/__init__.py`, docstring de `pdf.py`, `nonzero_amounts`.
- Pruebas: 144 → 149 pasan (9 omitidas sin pantalla; con Xvfb, 158). Sin cambios de cálculo. Pendientes nuevos arriba.
### 2026-11-05 — revisión nocturna (PR #2, rama `revision-nocturna`)
- `local.py:56` impuesto local personalizado sobre el AGI con AGI negativo (pérdida de negocio) daba impuesto negativo y
  "Reembolso local" → base acotada a 0 (prueba nueva; 3.000 declaraciones: solo cambian las 31 con base negativa).
- `forms/build.py:243` líneas 34/35a/36 redondeadas por separado (100,49 y 20,50 → 100 = 80 + 21) y monto negativo al año
  próximo impreso como (500) → dólares enteros y 0 ≤ L36 ≤ L34 (prueba nueva; cálculos iguales, 73 descuadres → 0).
- `reports.py:31` el borrador no tenía la línea 25c (Medicare adicional retenido): 25d no era la suma (prueba nueva).
- Limpieza: `elif` siempre verdadero y `section_name()` que solo reenviaba (`gui/assistant.py`), imports a mitad de
  `updater.py`, `any()` en `review.py`, `SECTIONS` en `__all__` de `gui/app.py`, comentario repetido en `i18n.py`.
- Pruebas: 141 → 144 pasan (7 de interfaz omitidas). Pendientes nuevos arriba (estados con SALT, UT, HOH, calculadora).
### 2026-11-04 — revisión nocturna (PR #2, rama `revision-nocturna`)
- `storage.py:34` "Guardar como" con punto (`Garcia.Maria`) usaba `with_suffix` y pisaba `Garcia.dfusa` sin aviso → se
  agrega la extensión (y `.json` antiguo pasa a `.dfusa`). Prueba en `test_engine.py`.
- `review.py`: W-2 del cónyuge en una declaración no conjunta se sumaba como salario propio → error en la revisión.
- `data_loader.py:49` las cuentas en `~/.declarafacilusa` (Documentos bloqueado) se ignoraban al desbloquearse → cuenta
  como carpeta con `usuarios.json`. `accounts.py:322` el texto de un usuario inexistente iba tal cual a `actividad.log`.
- `accounts.py:277` al eliminar un usuario sus PDF (SSN, cuenta) quedaban para un usuario nuevo con el mismo nombre →
  `_archive_leftovers`. Prueba con la carpeta `*_formularios`.
- `questions.py:124` número de ruta solo por largo → dígito de control ABA (`_routing_ok`).
- Limpieza sin cambio de montos (3.000 declaraciones aleatorias iguales al centavo): `state.py` 4 copias de
  `phase_factor`; `federal.py` `ctc_allowed` = `has_ssn` y `_excess_ss` dos veces; `build.py` `self.other` muerto y
  edad del cónyuge repetida. `except Exception` acotados en `assistant.py:316` y `generar_manifiesto.py:49` (ahora avisa).
- Revisión del propio cambio (ponytail-review + Thermos): `rename` en vez de `shutil.move`, `isdecimal`, prueba de
  respaldo que había quedado partida, `HOME` fijo en las pruebas de cuentas, `http.client.HTTPException`.
- Pruebas: 135 → 141 pasan (7 de interfaz omitidas). Pendientes nuevos arriba.

### 2026-11-03 — revisión nocturna (PR #2, rama `revision-nocturna`)
- `accounts.transfer_returns`/`unlock`: un Supervisor con "Crear usuarios" se llevaba las declaraciones del Administrador
  y lo desbloqueaba → `_require_admin` si la cuenta afectada es admin; la pantalla muestra el error.
- `data_loader.user_dir()`: si aparecía Documentos la app cambiaba a una carpeta vacía y pedía un admin nuevo → gana la
  carpeta con `usuarios.json` (ver Decisiones).
- `accounts.USERNAME_RE`: "ana." (Windows quita el punto: misma carpeta que "ana") y CON/NUL/COM1 → rechazados al crear.
- `updater.save_config`: `repo` quedaba congelado en la PC → solo se guarda lo distinto de `data/`.
- `local.py`: rama de Baltimore muerta, "threshold" copiaba `bracket_tax`, condición repetida, `earned_income` sin uso
  de `ret` (94.200 casos contra la versión anterior: 0 diferencias). `counties`: "…del Censo: None" → dice cuántos
  estados llegaron; `MIN_STATES`. Color `primary_dark` sin uso.
- Pendiente: local de trabajo (OH/MI), ODC fuera de EE. UU., cierre en 5 s tras actualizar, enumeración de usuarios,
  ajustes de seguridad (ver arriba).
### 2026-11-02 — revisión nocturna (PR #2, rama `revision-nocturna`)
- `models.py:~117` `is_child_relation`: "son" por subcadena → "Otra persona del hogar" recibía CTC y EITC (HOH $30k:
  $2,200 + $3,265) → regex de palabras completas (acepta Stepchild/Grandchild, rechaza Godson).
- `models.py` `qualifies_eitc`: ignoraba `lived_in_us` (§32(c)(3)(C)). Dependiente nacido después del año calificaba
  para CTC/EITC/cuidado y ODC → `born_by()`; `review.py` marca fechas imposibles ("2015-02-30") y futuras.
- `federal.py:~404` y `build.py` 8863: AOTC sin medio tiempo o con 4 años completados → `Student.aotc_eligible()`;
  sin líneas 26-30 tras el "Stop". 3.000 declaraciones contra la versión anterior: solo cambian las que tienen estos casos.
- `accounts.delete_user`: no dejaba borrar un admin ya desactivado.
- `assistant._dedupe`: enlaces de "Fuentes" de la IA abiertos con `webbrowser.open` sin revisar esquema (en Windows
  ejecuta rutas locales/UNC) → solo http/https.
- Pendiente: recién nacido, cuidado, `can_be_claimed`, MFS SS, Maine HOH, coma decimal, inactividad, consentimiento IA,
  tablas editadas, PDF viejos (ver arriba).
### 2026-11-01 — revisión nocturna (PR #2, rama `revision-nocturna`)
- `models.py` `Dependent.age`: un niño nacido el 1-ene salía un año mayor (regla del día anterior) y perdía CTC/EITC/
  cuidado → edad al 31-dic por aniversario.
- `federal.py:~480`: EITC conjunto sin SSN válido del cónyuge → se exigen los dos (§32(c)(1)(E), §32(m)).
- `federal.py:248,377` y `build.py:613`: la pérdida del Anexo C no restaba del ingreso del trabajo (EITC, ACTC, 2441,
  deducción estándar del dependiente) → `max(0, salario + ganancia − mitad SE)` (Pub. 596).
  Las tres comparadas en 2.000 declaraciones: solo cambian las que cumplen alguna condición.
- `build.py:605`: el 2441 contaba personas cuidadas distinto que el cálculo → usa `credits.n_care`.
- `accounts.py`: con `manage_users` un Supervisor podía hacerse Administrador, crear admins, restablecer su contraseña,
  borrarlo o cambiar la tabla de permisos → `_require_admin()` (pruebas nuevas).
- `review.py`: todo ITIN salía como "formato inválido" → se aceptan los grupos de ITIN y se avisa si un ITIN está marcado
  como SSN (contribuyente, cónyuge, dependiente).
- `gui/assistant.py`, `gui/updates.py`: `except Exception` sin registro → errores esperados + `logger.exception`.
  Clave `'Usted'` duplicada en `lang_en.py`; `self.state_cb` sin uso.
- Pendiente: MFS separado y EITC, beneficios de cuidado, interés de inversión, WA 9,9 %, QBI mínimo, Anexo B (ver arriba).
### 2026-10-28 — revisión nocturna (rama `revision-nocturna`, sobre `antislop`)
- `accounts.load()`: un `usuarios.json` bloqueado (OSError) se tomaba como vacío y el inicio de sesión lo guardaba encima
  en cada intento → marca `_unreadable`, `save()` lo rechaza, `authenticate` avisa; `update_settings` ya no escribe si
  nada cambió (pruebas nuevas).
- `gui/forms_view.py:255`, `gui/updates.py:113`: la lambda usaba `e` tras el `except` → NameError, `_failed` nunca corría
  (pantalla "Descargando…" para siempre) → `lambda err=e:` y registro.
- `gui/workspace.py:39`, `assistant.py:195-208`: casillas sí/no contaban como montos → `models.nonzero_amounts()`.
- `gui/app.py` `save()`: fallo de disco silencioso y ruta `.json` no actualizada al guardar como `.dfusa` → `_write()`
  con aviso; autoguardados con `quiet=True`.
- `widgets.parse_money` / `models._num`: "1500,50" se guardaba como 150,050 → `clean_money_text()` (coma decimal).
- `updater.py` errores de `.sha256` y `check_any` ignorados; `gui/settings.py:577` `except Exception` silencioso.
- `forms/build.py`: tasas y límites AOTC/LLC/CTC/QBI/Medicare leídos del JSON (1.500 declaraciones: formularios
  idénticos). Código muerto: `widgets.FONT`, `widgets.card`, `accounts.owner_of`, rama de `federal.pick`.
- Pendiente: QSS, Tax Table, oficina en casa, política de `.sha256`, entorno tras vuelta atrás (ver Pendientes).
### 2026-10-27 — revisión inicial (PR #1, rama `antislop`)
- `usuarios.json` dañado se tomaba como vacío y el asistente de inicio borraba todas las cuentas → ahora se guarda una
  copia `usuarios.danado-<fecha>.json` antes (prueba nueva).
- Registro `errores.log` en Documentos\DeclaraFacilUSA; errores de la interfaz y de abrir/calcular/exportar quedan
  con su detalle. Fallos que se ignoraban (idioma, configuración, condados, claves) ahora se anotan.
- `data_loader.read_json()` como único lector de JSON; `open_path()` en `gui/ui.py`.
- Montos por año a `data/federal_*.json`; resultados idénticos en 400 declaraciones de prueba.
- Eliminadas 10 funciones y 19 imports sin uso; `except Exception` reducidos a los errores posibles.
