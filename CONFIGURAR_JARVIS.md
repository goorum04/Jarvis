# Configurar JARVIS para Nacho

> Para instalarlo de principio a fin, sigue **[GUIA_INSTALACION.md](GUIA_INSTALACION.md)**:
> es la lista ordenada. Este documento es la referencia detallada de cada pieza.

El cerebro de JARVIS vive en su Mac. El iPhone y el coche (CarPlay) escuchan
y hablan a través de Siri y de Atajos de iOS; una tablet en casa u oficina
hace de panel permanente. Esta guía cubre lo que hay que hacer una sola vez.

Cada parte funciona por separado: si algo no está configurado, JARVIS
simplemente no lo menciona. Orden recomendado: del 1 al 12.

**Después de cada paso**, ejecutar en el Mac:

```
./jarvis.sh reiniciar      # si has cambiado el .env
./jarvis.sh diagnostico
```

El diagnóstico revisa cada pieza contra los servicios reales (sin gastar
créditos) y dice qué funciona, qué falta y cómo arreglarlo. Con
`--probar-avisos` manda además un aviso de prueba al iPhone. Lo mismo se ve
en `TU_DIRECCIÓN/api/status` con el token.

### Lo conecta Nacho desde el panel

Nacho no tiene que pasarle claves ni contraseñas a nadie. En el panel de
JARVIS (paso 9) hay un botón **CONEXIONES**:

- **Gmail, Calendar y Docs**, **Mercedes me**, **pulsera WHOOP** y **WooCommerce**: pulsa
  *Conectar*, inicia sesión con su propia cuenta y acepta. Se vuelve solo al
  panel.
- **Claude, voz, avisos, mapas, Shopify y llamadas**: pega su clave en el
  formulario y pulsa *Guardar*. Cada tarjeta tiene el enlace a dónde se saca.

Las claves van de su navegador directamente al `.env` de su Mac. El panel
nunca las vuelve a mostrar (solo pone «guardada»). Tras guardar, JARVIS se
reinicia solo en unos segundos para aplicarlas. Con *Probar* se comprueba
cada conexión contra el servicio real, y con *Desconectar* se retira.

Quien instala solo prepara una vez la «identidad» de la app en Google
(paso 2), en Mercedes (paso 4) y en WHOOP (paso 12): el apartado
*Preparación* de esas tarjetas.

---

## 1. El Mac

1. Copiar la carpeta de JARVIS a su carpeta personal, por ejemplo `~/JARVIS`.
   **No** en Documentos, Escritorio, Descargas ni iCloud Drive: macOS no deja
   a los programas que arrancan solos usar esas carpetas (el instalador avisa).
2. Instalar **Tailscale** (<https://tailscale.com/download/mac> o la App
   Store) e iniciar sesión con una cuenta gratuita (paso 6).
3. Abrir Terminal y ejecutar:

   ```
   cd ~/JARVIS
   bash instalar.command
   ```

   Prepara Python por su cuenta (no hace falta instalar nada antes), genera
   el token de acceso, deja JARVIS arrancando solo al encender el Mac y
   reiniciándose si falla, abre el acceso seguro de Tailscale y termina con
   el diagnóstico. Al final muestra la **dirección** y el **token** que
   necesitan el iPhone y la tablet. Se puede volver a ejecutar cuando se
   quiera; no borra nada.
4. Abrir el panel con el enlace del instalador → **CONEXIONES**: ahí Nacho
   pega al menos la clave de Claude y la de ElevenLabs, y en *Casa y trabajo*
   las direcciones y las coordenadas de casa. `TIMEZONE` y `HOME_CITY` ya
   vienen puestos para Andorra. (También se puede todo a mano en el `.env` y
   después `./jarvis.sh reiniciar`.)

**El Mac tiene que estar encendido y despierto.** JARVIS impide que se duerma
por inactividad mientras está en marcha. Con el portátil de Nacho en casa:
- **Enchufado y con la tapa abierta.** La pantalla puede apagarse sola, eso
  da igual. Al cerrar la tapa el Mac se duerme y ningún programa lo evita
  (salvo con una pantalla externa conectada).
