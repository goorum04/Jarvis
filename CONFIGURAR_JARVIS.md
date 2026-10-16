# Configurar JARVIS para Nacho

El cerebro de JARVIS vive en su PC. El iPhone y el coche (CarPlay) solo
escuchan y hablan, a través de Siri y de Atajos de iOS. Esta guía cubre lo
que hay que hacer una sola vez para dejarlo funcionando.

Orden recomendado: **1 → 2 → 3 → 4 → 5**. Cada paso funciona por separado:
si algo no está configurado, JARVIS simplemente no lo menciona.

---

## 1. El PC

1. Instalar dependencias: doble clic en `instalar.bat` (o `pip install -r requirements.txt`).
2. Copiar `.env.example` como `.env` y rellenar al menos:
   - `CLAUDE_API_KEY` y `ELEVENLABS_API_KEY`
   - `JARVIS_API_TOKEN`: una contraseña larga y aleatoria. Es la llave para
     hablar con JARVIS desde fuera de casa; sin ella cualquiera podría usarlo.
   - `HOME_LAT` / `HOME_LON`: coordenadas de su casa (para el tiempo).
3. Arrancar: `iniciar_backend.bat`.

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

## 3. El Mercedes

1. Registrarse en <https://developer.mercedes-benz.com> y crear una app con
   acceso a la **Vehicle Status API** para el VIN del C63.
2. Completar el flujo OAuth de Mercedes para obtener un *refresh token*.
3. Rellenar en `.env`: `MERCEDES_CLIENT_ID`, `MERCEDES_CLIENT_SECRET`,
   `MERCEDES_REFRESH_TOKEN` y `MERCEDES_VIN`.

Los nombres exactos de los campos de esa API hay que confirmarlos con su
documentación (ver el comentario al principio de `car.py`). Si alguno no
coincide, el error queda en la consola del backend con el JSON que devuelve
Mercedes, y se ajusta en un minuto.

## 4. Acceso desde fuera de casa

El iPhone tiene que llegar al PC estando en la calle o en el coche:

- Un subdominio de su web, por ejemplo `jarvis.sudominio.com`, apuntando a
  la IP de casa (con DNS dinámico, porque la IP de casa cambia).
- **Caddy** en el PC como proxy: pide el certificado HTTPS solo y reenvía a
  `localhost:8000`. iOS exige HTTPS.
- Abrir el puerto 443 del router hacia el PC.

En el resto de la guía, `https://jarvis.sudominio.com` es esa dirección y
`TOKEN` es el valor de `JARVIS_API_TOKEN`.

## 5. El iPhone

En todas las peticiones a JARVIS, la acción **Obtener contenido de URL**
lleva la cabecera `Authorization` con el valor `Bearer TOKEN`.

Para reproducir la voz de JARVIS, en todos los casos:
**Obtener valor del diccionario** `audio` → **Codificar con Base64**
(modo *Decodificar*) → **Establecer nombre** `jarvis.mp3` →
**Reproducir sonido**. Si `audio` viene vacío, usar **Leer texto** con `text`.

### 5.1 Atajo "JARVIS" — hablar con él

App Atajos → nuevo atajo llamado exactamente **JARVIS** (así basta con
decir *"Oye Siri, JARVIS"*, también con el botón de voz del volante en CarPlay).

```
Repetir 6 veces
    Dictar texto   (idioma: Español (España), dejar de escuchar: tras una pausa)
    Si [Texto dictado] no tiene ningún valor → Detener este atajo
    Obtener contenido de URL
        URL: https://jarvis.sudominio.com/api/ask
        Método: POST
        Cabeceras: Authorization = Bearer TOKEN
        Cuerpo de la solicitud: JSON → text = [Texto dictado]
    (reproducir la voz de JARVIS, ver arriba)
    Obtener valor del diccionario  client_action
    Si [client_action] tiene algún valor
        Buscar contactos donde Nombre contiene [client_action → contact]
        WhatsApp: Enviar mensaje  → destinatario: [Contactos], mensaje: [client_action → text]
    Obtener valor del diccionario  expects_reply
    Si [expects_reply] es falso → Detener este atajo
Fin de Repetir
```

Cómo se usa: *"Oye Siri, JARVIS"* → *"¿Tengo algo importante en el correo?"*.
Si JARVIS hace una pregunta (por ejemplo, *"¿Lo envío?"*), el atajo vuelve a
escuchar solo; si no, termina.

La acción de WhatsApp aparece en Atajos cuando WhatsApp está instalado. La
primera vez puede pedir permiso: conviene probarla una vez con el coche parado.

### 5.2 Automatización — saludo al subir al coche

Atajos → *Automatización* → **CarPlay** → *Se conecta* → *Ejecutar inmediatamente*
(y desactivar *Notificar al ejecutar*):

```
Obtener contenido de URL
    URL: https://jarvis.sudominio.com/api/carplay/greeting
    Método: GET
    Cabeceras: Authorization = Bearer TOKEN
(reproducir la voz de JARVIS)
```

Resultado: *"Buenos días, Nacho. Depósito al 70 %, unos 412 km de autonomía.
Fuera hacen 8 grados. Tu próxima cita es a las 10:00: reunión con proveedores.
Tienes 3 correos sin leer."*

### 5.3 Automatización — aviso de coche abierto

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

### 5.4 WhatsApp entrantes en el coche

Los WhatsApp que le llegan no los puede leer JARVIS (WhatsApp no lo permite
a ningún programa). Los lee Siri:
*Ajustes → Notificaciones → Anunciar notificaciones → CarPlay* (activado) y
WhatsApp activado en esa misma lista. Siri los lee al llegar y deja contestar
por voz.

---

## Qué se le puede pedir

- **Correo**: "¿Tengo correos importantes?", "¿Me ha escrito el banco esta
  semana?", "Léeme el de Laura", "Respóndele que adelante", "Escríbele a
  Pedro que mañana le llamo".
- **Agenda**: "¿Qué tengo hoy?", "¿Y mañana?", "Agéndame dentista el jueves
  a las cinco", "Cancela la reunión de las diez".
- **WhatsApp** (desde el iPhone o el coche): "Dile a Marta que llego en diez minutos".
- **Coche**: "¿Cuánta gasolina tengo?", "¿Cerré el coche?".
- **Tiempo, tareas, recordatorios y notas**: "Recuérdame a las seis llamar al
  taller", "¿Qué tengo pendiente?", "Apunta que el código del garaje es 4821".
- **Preferencias**: "Recuerda que el café lo tomo solo". Lo sabrá siempre.

Enviar correos, enviar WhatsApp y borrar citas van **siempre en dos pasos**:
JARVIS lo prepara, lo lee en voz alta y solo lo ejecuta si Nacho responde
que sí en el siguiente mensaje. El servidor lo impone: aunque el modelo se
equivocara, no puede enviar nada en el mismo turno en que lo redacta.
