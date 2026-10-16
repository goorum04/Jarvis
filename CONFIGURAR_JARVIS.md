# Configurar JARVIS para Nacho

El cerebro de JARVIS vive en su PC. El iPhone y el coche (CarPlay) escuchan
y hablan a través de Siri y de Atajos de iOS; una tablet en casa u oficina
hace de panel permanente. Esta guía cubre lo que hay que hacer una sola vez.

Cada parte funciona por separado: si algo no está configurado, JARVIS
simplemente no lo menciona. Orden recomendado: del 1 al 9.

---

## 1. El PC

1. Instalar dependencias: doble clic en `instalar.bat` (o `pip install -r requirements.txt`).
2. Copiar `.env.example` como `.env` y rellenar al menos:
   - `CLAUDE_API_KEY` y `ELEVENLABS_API_KEY`
   - `JARVIS_API_TOKEN`: una contraseña larga y aleatoria. Es la llave para
     hablar con JARVIS desde fuera de casa; sin ella cualquiera podría usarlo.
   - `HOME_LAT`, `HOME_LON` y `HOME_ADDRESS` (casa) y `WORK_ADDRESS` (oficina).
3. Arrancar: `iniciar_backend.bat`.

**El PC tiene que estar siempre encendido**: si se suspende, JARVIS deja de
responder y de avisar.
- *Configuración → Sistema → Inicio/apagado → Suspender*: **Nunca** (con corriente).
- Que arranque solo: *Programador de tareas → Crear tarea básica → Al iniciar
  sesión → Iniciar un programa → `iniciar_backend.bat`*.
- Alternativa más fiable: un mini-PC dedicado, encendido siempre.

## 2. Gmail y Google Calendar

Se hace en <https://console.cloud.google.com> con la cuenta de Gmail de Nacho.

1. Crear un proyecto nuevo (por ejemplo, "JARVIS").
2. *APIs y servicios → Biblioteca*: activar **Gmail API** y **Google Calendar API**.
3. *APIs y servicios → Pantalla de consentimiento de OAuth*:
   - Tipo de usuario: **Externo**. Nombre de la app: JARVIS.
   - Añadir su propio correo como usuario de prueba.
   - Al terminar, pulsar **Publicar aplicación** (pasarla a "En producción").
     Si se queda en modo "Prueba", Google caduca el permiso cada 7 días y
     JARVIS dejaría de ver el correo.
4. *APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth*:
   tipo **Aplicación de escritorio**. Descargar el JSON, renombrarlo a
   `google_credentials.json` y dejarlo en la carpeta de JARVIS.
5. En el PC: `python autorizar_google.py`. Se abre el navegador; Nacho entra
   con su cuenta y acepta. Como la app es suya y no está verificada por
   Google, saldrá un aviso: *Configuración avanzada → Ir a JARVIS*.
   Queda guardado `google_token.json` y ya no hay que repetirlo.

Ninguno de esos dos archivos se sube al repositorio (están en `.gitignore`).

## 3. Tráfico y navegación

En el mismo proyecto de Google Cloud: *Biblioteca* → activar **Routes API**;
*Credenciales → Crear credenciales → Clave de API* (restringirla a Routes API)
y ponerla en `GOOGLE_MAPS_API_KEY`. Es de pago por uso; JARVIS solo calcula
rutas para las citas que tienen lugar y como mucho cada 15 minutos.

`NAV_APP` elige qué app se abre al navegar: `apple`, `google` o `waze`.

## 4. El Mercedes

1. Registrarse en <https://developer.mercedes-benz.com> y crear una app con
   acceso a la **Vehicle Status API** para el VIN del C63.
2. Completar el flujo OAuth de Mercedes para obtener un *refresh token*.
3. Rellenar en `.env`: `MERCEDES_CLIENT_ID`, `MERCEDES_CLIENT_SECRET`,
   `MERCEDES_REFRESH_TOKEN` y `MERCEDES_VIN`.

Los nombres exactos de los campos de esa API hay que confirmarlos con su
documentación (ver el comentario al principio de `car.py`). Si alguno no
coincide, el error queda en la consola del backend con el JSON que devuelve
Mercedes, y se ajusta en un minuto.

## 5. La tienda online

Con permisos **solo de lectura**: JARVIS consulta ventas y pedidos, no toca nada.

- **Shopify**: *Configuración → Apps y canales de venta → Desarrollar apps →
  Crear una app* → permisos de Admin API: `read_orders` → instalar y copiar el
  *token de acceso de Admin API*. En `.env`: `STORE_PLATFORM=shopify`,
  `SHOPIFY_SHOP=sutienda.myshopify.com`, `SHOPIFY_ACCESS_TOKEN=...`.