- **Los días que se lo lleve**, JARVIS no responde mientras el portátil vaya
  cerrado: Siri dirá que hubo un problema con el atajo. No se pierde nada: al
  abrirlo, JARVIS sigue solo, los recordatorios pendientes saltan en ese
  momento y el informe de la mañana se envía si aún es por la mañana.
- Si algún día hace falta que funcione siempre, aunque se lleve el portátil,
  la carpeta se puede pasar tal cual a un Mac mini o a un servidor en la nube.

Comandos del día a día: `./jarvis.sh estado | reiniciar | logs | parar |
arrancar | diagnostico | google | actualizar`.

## 2. Gmail y Google Calendar

Se hace en <https://console.cloud.google.com> con la cuenta de Gmail de Nacho.

1. Crear un proyecto nuevo (por ejemplo, "JARVIS").
2. *APIs y servicios → Biblioteca*: activar **Gmail API**, **Google Calendar API**
   y **Google Docs API** (para que JARVIS cree documentos).
3. *APIs y servicios → Pantalla de consentimiento de OAuth*:
   - Tipo de usuario: **Externo**. Nombre de la app: JARVIS.
   - Añadir su propio correo como usuario de prueba.
   - Al terminar, pulsar **Publicar aplicación** (pasarla a "En producción").
     Si se queda en modo "Prueba", Google caduca el permiso cada 7 días y
     JARVIS dejaría de ver el correo.
4. *APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth*:
   tipo **Aplicación web**. En *URI de redireccionamiento autorizados*, añadir:
   - `http://localhost:8000/api/conexiones/google/callback` (panel abierto en el Mac)
   - `https://TU_DIRECCIÓN/api/conexiones/google/callback` (desde el iPhone o la
     tablet; `TU_DIRECCIÓN` es la de Tailscale, paso 6)
5. En el panel → **CONEXIONES** → *Gmail, Calendar y Docs* → *Preparación*:
   pegar el **ID de cliente** y el **secreto del cliente** y guardar.
6. Nacho pulsa **Conectar**, entra con su cuenta y acepta todos los permisos.
   Como la app es suya y no está verificada por Google, saldrá un aviso:
   *Configuración avanzada → Ir a JARVIS*. Queda guardado `google_token.json`
   y ya no hay que repetirlo.

Alternativa sin panel: un cliente tipo **Aplicación de escritorio**, su JSON
renombrado a `google_credentials.json` en la carpeta de JARVIS, y
`./jarvis.sh google` en el Mac.

Ni las claves ni esos archivos se suben al repositorio (están en `.gitignore`).

Los documentos se crean en su Drive y JARVIS solo tiene acceso a los que crea
él, no al resto de su Drive. Si Google se autorizó antes de existir esta
función, el diagnóstico lo indica: basta con pulsar *Volver a conectar*.

## 3. Tráfico y navegación

En el mismo proyecto de Google Cloud: *Biblioteca* → activar **Routes API**;
*Credenciales → Crear credenciales → Clave de API* (restringirla a Routes API)
y ponerla en `GOOGLE_MAPS_API_KEY`. Es de pago por uso; JARVIS solo calcula
rutas para las citas que tienen lugar y como mucho cada 15 minutos.

`NAV_APP` elige qué app se abre al navegar: `apple`, `google` o `waze`.

## 4. El Mercedes

1. Registrarse en <https://developer.mercedes-benz.com> y crear un proyecto
   con acceso a la **Vehicle Status API** (combustible, cierre, estado y
   neumáticos). Página que explica el proyecto («URL de propósito»):
   <https://goorum04.github.io/Jarvis/>.
2. En el proyecto, como *URL de redirección*, añadir:
   - `http://localhost:8000/api/conexiones/mercedes/callback`
   - `https://TU_DIRECCIÓN/api/conexiones/mercedes/callback` (cuando ya
     esté Tailscale, paso 6)
3. En el panel → **CONEXIONES** → *Mercedes me* → *Preparación*: pegar el
   **Client ID** y el **Client Secret** y guardar.
