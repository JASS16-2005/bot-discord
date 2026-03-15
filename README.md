# Bot de bienvenida para Discord (Python)

## 1) Crear aplicación y bot en Discord Developer Portal
1. Ve a https://discord.com/developers/applications
2. Crea una app nueva.
3. En **Bot**, crea el bot y copia el token.
4. Activa en **Privileged Gateway Intents** la opción **Server Members Intent**.

## 2) Configurar el proyecto
En PowerShell, dentro de esta carpeta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3) Variables de entorno
1. Copia `.env.example` como `.env`.
2. Reemplaza:
   - `DISCORD_TOKEN` por tu token.

## 4) Invitar el bot al servidor
En Developer Portal > OAuth2 > URL Generator:
- Scopes: `bot`, `applications.commands`
- Bot Permissions: `Send Messages`, `View Channels`, `Manage Server` (solo si quieres restringir el comando a staff)

Abre la URL generada e invita el bot a tu servidor.

## 5) Ejecutar
```powershell
python main.py
```

Si todo va bien, verás: `✅ Bot conectado como ...`

## 6) Probar simulación de bienvenida
Usa el comando slash:
- `/simular_bienvenida` (usa tu propio usuario)
- `/simular_bienvenida miembro:@usuario` (simula para otro miembro)

El comando responde en privado y envía la bienvenida al canal configurado.

## 7) Configurar embed de bienvenida (solo administradores)
Comando principal:

- `/configurar_bienvenida_embed canal:#canal titulo:"..." descripcion:"..." imagen_url:"https://..." color_hex:#5865F2`
- Alternativa recomendada para multilínea: `/configurar_bienvenida_modal canal:#canal imagen_url:"https://..." color_hex:#5865F2`

Parámetros:
- `canal`: canal donde se enviará la bienvenida.
- `titulo`: título del embed.
- `descripcion`: texto del embed.
- `imagen_url` (opcional): URL de imagen para mostrar en el mensaje.
- `color_hex` (opcional): color HEX del embed (ejemplo `#5865F2`).

En `descripcion` puedes usar:
- `{user}` o `@user` para mencionar al miembro que entra.
- Shift+Enter para separar el texto en varias líneas.

Nota: si Discord no te deja hacer saltos de línea cómodamente en el comando normal, usa `configurar_bienvenida_modal`, que abre un cuadro de texto grande para escribir múltiples líneas.

Ejemplo de descripción:
`¡Hola {user}!`
`Lee #reglas y disfruta el servidor 🎉`

El bot guarda esta configuración por servidor y la reutiliza en cada nuevo miembro.
Sin esta configuración, el bot no enviará bienvenida.
Incluye protección anti-duplicados: si Discord dispara el evento más de una vez para el mismo usuario en pocos segundos, solo enviará un mensaje.

## 8) Autorrol al entrar (solo administradores)
- `/configurar_autorrol rol:@MiRol` → asigna automáticamente ese rol a cada miembro que entre.
- `/quitar_autorrol` → desactiva el autorrol.

Importante: el bot necesita permiso **Manage Roles** y su rol debe estar por encima del rol que quieres asignar.

## 9) Comandos de administración del bot
- `/apagar_bot` → apaga el bot.
- `/reiniciar_bot` → reinicia el proceso del bot.

Estos comandos requieren permisos de **Manage Server**.

## 10) Dejarlo online gratis (sin tu PC encendida)
Las opciones gratuitas cambian con el tiempo, pero estas suelen funcionar:

### Opción recomendada (24/7): Oracle Cloud Always Free VM
1. Crea una VM gratuita (Ubuntu) en Oracle Cloud.
2. Sube tu proyecto al servidor (Git o SCP).
3. Instala Python y dependencias.
4. Crea tu `.env` en el servidor.
5. Ejecuta el bot como servicio `systemd` para que reinicie solo.

Ejemplo rápido de servicio:

```ini
[Unit]
Description=Discord Welcome Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/bot-discord
ExecStart=/home/ubuntu/bot-discord/.venv/bin/python main.py
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target
```

Luego:

```bash
sudo systemctl daemon-reload
sudo systemctl enable discord-bot
sudo systemctl start discord-bot
sudo systemctl status discord-bot
```

### Opción fácil pero no siempre 24/7: Render / Koyeb / Railway (free tier)
- Subes el repo y configuras `DISCORD_TOKEN` como variable.
- Comando de arranque: `python main.py`.
- Algunos planes gratis duermen servicios o tienen límites mensuales.