- **WooCommerce**: *WooCommerce → Ajustes → Avanzado → API REST → Añadir clave*,
  permisos **Lectura**. En `.env`: `STORE_PLATFORM=woocommerce`, `WOO_URL`,
  `WOO_CONSUMER_KEY`, `WOO_CONSUMER_SECRET`.

## 6. Acceso desde fuera de casa

El iPhone tiene que llegar al PC estando en la calle o en el coche:

- Un subdominio de su web, por ejemplo `jarvis.sudominio.com`, apuntando a
  la IP de casa (con DNS dinámico, porque la IP de casa cambia).
- **Caddy** en el PC como proxy: pide el certificado HTTPS solo y reenvía a
  `localhost:8000`. iOS exige HTTPS.
- Abrir el puerto 443 del router hacia el PC.

En el resto de la guía, `https://jarvis.sudominio.com` es esa dirección y
`TOKEN` es el valor de `JARVIS_API_TOKEN`.

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

Para recibirlos, una de las dos:

- **Pushcut** (recomendada): instalar la app, crear una notificación llamada
  `JARVIS` y copiar en `.env` el *Secret* (*Ajustes → API*). Para que se oiga:
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
        URL: https://jarvis.sudominio.com/api/ask
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
    URL: https://jarvis.sudominio.com/api/carplay/greeting?lat=[Latitud]&lon=[Longitud]
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
Esperar 60 segundos
Obtener contenido de URL  https://jarvis.sudominio.com/api/car/status  (GET, misma cabecera)
Obtener valor del diccionario  locked
Si [locked] es falso
    Mostrar notificación: "El coche está abierto. Ciérralo desde Mercedes me."
```

La API de Mercedes solo permite consultar el cierre, no cerrar. Si `locked`
viene vacío (no se pudo consultar), no avisa: nunca da una alarma falsa.

### 8.4 WhatsApp entrantes en el coche

Los WhatsApp que le llegan no los puede leer JARVIS (WhatsApp no lo permite
a ningún programa). Los lee Siri:
*Ajustes → Notificaciones → Anunciar notificaciones → CarPlay* (activado) y
WhatsApp activado en esa misma lista. Siri los lee al llegar y deja contestar
por voz.

## 9. El panel de la tablet

En el PC: `iniciar_frontend.bat`. En la tablet (misma WiFi), abrir una vez
`http://IP-DEL-PC:3000/?token=TOKEN`; el navegador recuerda el token.
Desde fuera de casa: `?token=TOKEN&api=https://jarvis.sudominio.com`.

A la izquierda, la conversación (botón de micrófono). A la derecha, en vivo:
tiempo, depósito y cierre del coche, agenda de hoy, correo sin leer, ventas
y pedidos por enviar, y lo pendiente. Se actualiza cada minuto y cada vez
que JARVIS termina de hablar. En la tablet, *Añadir a pantalla de inicio*
para que se abra a pantalla completa.

---

## Qué se le puede pedir

- **Correo**: "¿Tengo correos importantes?", "¿Me ha escrito el banco esta
  semana?", "Léeme el de Laura", "Respóndele que adelante", "Escríbele a
  Pedro que mañana le llamo".
- **Agenda**: "¿Qué tengo hoy?", "¿Y mañana?", "Agéndame dentista el jueves
  a las cinco", "Cancela la reunión de las diez".
- **Conducir**: "Llévame a mi próxima cita", "Llévame a casa", "¿Cuánto
  tardo a la oficina?", "¿Cuánta gasolina tengo?", "¿Cerré el coche?".
- **WhatsApp y llamadas** (desde el iPhone o el coche): "Dile a Marta que
  llego en diez minutos", "Llama a Laura".
- **Tienda**: "¿Cuánto he vendido hoy?", "¿Y esta semana?", "¿Hay pedidos
  sin enviar?", "¿Qué es lo que más se vende este mes?".
- **Internet**: "¿Cómo ha quedado el Madrid?", "Noticias de hoy", "¿A qué
  hora cierra el taller Pérez?".
- **Casa y música**: "Abre el garaje", "Pon música tranquila" (los Atajos de
  `IPHONE_SHORTCUTS`).
- **Tiempo, tareas, recordatorios y notas**: "Recuérdame a las seis llamar al
  taller", "¿Qué tengo pendiente?", "Apunta que el código del garaje es 4821".
- **Memoria**: "Recuerda que el café lo tomo solo" (lo sabrá siempre),
  "¿Qué te dije ayer del taller?", "¿De qué hablamos el lunes?".

Enviar correos, enviar WhatsApp y borrar citas van **siempre en dos pasos**:
JARVIS lo prepara, lo lee en voz alta y solo lo ejecuta si Nacho responde
que sí en el siguiente mensaje. El servidor lo impone: aunque el modelo se
equivocara, no puede enviar nada en el mismo turno en que lo redacta.
