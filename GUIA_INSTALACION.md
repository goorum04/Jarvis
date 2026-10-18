# Guía de instalación de JARVIS

Lista de pasos, en orden, para dejar JARVIS funcionando en el Mac de Nacho.
Los detalles de cada servicio están en **[CONFIGURAR_JARVIS.md](CONFIGURAR_JARVIS.md)**
(cada paso indica qué apartado). La guía para Nacho, la de uso, está en el
propio panel (botón **GUÍA**) y en [`guia/index.html`](guia/index.html).

Hay dos formas de instalarlo:

- **A distancia: lo instala Nacho solo** con su guía,
  <https://goorum04.github.io/Jarvis/instalar/>. Tú preparas las apps y le
  envías el enlace y un código. Ver el apartado siguiente.
- **En persona**: sigues tú las partes A a F de abajo, con Nacho delante para
  sus cuentas. Una hora de preparación y una hora y media en su casa.

---

## Instalación a distancia (la hace Nacho)

Nacho solo tiene que pegar una línea en la Terminal y seguir su guía. Tú
preparas antes tres cosas y se las envías.

### 1. Preparar las apps

La parte A de abajo: Google Cloud, Mercedes y WHOOP (y Twilio si va a usar
llamadas). Con la redirección de `localhost` basta: en su guía, Nacho conecta
las cuentas desde el panel en su Mac, y el instalador ya le abre el panel con
`localhost`.

### 2. Los tres Atajos del iPhone, para compartirlos

Se crean una vez en **tu** iPhone y se comparten por iCloud. Al añadirlos,
el iPhone de Nacho le pregunta su dirección y su token, que copia de su panel
(*Conexiones → Tu iPhone*).

| Atajo | Qué hace | Contenido |
|---|---|---|
| **JARVIS** | Hablar con él: «Oye Siri, JARVIS» | CONFIGURAR §8.1 |
| **JARVIS saludo** | Saludo al conectar CarPlay | Lo de dentro de la automatización de §8.2 |
| **JARVIS coche** | Aviso de coche abierto al desconectar CarPlay | Lo de dentro de la automatización de §8.3 |

Para que sirvan a cualquiera:

1. Al principio de cada atajo, dos acciones **Texto**: una con una dirección
   cualquiera (`https://ejemplo.ts.net`) y otra con un token cualquiera. En el
   resto del atajo, usa esas dos variables donde §8 pone `TU_DIRECCIÓN` y `TOKEN`.
2. En cada atajo: **ⓘ (Detalles) → Configurar → Preguntas de importación →
   Añadir pregunta** para cada una de esas dos acciones Texto, con las
   preguntas «Dirección de JARVIS» y «Token de JARVIS».
3. **Compartir → Copiar enlace de iCloud.** Los tres enlaces empiezan por
   `https://www.icloud.com/shortcuts/`.

Pruébalos antes en tu iPhone, añadiéndolos con los datos de un JARVIS de
pruebas, o con los de Nacho cuando ya lo tenga instalado.

### 3. El código de preparación

En <https://goorum04.github.io/Jarvis/preparar/> pega los ID y secretos de
cliente de Google, Mercedes y WHOOP, la clave de Routes y los tres enlaces de
los atajos, y pulsa **Generar código**. Se genera en tu navegador: no se envía
nada a ningún sitio. El resultado empieza por `JARVIS1:`.

Si falta algo (por ejemplo, Mercedes aún no ha aprobado el proyecto), genera
el código con lo que tengas. Más adelante le mandas otro solo con lo nuevo:
pegarlo no borra lo que ya tenía.

### 4. Enviárselo

- El enlace de su guía: <https://goorum04.github.io/Jarvis/instalar/>
- El código de preparación, **en un mensaje privado aparte**. Que lo borre
  cuando lo haya pegado.

Su guía le lleva por: Tailscale → la línea de la Terminal → el código → sus
cuentas → Pushcut → el iPhone (QR del panel, atajos y automatizaciones de
CarPlay) → probarlo. Si algo falla, te mandará una foto de la pantalla.

### 5. Después

- Pídele la dirección pública que sale en *Conexiones → Tu iPhone* y añádela a
  las redirecciones de Google, Mercedes y WHOOP (parte B.4). Así podrá
  reconectar cuentas también desde el iPhone.
