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
   - `AUTOROLE_ID` por el ID del rol que quieres asignar al entrar (opcional).
   - `WELCOME_CHANNEL_ID` por el ID del canal donde quieres enviar la bienvenida (opcional).

## 4) Invitar el bot al servidor
En Developer Portal > OAuth2 > URL Generator:
- Scopes: `bot`, `applications.commands`
- Bot Permissions: `Send Messages`, `View Channels`, `Manage Roles`, `Manage Server`

Abre la URL generada e invita el bot a tu servidor.

## 5) Ejecutar
```powershell
python main.py
```

Si todo va bien, verás: `✅ Bot conectado como ...`

## 6) Estructura de bienvenida actual
El bot envía automáticamente un embed fijo cuando entra un miembro nuevo:
- Menciona al usuario que entra.
- Usa texto de bienvenida en varias líneas.
- Incluye imagen: `https://i.imgur.com/z9PiKMr.jpeg`.
- Publica en `WELCOME_CHANNEL_ID` si está configurado; si no, usa canal del sistema o el primer canal con permisos.

Además, si configuras `AUTOROLE_ID`, asigna ese rol automáticamente al entrar.

## 7) Comandos disponibles (solo admins)
- `/mandar canal:#canal mensaje:...` → envía un mensaje por el bot en el canal indicado.
- `/simular_bienvenida` → envía una bienvenida de prueba.
- `/simular_bienvenida miembro:@usuario` → simula para otro usuario.

## 8) Dejarlo online gratis (sin tu PC encendida)
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