4. Nacho escribe el **VIN** (campo E del permiso de circulación), guarda y
   pulsa **Conectar**: entra con su cuenta de Mercedes me y acepta. JARVIS
   guarda el permiso (`MERCEDES_REFRESH_TOKEN`) y lo renueva solo.

Si el portal indica otras direcciones de inicio de sesión o otros permisos,
se cambian en el `.env` sin tocar el código: `MERCEDES_AUTH_URL`,
`MERCEDES_TOKEN_URL` y `MERCEDES_SCOPES` (separados por espacios; tiene que
incluir `offline_access` para que el permiso no caduque).

Los nombres exactos de los campos de esa API hay que confirmarlos con su
documentación (ver el comentario al principio de `car.py`). Si alguno no
coincide, el error queda en la consola del backend con el JSON que devuelve
Mercedes, y se ajusta en un minuto.

**Coche matriculado en Andorra:** antes de nada, comprobar que la app
*Mercedes me* muestra el combustible y el cierre del C63. Si la app funciona
con su coche, la API también; si los servicios conectados no están activos
en Andorra para ese coche, esta parte no se podrá usar.

## 5. La tienda online

Con permisos **solo de lectura**: JARVIS consulta ventas y pedidos, no toca nada.

- **WooCommerce** (desde el panel, sin copiar claves): **CONEXIONES** →
  *Tienda WooCommerce* → escribir la dirección de la tienda, guardar y pulsar
  **Conectar**. Se abre su propia tienda: entra como administrador y aprueba
  el acceso de **lectura**; WooCommerce le entrega la clave directamente a
  JARVIS. Necesita la dirección pública de Tailscale activa (paso 6).
  A mano: *WooCommerce → Ajustes → Avanzado → API REST → Añadir clave*,
  permisos **Lectura**, y en `.env` `STORE_PLATFORM=woocommerce`, `WOO_URL`,
  `WOO_CONSUMER_KEY`, `WOO_CONSUMER_SECRET`.
- **Shopify**: *Configuración → Apps y canales de venta → Desarrollar apps →
  Crear una app* → permisos de Admin API: `read_orders` y `read_products`
  (este último para el aviso de stock bajo) → instalar y copiar el
  *token de acceso de Admin API*. Pegarlo en el panel → **CONEXIONES** →
  *Tienda Shopify* junto con la dirección `sutienda.myshopify.com`.

## 6. Acceso desde fuera de casa

El iPhone y la tablet tienen que llegar al Mac estando en cualquier sitio.
Se hace con **Tailscale Funnel**, gratis: una dirección `https://` fija para
el Mac, sin tocar el router, el DNS ni certificados. Ni el iPhone ni la
tablet necesitan instalar nada.

1. Tener Tailscale instalado y con sesión iniciada en el Mac (paso 1).
2. Ejecutar `bash instalar.command`. La primera vez, Tailscale muestra en la
   Terminal un enlace para activar Funnel: abrirlo, aceptar y volver a
   ejecutar el instalador.
3. El instalador apunta la dirección en `.env` (`PUBLIC_URL`) y la muestra al
   final, con forma `https://nombre-del-mac.tailXXXX.ts.net`.

JARVIS solo escucha dentro del propio Mac; desde fuera únicamente se entra
por esa dirección, y todo exige el token.

En el resto de la guía, `TU_DIRECCIÓN` es esa dirección y `TOKEN` es el valor
de `JARVIS_API_TOKEN` (los dos aparecen al final del instalador).

*Alternativa con su dominio* (por ejemplo `jarvis.sudominio.com`): DNS
dinámico hacia la IP de casa, Caddy en el Mac como proxy HTTPS hacia
`127.0.0.1:8000` y el puerto 443 del router abierto hacia el Mac. Funciona
igual, pero son tres piezas más que mantener.

## 7. Avisos al iPhone (JARVIS habla sin que le pregunten)