- Lo que queda fuera de su guía, y es mejor hacerlo con él: la tienda
  Shopify, las llamadas (Twilio) y los Atajos de casa y música.

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
WHOOP: van en el código de preparación (paso B.3).

## B. En el Mac de Nacho

- [ ] **1. Tailscale**: instalarlo (<https://tailscale.com/download/mac>) e iniciar sesión.
- [ ] **2. Instalar JARVIS**: en la Terminal, pegar la línea de la guía de
      Nacho (la descarga en `~/JARVIS`, sin necesidad de git, y la instala):
      ```
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/goorum04/Jarvis/main/instalar_jarvis.sh)"
      ```
      La primera vez Tailscale muestra un enlace para activar *Funnel*: abrirlo,
      aceptar y, si lo pide, volver a pegar la línea. Al final muestra la
      **dirección** (`https://….ts.net`), los enlaces del panel y el **token**, y
      abre el panel en el navegador.
- [ ] **3. Código de preparación** (o, a mano, el apartado *Preparación* de las
      tarjetas de Gmail, Mercedes y WHOOP): generarlo en
      <https://goorum04.github.io/Jarvis/preparar/> y pegarlo en el panel →
      **CONEXIONES** → *Código de preparación*.
- [ ] **4. Añadir la dirección pública** a las redirecciones de Google, Mercedes
      y WHOOP (la misma ruta que en la parte A, cambiando
      `http://localhost:8000` por `https://….ts.net`). Así Nacho podrá conectar
      desde el iPhone, no solo desde el Mac.
- [ ] **5. Energía**: en Ajustes del Sistema → Batería → *Opciones*, activar la
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

Detalle en CONFIGURAR §7 y §8. Hacen falta la dirección y el token del paso B.2 (también en el panel → Conexiones → Tu iPhone).

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

## Más adelante: JARVIS en la nube, activo 24/7

El plan es pasar JARVIS a la nube para que funcione siempre, aunque Nacho
cierre el portátil o se lo lleve de viaje. Para él no cambiará nada: el mismo
«Oye Siri, JARVIS», el mismo panel y la misma memoria.

JARVIS ya está preparado para moverse: toda su configuración y sus datos
están en su carpeta. Cuando llegue el momento:

- [ ] **Servidor privado**, solo para Nacho, en Europa (por cercanía y por
      protección de datos). El instalador actual es para Mac; para un servidor
      Linux habrá que preparar su versión (arranque automático como servicio
      del sistema).
- [ ] **Copiar la carpeta entera** con lo que no está en el repositorio:
      `.env` (claves), `google_token.json`, `conexiones.json` y
      `jarvis_memory.db` (conversaciones, recordatorios y memoria).
- [ ] **Dirección fija**: mejor con un dominio propio (por ejemplo
      `jarvis.sudominio.com`), para que no vuelva a cambiar aunque se cambie de
      servidor. Tailscale Funnel también funciona en un servidor.
- [ ] **Actualizar la dirección** en las redirecciones de Google, Mercedes y
      WHOOP, en los Atajos y automatizaciones del iPhone y en el panel de la
      pantalla de inicio (y `PUBLIC_URL` en el `.env`).
- [ ] **Actualizar la página del proyecto** (`proyecto/index.html`): ahora dice
      que los datos se guardan en el ordenador del titular.
- [ ] **Apagar JARVIS en el Mac** (`./jarvis.sh desinstalar`) en cuanto el del
      servidor funcione: dos JARVIS a la vez mandarían los avisos repetidos y se
      pisarían los permisos de WHOOP y Mercedes, que cambian en cada renovación.

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
| Conectar la tienda WooCommerce no deja | Falta la dirección pública activa | Terminar B.2 (Funnel) |
| El panel dice «no tiene el acceso de JARVIS» | Abierto sin el token | Abrir el enlace con `?token=` del instalador |
| Los avisos no llegan | Pushcut sin conectar o notificaciones desactivadas | Conexiones → Avisos → *Probar*; revisar los ajustes del iPhone |
| Los datos del coche no salen | Nombres de campos de Mercedes distintos | `./jarvis.sh logs` muestra el JSON de Mercedes; ajustar `car.py` (CONFIGURAR §4) |
