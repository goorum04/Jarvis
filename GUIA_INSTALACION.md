# Guía de instalación de JARVIS

Lista de pasos, en orden, para dejar JARVIS funcionando en el Mac de Nacho.
Los detalles de cada servicio están en **[CONFIGURAR_JARVIS.md](CONFIGURAR_JARVIS.md)**
(cada paso indica qué apartado). La guía para Nacho, la de uso, está en el
propio panel (botón **GUÍA**) y en [`guia/index.html`](guia/index.html).

Tiempo aproximado: una hora de preparación desde tu ordenador y una hora y
media en casa de Nacho, con él delante para la parte de sus cuentas.

---

## Qué hace falta

- El **Mac de Nacho** (portátil), que se quedará en casa **enchufado y con la tapa abierta**.
- Su **iPhone**, y la tablet si va a tener panel fijo.
- **Nacho delante** en la parte C: él inicia sesión en sus cuentas y pega sus claves. Tú no tienes que verlas.

### Cuentas

Lo ideal es que las de pago estén **a nombre de Nacho y con su tarjeta**:
así pega él las claves en el panel y nadie más las tiene.

| Servicio | Para qué | Pago | Obligatorio |
|---|---|---|---|
| [Anthropic](https://console.anthropic.com) | El cerebro (Claude) | Por uso; JARVIS se para al llegar al tope diario (10 $ por defecto) | Sí |
| [ElevenLabs](https://elevenlabs.io) | Su voz y las llamadas | Suscripción mensual | Recomendado (si no, habla con la voz de Siri) |
| [Tailscale](https://tailscale.com) | Llegar al Mac desde fuera de casa, con HTTPS | Gratis | Sí |
| [Google Cloud](https://console.cloud.google.com) | Gmail, Calendar y Docs; tráfico y rutas | Gmail gratis; rutas por uso | Recomendado |
| [Mercedes developer](https://developer.mercedes-benz.com) | Gasolina, cierre y ruedas | — | Opcional |
| [WHOOP developer](https://developer-dashboard.whoop.com) | Sueño, recuperación y esfuerzo | — | Opcional |
| [Pushcut](https://www.pushcut.io) (app del iPhone) | Avisos al iPhone | App gratis | Recomendado |
| [Twilio](https://www.twilio.com) | Número para las llamadas en su nombre | Número mensual + minutos | Opcional |
| Su tienda (WooCommerce o Shopify) | Ventas y pedidos | Ya la tiene | Opcional |

Cada parte funciona por separado: lo que no se conecte, JARVIS simplemente no lo menciona.

---

## A. Antes de ir: preparar las apps (desde tu ordenador)

Son las «identidades» de JARVIS en Google, Mercedes y WHOOP. No dan acceso a
nada de Nacho hasta que él pulsa *Conectar* y acepta.

- [ ] **Google Cloud** (CONFIGURAR §2 y §3), con la cuenta de Google de Nacho:
      proyecto, APIs de Gmail, Calendar, Docs y Routes, pantalla de consentimiento
      **publicada** (si se queda en «Prueba», el permiso caduca a los 7 días),
      cliente OAuth tipo **Aplicación web** y una clave de API para Routes.
      Redirección por ahora: `http://localhost:8000/api/conexiones/google/callback`.
- [ ] **Mercedes** (CONFIGURAR §4): proyecto con la Vehicle Status API.
      URL de propósito: <https://goorum04.github.io/Jarvis/>.
      Redirección: `http://localhost:8000/api/conexiones/mercedes/callback`.
- [ ] **WHOOP** (CONFIGURAR §12): app con los permisos de lectura.
      Redirección: `http://localhost:8000/api/conexiones/whoop/callback`.
- [ ] **Twilio**, si va a usar llamadas (CONFIGURAR §11): pedir **cuanto antes**
      el número español; Twilio pide una dirección en España y puede tardar días.
- [ ] **Voz propia**, opcional (CONFIGURAR §10): diseñarla en ElevenLabs y apuntar su Voice ID.

Apunta en un sitio seguro los ID y secretos de cliente de Google, Mercedes y
WHOOP: los pegarás en el panel en el paso B.5.

## B. En el Mac de Nacho

- [ ] **1. Bajar JARVIS** a su carpeta personal (no en Documentos, Escritorio
      ni Descargas). En Terminal:
      ```
      git clone https://github.com/goorum04/Jarvis.git ~/JARVIS
      ```
      Si el Mac pide instalar las «herramientas de línea de comandos», aceptar y
      repetir el comando.
- [ ] **2. Tailscale**: instalarlo (<https://tailscale.com/download/mac>) e iniciar sesión.
- [ ] **3. Instalar**:
      ```
      cd ~/JARVIS
      bash instalar.command
      ```
      La primera vez Tailscale muestra un enlace para activar *Funnel*: abrirlo,
      aceptar y volver a ejecutar el instalador. Al final muestra la
      **dirección** (`https://….ts.net`), el **enlace del panel** y el **token**.
- [ ] **4. Añadir la dirección pública** a las redirecciones de Google, Mercedes
      y WHOOP (la misma ruta que en la parte A, cambiando
      `http://localhost:8000` por `https://….ts.net`). Así Nacho podrá conectar
      desde el iPhone, no solo desde el Mac.
- [ ] **5. Abrir el panel** con el enlace que dio el instalador → **CONEXIONES** →
      en *Gmail*, *Mercedes me* y *Pulsera WHOOP*, abrir **Preparación** y pegar
      el ID y el secreto de cliente de cada una.
- [ ] **6. Energía**: en Ajustes del Sistema → Batería → *Opciones*, activar la
      opción que evita el reposo automático con el adaptador de corriente cuando
      la pantalla está apagada. JARVIS ya evita el reposo por inactividad, pero
      así queda doblemente asegurado. Recordarle a Nacho: **tapa abierta**.

## C. Con Nacho: sus cuentas (panel → CONEXIONES)

Que lo haga él desde su iPhone o desde el Mac. Cada tarjeta dice si está
conectada; con *Probar* se comprueba contra el servicio real.

- [ ] **Cerebro (Claude)**: crea la clave en su cuenta de Anthropic y la pega.
- [ ] **Voz (ElevenLabs)**: pega su clave (y el Voice ID si hay voz propia).
- [ ] **Gmail, Calendar y Docs**: *Conectar*, entra con su Google y acepta todas
      las casillas. Si Google avisa de «app no verificada»: *Configuración
      avanzada → Ir a JARVIS*.
- [ ] **Mercedes me**: escribe el VIN (campo E del permiso de circulación),
      guarda y *Conectar*.
- [ ] **Pulsera WHOOP**: *Conectar* con su cuenta de WHOOP.
- [ ] **Tienda**: WooCommerce con *Conectar* (aprueba el acceso de lectura en su
      tienda), o Shopify pegando el token (CONFIGURAR §5).
- [ ] **Casa y trabajo**: direcciones y coordenadas de casa.
- [ ] **Tráfico y rutas**: la clave de Routes de la parte A.
- [ ] **Avisos al iPhone**: el *Secret* de Pushcut (en el paso D.1).
- [ ] **Llamadas**: datos de Twilio → *Guardar* → **Preparar llamadas**.

Al guardar, JARVIS se reinicia solo unos segundos para aplicar los cambios.

## D. Su iPhone (y la tablet)

Detalle en CONFIGURAR §7 y §8. Hacen falta la dirección y el token del paso B.3.

- [ ] **1. Pushcut**: instalar la app, crear una notificación llamada `JARVIS` y
      copiar el *Secret* (*Ajustes → API*) en Conexiones → Avisos.
- [ ] **2. Atajo «JARVIS»** (CONFIGURAR §8.1), con ese nombre exacto para que
      baste con decir «Oye Siri, JARVIS».
- [ ] **3. Automatización CarPlay → Se conecta**: saludo al subir al coche (§8.2).
- [ ] **4. Automatización CarPlay → Se desconecta**: aviso de coche abierto (§8.3).
- [ ] **5. Anunciar notificaciones** en CarPlay, con WhatsApp y Pushcut activados (§7 y §8.4).
- [ ] **6. Atajos de casa y música**, opcional: crearlos y poner sus nombres en
      `IPHONE_SHORTCUTS` en el `.env` (§8.1), y `./jarvis.sh reiniciar`.
- [ ] **7. Panel en la pantalla de inicio**: abrir en Safari el enlace del panel
      (con `?token=`) → Compartir → *Añadir a pantalla de inicio*. Igual en la tablet.

## E. Comprobar

- [ ] En el Mac: `./jarvis.sh diagnostico --probar-avisos`. Todo en ✅ salvo lo
      que no se haya querido conectar; debe llegar un aviso de prueba al iPhone.
- [ ] «Oye Siri, JARVIS» → «¿Qué tengo hoy?»: responde con su agenda real.
- [ ] «¿Tengo correos importantes?» y «Escríbeme un correo a mí mismo que diga
      prueba»: debe leerlo y **preguntar antes de enviarlo**.
- [ ] Con el coche parado: subir, conectar CarPlay y oír el saludo. «¿Cuánta gasolina tengo?».
- [ ] «¿Cómo he dormido?» (si tiene WHOOP conectada).
- [ ] Con el coche parado: «Dile a [alguien de confianza] que es una prueba» y
      «Llama a [alguien]». La primera vez el iPhone pide permisos.
- [ ] Si hay llamadas: una reserva de prueba a un negocio de confianza, en horario de 9:00 a 22:00.

## F. Entregar

- [ ] Enseñarle a Nacho el botón **GUÍA** del panel: ahí tiene todo lo que puede pedirle.
- [ ] Recordarle: **Mac en casa, enchufado y con la tapa abierta**.
- [ ] Dejarle claro que puede ver todo lo que JARVIS ha hecho en su nombre en el
      panel, y retirar cualquier conexión con *Desconectar*.

---

## Mantenimiento

```
./jarvis.sh estado        # ¿está en marcha?
./jarvis.sh logs          # registro en directo
./jarvis.sh diagnostico   # revisa cada pieza contra los servicios reales
./jarvis.sh reiniciar     # tras cambiar el .env a mano
./jarvis.sh actualizar    # baja la última versión e instala
```

Todo se hace desde la carpeta `~/JARVIS`. Actualizar no borra claves, conexiones ni conversaciones.

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| Siri: «hubo un problema con el atajo» | Mac cerrado, dormido o sin internet; o Tailscale cerrado | Abrir el Mac; `./jarvis.sh estado`; comprobar que Tailscale está abierto y `tailscale funnel status` |
| Google o Mercedes: «redirect_uri_mismatch» al conectar | La dirección de vuelta no está registrada **exactamente** igual | Revisar las redirecciones (parte A y B.4). `localhost` y `127.0.0.1` cuentan como distintas: abrir el panel con `localhost` |
| El correo deja de funcionar a los 7 días | Pantalla de consentimiento de Google en modo «Prueba» | Publicarla (CONFIGURAR §2) y *Volver a conectar* |
| Conectar la tienda WooCommerce no deja | Falta la dirección pública activa | Terminar B.3 (Funnel) |
| El panel dice «no tiene el acceso de JARVIS» | Abierto sin el token | Abrir el enlace con `?token=` del instalador |
| Los avisos no llegan | Pushcut sin conectar o notificaciones desactivadas | Conexiones → Avisos → *Probar*; revisar los ajustes del iPhone |
| Los datos del coche no salen | Nombres de campos de Mercedes distintos | `./jarvis.sh logs` muestra el JSON de Mercedes; ajustar `car.py` (CONFIGURAR §4) |