JARVIS vigila por su cuenta y avisa al iPhone de:
- **Recordatorios**, a su hora.
- **Hora de salir** hacia una cita con lugar, calculada con el tráfico real
  ("Deberías salir ya hacia la reunión: hay 35 minutos con el tráfico de
  ahora"). El aviso abre la navegación.
- **Correo importante**: un modelo barato filtra el correo nuevo y solo avisa
  de lo que merece interrumpir (personas esperando respuesta, banco,
  clientes con problemas…), no de publicidad ni boletines.
- **Gasolina baja**, una sola vez hasta que reposte (`FUEL_ALERT_PERCENT`).
- **Rueda con poca presión**: si el coche marca aviso, o una rueda está
  claramente por debajo de las demás (pinchazo lento). Una vez, hasta que se infle.
- **Tienda**: pedido grande (`BIG_ORDER_AMOUNT`), pedidos pagados que llevan
  días sin enviarse (`STALE_ORDER_DAYS`) y productos que se acaban
  (`LOW_STOCK_THRESHOLD`).
- **Informe de la mañana** (`BRIEFING_TIME`, 8:00): citas del día, correo sin
  leer, ventas de ayer, pedidos por enviar, tiempo, y gasolina o ruedas si
  hace falta.
- **Cierre de la tienda** (`STORE_CLOSE_TIME`, 21:30): pedidos, facturación y
  ticket medio del día.

Para recibirlos:

- **Avisos propios de JARVIS** (lo más sencillo, sin apps aparte): abrir el
  panel desde su icono en la pantalla de inicio (paso 9) → **CONEXIONES** →
  *Avisos en este dispositivo* → *Activar avisos aquí*. Llegan con el icono de
  JARVIS. En el iPhone hace falta iOS 16.4 o posterior y abrirlo desde el icono.
- **Pushcut** (opcional, si se quiere que los lea en voz alta): instalar la app, crear una notificación llamada
  `JARVIS` y pegar el *Secret* (*Ajustes → API*) en Conexiones → *Avisos por
  Pushcut o ntfy*. Para que se oiga:
  - En el coche: si Pushcut aparece en *Ajustes → Notificaciones → Anunciar
    notificaciones*, activarlo; Siri leerá los avisos por CarPlay.
  - Fuera del coche: en la notificación `JARVIS` de Pushcut, añadir como
    acción un Atajo con **Leer texto [Entrada del atajo]**. Que se ejecute
    solo, sin tocar, requiere el *Automation Server* de Pushcut (de pago).
- **ntfy** (gratuita, solo notificación): instalar la app, suscribirse a un
  tema con un nombre largo e imposible de adivinar y ponerlo en `NTFY_TOPIC`.

## 8. El iPhone

En todas las peticiones a JARVIS, la acción **Obtener contenido de URL**
lleva la cabecera `Authorization` con el valor `Bearer TOKEN`.

Para reproducir la voz de JARVIS, en todos los casos:
**Obtener valor del diccionario** `audio` → **Codificar con Base64**
(modo *Decodificar*) → **Establecer nombre** `jarvis.mp3` →
**Reproducir sonido**. Si `audio` viene vacío, usar **Leer texto** con `text`.

### 8.1 Atajo "JARVIS" — hablar con él

App Atajos → nuevo atajo llamado exactamente **JARVIS** (así basta con
decir *"Oye Siri, JARVIS"*, también con el botón de voz del volante en CarPlay).

```
Obtener ubicación actual
Repetir 6 veces
    Dictar texto   (idioma: Español (España), dejar de escuchar: tras una pausa)
    Si [Texto dictado] no tiene ningún valor → Detener este atajo
    Obtener contenido de URL
        URL: TU_DIRECCIÓN/api/ask
        Método: POST
        Cabeceras: Authorization = Bearer TOKEN
        Cuerpo de la solicitud: JSON
            text = [Texto dictado]
            lat  = [Ubicación actual → Latitud]
            lon  = [Ubicación actual → Longitud]
    (reproducir la voz de JARVIS, ver arriba)
    Repetir con cada elemento de [client_actions]
        Si [type] es "send_whatsapp"
            Buscar contactos donde Nombre contiene [contact]
            WhatsApp: Enviar mensaje → destinatario: [Contactos], mensaje: [text]
        Si [type] es "navigate"
            Abrir URL [url]
        Si [type] es "call"
            Buscar contactos donde Nombre contiene [contact]
            Llamar a [Contactos]
        Si [type] es "run_shortcut"
            Codificar URL [name]
            Abrir URL  shortcuts://run-shortcut?name=[URL codificada]
    Fin de Repetir
    Obtener valor del diccionario  expects_reply
    Si [expects_reply] es falso → Detener este atajo
Fin de Repetir
```

Cómo se usa: *"Oye Siri, JARVIS"* → *"¿Tengo algo importante en el correo?"*.
Si JARVIS hace una pregunta (por ejemplo, *"¿Lo envío?"*), el atajo vuelve a
escuchar solo; si no, termina.

Las acciones de WhatsApp y de llamada pueden pedir permiso la primera vez:
conviene probarlas una vez con el coche parado.

**Atajos que JARVIS puede lanzar** (casa, música, escenas): crear cada uno
en la app Atajos (por ejemplo "Abrir garaje" con *Controlar Casa*, o "Música
tranquila" con *Reproducir música*) y poner sus nombres exactos en
`IPHONE_SHORTCUTS`, separados por comas. JARVIS solo puede lanzar esos.

### 8.2 Automatización — saludo al subir al coche

Atajos → *Automatización* → **CarPlay** → *Se conecta* → *Ejecutar inmediatamente*
(y desactivar *Notificar al ejecutar*):

```
Obtener ubicación actual
Obtener contenido de URL
    URL: TU_DIRECCIÓN/api/carplay/greeting?lat=[Latitud]&lon=[Longitud]
    Método: GET
    Cabeceras: Authorization = Bearer TOKEN
(reproducir la voz de JARVIS)
```

Resultado: *"Buenos días, Nacho. Depósito al 70 %, unos 412 km de autonomía.
Fuera hacen 8 grados. Tu próxima cita es a las 10:00: reunión con proveedores.
Tienes 3 correos sin leer. En la tienda hay 4 pedidos por enviar."*

La ubicación también sirve para que el aviso de "hora de salir" calcule la
ruta desde donde está de verdad (si no, usa casa).

### 8.3 Automatización — aviso de coche abierto

Atajos → *Automatización* → **CarPlay** → *Se desconecta* → *Ejecutar inmediatamente*:

```
Obtener contenido de URL  TU_DIRECCIÓN/api/car/left  (POST, misma cabecera)
```

JARVIS espera un minuto él mismo, consulta el cierre y, si el coche está
abierto, avisa al iPhone («Te has dejado el coche abierto…»). El iPhone no
tiene que esperar nada. La API de Mercedes solo permite consultar el cierre,
no cerrar. Si no se pudo consultar, no avisa: nunca da una alarma falsa.

### 8.4 WhatsApp entrantes en el coche

Los WhatsApp que le llegan no los puede leer JARVIS (WhatsApp no lo permite
a ningún programa). Los lee Siri:
*Ajustes → Notificaciones → Anunciar notificaciones → CarPlay* (activado) y
WhatsApp activado en esa misma lista. Siri los lee al llegar y deja contestar
por voz.

## 9. El panel de la tablet

No hay que arrancar nada aparte: el propio JARVIS sirve el panel. En la
tablet, abrir una vez `TU_DIRECCIÓN/?token=TOKEN` (el instalador muestra el
enlace completo al final); el navegador recuerda el token. Funciona en casa,
en la oficina o donde sea, y por HTTPS, que el navegador exige para usar el
micrófono.

**Como una app:** en el iPhone o la tablet, *Compartir → Añadir a pantalla de
inicio*. Queda con su icono, se abre a pantalla completa y ya entra con su
acceso. En el iPhone se ve en una columna, con el micrófono fijo abajo. Si el
Mac no responde, enseña «JARVIS está descansando» en vez de un error.

A la izquierda, la conversación (botón de micrófono). A la derecha, en vivo:
tiempo; depósito, cierre y presión de cada rueda del coche; agenda de hoy;
correo sin leer; ventas y pedidos por enviar; lo pendiente; **lo que JARVIS
ha hecho en su nombre** (correos, WhatsApp, citas, documentos, llamadas); y
el gasto del día. Se actualiza cada minuto y cada vez que JARVIS termina de
hablar. En la tablet, *Añadir a pantalla de inicio* para que se abra a
pantalla completa.

El registro completo de acciones está también en `/api/actions`.

Abajo, el botón **CONEXIONES** abre la sección donde Nacho conecta sus
cuentas y pega sus claves (ver el principio de esta guía).

## 10. Una voz propia para JARVIS

La voz por defecto es "George", una voz estándar de ElevenLabs. Para que
JARVIS tenga una voz suya (original: imitar la de un actor real no es legal):

1. En <https://elevenlabs.io>: *Voices → Add a new voice → Voice Design*.
2. Describirla, por ejemplo: *"Hombre de unos cincuenta años, voz grave,
   serena y elegante, español de España con un leve acento británico, tono de
   mayordomo culto con un punto de ironía"*.
3. Como texto de prueba, una frase típica: *"Buenos días, señor. Depósito al
   setenta por ciento y la primera reunión a las diez."*
4. Escuchar las variantes, guardar la que más guste y copiar su **Voice ID**
   en `ELEVENLABS_VOICE_ID`.

## 11. Llamadas en su nombre

JARVIS puede llamar por teléfono para reservar mesa, pedir cita o preguntar
horarios. Llama un agente de voz de ElevenLabs que empieza diciendo que es
el asistente de inteligencia artificial de Nacho. Habla en castellano y
cambia a catalán o francés si le contestan así.

1. **Un número para JARVIS** en <https://www.twilio.com>: crear la cuenta y
   comprar un número español (+34). Twilio no ofrece números de Andorra.
   Para los números españoles piden datos de una dirección en España.
   Copiar en `.env` el *Account SID*, el *Auth Token* y el número
   (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, con +34).
2. En el Mac: `./jarvis.sh llamadas`. Crea el agente en la cuenta de
   ElevenLabs de Nacho (con su misma voz), le conecta el número, guarda los ID
   en `.env` y reinicia JARVIS.
3. `./jarvis.sh diagnostico` debe mostrar "Llamadas en su nombre: Agente listo".

Cómo se usa: *"Resérvame mesa el sábado a las nueve en Borda Estevet para
cuatro"*. JARVIS busca el teléfono, pregunta lo que falte y dice qué va a
pedir y con qué margen (*"si no hay a las nueve, ¿te vale entre las ocho y
media y las nueve y media?"*). Solo llama cuando Nacho dice que sí. Al
colgar, avisa al iPhone con el resultado y, si quedó reservado, lo apunta en
el calendario. Cada llamada queda en el registro.

Límites: solo llama a negocios entre las 9:00 y las 22:00 (`CALL_HOURS`),
como mucho 5 llamadas al día (`MAX_CALLS_PER_DAY`) y 5 minutos cada una. No
acepta pagos ni señales ni da más datos que el nombre; el teléfono de
contacto solo si se pone en `OWNER_PHONE`. Cada llamada cuesta unos céntimos
por minuto, entre Twilio y ElevenLabs.

**Con número andorrano:** si Andorra Telecom ofrece una línea SIP para su
número, se da de alta en ElevenLabs (*Agents → Phone numbers → Import → SIP
trunk*), se pone su ID en `ELEVENLABS_PHONE_NUMBER_ID` y `CALL_PROVIDER=sip_trunk`.
JARVIS llamaría entonces con ese número.

## 12. La pulsera WHOOP

JARVIS lee de su WHOOP la recuperación de hoy, cómo ha dormido, el esfuerzo
del día y sus entrenamientos. Se lo cuenta en el resumen de la mañana, lo
muestra en el panel (tarjeta *SALUD*) y le responde si pregunta «¿cómo he
dormido?» o «¿me conviene entrenar fuerte hoy?». Solo lee: no cambia nada en
su cuenta, y no da consejos médicos.

1. Entrar en <https://developer-dashboard.whoop.com> con una cuenta de WHOOP
   (vale la de Nacho), crear un equipo si lo pide y después **Create App**:
   - Nombre: `JARVIS`. Si pide una página o política de privacidad:
     <https://goorum04.github.io/Jarvis/>.
   - *Scopes*: `read:recovery`, `read:cycles`, `read:sleep`, `read:workout` y
     `read:profile`.
   - *Redirect URIs*:
     - `http://localhost:8000/api/conexiones/whoop/callback`
     - `https://TU_DIRECCIÓN/api/conexiones/whoop/callback` (Tailscale, paso 6)
2. En el panel → **CONEXIONES** → *Pulsera WHOOP* → *Preparación*: pegar el
   **Client ID** y el **Client Secret** y guardar.
3. Nacho pulsa **Conectar**, entra con su cuenta de WHOOP y acepta.

WHOOP renueva el permiso cada hora y cambia la clave de renovación cada vez:
JARVIS guarda siempre la última él solo. Si alguna vez dejara de funcionar
(por ejemplo, si Nacho retira el acceso desde WHOOP), basta con *Volver a
conectar*.

## Protección

- **Límite de gasto diario** (`DAILY_BUDGET_USD`, 10 $ por defecto): al
  llegar, JARVIS avisa y deja de usar la IA hasta el día siguiente. El gasto
  del día se ve en el panel.
- **Límite de voz** (`DAILY_VOICE_CHARS`): pasado el límite, responde con
  texto y el iPhone lo lee con la voz de Siri.
- **Freno** (`REQUESTS_PER_MINUTE`): más preguntas de las normales en un
  minuto se rechazan, por si algo entra en bucle o alguien consigue el token.
- **Registro**: todo lo que JARVIS envía, crea o borra en su nombre queda
  apuntado con la hora.

---

## Qué se le puede pedir

- **Correo**: "¿Tengo correos importantes?", "¿Me ha escrito el banco esta
  semana?", "Léeme el de Laura", "Respóndele que adelante", "Escríbele a
  Pedro que mañana le llamo".
- **Agenda**: "¿Qué tengo hoy?", "¿Y mañana?", "Agéndame dentista el jueves
  a las cinco", "Cancela la reunión de las diez".
- **Conducir**: "Llévame a mi próxima cita", "Llévame a casa", "¿Cuánto
  tardo a la oficina?", "¿Cuánta gasolina tengo?", "¿Cerré el coche?",
  "¿Cómo están las ruedas?".
- **Documentos**: "Hazme un presupuesto para Laura con cuatro llantas R19 y
  el montaje", "Prepárame un resumen de la reunión de hoy" (y después
  "mándaselo a Laura").
- **Facturas**: "¿Cuánto le he pagado este mes a Neumáticos Pérez?", "¿Me ha
  llegado la factura de la luz?".
- **WhatsApp y llamadas** (desde el iPhone o el coche): "Dile a Marta que
  llego en diez minutos", "Llama a Laura".
- **Llamadas que hace JARVIS por él**: "Resérvame mesa el sábado en Borda
  Estevet para cuatro", "Pide cita en el taller para el martes por la mañana",
  "Llama a la farmacia y pregunta si abren hoy".
- **Tienda**: "¿Cuánto he vendido hoy?", "¿Y esta semana?", "¿Hay pedidos
  sin enviar?", "¿Qué es lo que más se vende este mes?", "¿Qué productos se
  están acabando?".
- **Internet**: "¿Cómo ha quedado el Madrid?", "Noticias de hoy", "¿A qué
  hora cierra el taller Pérez?".
- **Casa y música**: "Abre el garaje", "Pon música tranquila" (los Atajos de
  `IPHONE_SHORTCUTS`).
- **Tiempo, tareas, recordatorios y notas**: "Recuérdame a las seis llamar al
  taller", "¿Qué tengo pendiente?", "Apunta que el código del garaje es 4821".
- **Memoria**: "Recuerda que el café lo tomo solo" (lo sabrá siempre),
  "¿Qué te dije ayer del taller?", "¿De qué hablamos el lunes?".

Enviar correos, enviar WhatsApp, llamar en su nombre y borrar citas van **siempre en dos pasos**:
JARVIS lo prepara, lo lee en voz alta y solo lo ejecuta si Nacho responde
que sí en el siguiente mensaje. El servidor lo impone: aunque el modelo se
equivocara, no puede enviar nada en el mismo turno en que lo redacta.
