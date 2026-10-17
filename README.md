# JARVIS

Asistente personal por voz para Nacho. El cerebro vive en su Mac; el iPhone
y el coche (CarPlay) le hablan a través de Siri, y una tablet hace de panel.

Lee y responde su correo, lleva su agenda, crea documentos, envía WhatsApp,
vigila el Mercedes (gasolina, ruedas, cierre), le cuenta cómo ha dormido y
cómo está según su pulsera WHOOP, sigue las ventas de su tienda online,
llama a negocios en su nombre, busca en internet y le avisa por su cuenta cuando toca salir, llega
algo importante o se acaba el stock.

## Instalar (en el Mac de Nacho)

1. Copiar esta carpeta a su carpeta personal, por ejemplo `~/JARVIS`
   (no en Documentos, Escritorio ni Descargas: macOS no deja arrancar desde ahí).
2. Instalar [Tailscale](https://tailscale.com/download/mac) e iniciar sesión.
3. En Terminal:

   ```
   cd ~/JARVIS
   bash instalar.command
   ```

El instalador prepara Python, genera la llave de acceso, deja JARVIS
arrancando solo al encender el Mac, abre el acceso seguro para el iPhone y
la tablet, y termina con una comprobación que dice qué falta configurar.

Después, Nacho abre el panel y pulsa **CONEXIONES**: ahí conecta Gmail,
Mercedes, WHOOP y la tienda con su propia cuenta, y pega sus claves, sin
pasárselas a nadie. El resto está en **[CONFIGURAR_JARVIS.md](CONFIGURAR_JARVIS.md)**
(preparación de Google, Mercedes y WHOOP, avisos y Atajos del iPhone).

## Uso diario

```
./jarvis.sh estado        # ¿está en marcha?
./jarvis.sh reiniciar     # tras cambiar el .env
./jarvis.sh logs          # registro en directo
./jarvis.sh diagnostico   # revisa cada pieza
./jarvis.sh actualizar    # baja la última versión e instala
```

## Para desarrollar

- Backend: `siri_2.0_backend.py` (FastAPI) y los módulos `car.py`,
  `google_services.py`, `store.py`, `maps.py`, `notifier.py`, `weather.py`.
- Panel: React en `src/`. Tras cambiarlo, `npm install && npm run build`
  regenera `panel/`, que es lo que sirve el backend.
