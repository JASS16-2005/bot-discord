import os
import sys
import asyncio
import json
import time
from pathlib import Path
from typing import Any
import discord
from discord import app_commands
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("Falta DISCORD_TOKEN en el archivo .env")

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
_synced = False
CONFIG_FILE = Path(__file__).with_name("welcome_config.json")
welcome_config: dict[str, dict[str, Any]] = {}
recent_welcomes: dict[tuple[int, int], float] = {}
WELCOME_DEDUP_SECONDS = 20


def load_config() -> None:
    global welcome_config
    if not CONFIG_FILE.exists():
        welcome_config = {}
        return

    try:
        welcome_config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        welcome_config = {}


def save_config() -> None:
    CONFIG_FILE.write_text(
        json.dumps(welcome_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_guild_config(guild_id: int) -> dict[str, Any]:
    return welcome_config.setdefault(str(guild_id), {})


def parse_hex_color(color_hex: str | None) -> int:
    if not color_hex:
        return discord.Color.blurple().value

    normalized = color_hex.strip().removeprefix("#")
    if len(normalized) != 6:
        raise ValueError("El color debe tener formato HEX de 6 dígitos, por ejemplo #5865F2")
    return int(normalized, 16)


class WelcomeEmbedModal(discord.ui.Modal, title="Configurar bienvenida embed"):
    def __init__(
        self,
        guild_id: int,
        canal_id: int,
        imagen_url: str,
        color_value: int,
        default_title: str,
        default_description: str,
    ):
        super().__init__()
        self.guild_id = guild_id
        self.canal_id = canal_id
        self.imagen_url = imagen_url
        self.color_value = color_value

        self.titulo = discord.ui.TextInput(
            label="Título",
            default=default_title,
            max_length=256,
            required=True,
        )
        self.descripcion = discord.ui.TextInput(
            label="Descripción (multilínea)",
            style=discord.TextStyle.paragraph,
            default=default_description,
            max_length=2000,
            required=True,
        )
        self.add_item(self.titulo)
        self.add_item(self.descripcion)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild_settings = get_guild_config(self.guild_id)
        guild_settings["welcome_channel_id"] = self.canal_id
        guild_settings["embed_title"] = str(self.titulo.value)
        guild_settings["embed_description"] = str(self.descripcion.value)
        guild_settings["embed_image_url"] = self.imagen_url
        guild_settings["embed_color"] = self.color_value
        save_config()

        await interaction.response.send_message(
            "✅ Embed configurado desde modal. Puedes usar Enter para saltos de línea y `{user}` para mencionar.",
            ephemeral=True,
        )


def get_welcome_channel(guild: discord.Guild) -> discord.abc.Messageable | None:
    me = guild.me
    if me is None:
        return None

    guild_settings = get_guild_config(guild.id)
    config_channel_id = guild_settings.get("welcome_channel_id")
    if isinstance(config_channel_id, int):
        channel = guild.get_channel(config_channel_id)
        if isinstance(channel, discord.TextChannel) and channel.permissions_for(me).send_messages:
            return channel

    return None


async def send_welcome(member: discord.Member) -> bool:
    guild_settings = get_guild_config(member.guild.id)
    embed_title = guild_settings.get("embed_title")
    embed_description = guild_settings.get("embed_description")
    embed_image_url = guild_settings.get("embed_image_url")
    embed_color = guild_settings.get("embed_color", discord.Color.blurple().value)

    if not (embed_title or embed_description or embed_image_url):
        return False

    channel = get_welcome_channel(member.guild)
    if not channel:
        print(f"⚠️ No encontré canal para bienvenida en {member.guild.name}")
        return False
    raw_description = embed_description or "{user} se acaba de unir al servidor."
    processed_description = (
        raw_description
        .replace("{user}", member.mention)
        .replace("@user", member.mention)
    )
    has_user_placeholder = "{user}" in raw_description or "@user" in raw_description

    embed = discord.Embed(
        title=embed_title or "¡Bienvenido/a!",
        description=processed_description,
        color=embed_color,
    )
    if isinstance(embed_image_url, str) and embed_image_url.strip():
        embed.set_image(url=embed_image_url)

    await channel.send(content=None if has_user_placeholder else member.mention, embed=embed)
    return True


def should_send_welcome(member: discord.Member) -> bool:
    key = (member.guild.id, member.id)
    now = time.monotonic()

    stale_keys = [item_key for item_key, ts in recent_welcomes.items() if now - ts > WELCOME_DEDUP_SECONDS]
    for stale_key in stale_keys:
        recent_welcomes.pop(stale_key, None)

    last_sent = recent_welcomes.get(key)
    if last_sent is not None and now - last_sent < WELCOME_DEDUP_SECONDS:
        return False

    recent_welcomes[key] = now
    return True


def is_guild_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    return interaction.user.guild_permissions.manage_guild


async def try_assign_autorole(member: discord.Member) -> bool:
    guild_settings = get_guild_config(member.guild.id)
    role_id = guild_settings.get("autorole_id")
    if not isinstance(role_id, int):
        return False

    role = member.guild.get_role(role_id)
    me = member.guild.me
    if role is None or me is None:
        return False

    if not me.guild_permissions.manage_roles:
        print(f"⚠️ El bot no tiene permiso Manage Roles en {member.guild.name}")
        return False

    if me.top_role <= role:
        print(f"⚠️ El rol del bot está por debajo o igual a {role.name} en {member.guild.name}")
        return False

    try:
        await member.add_roles(role, reason="Autorrol de bienvenida")
        return True
    except discord.Forbidden:
        print(f"⚠️ No se pudo asignar autorrol en {member.guild.name} por permisos")
        return False


@client.event
async def on_ready():
    global _synced
    if not _synced:
        await tree.sync()
        _synced = True
        print("✅ Comandos slash sincronizados")

    print(f"✅ Bot conectado como {client.user}")


@client.event
async def on_member_join(member: discord.Member):
    if not should_send_welcome(member):
        print(f"ℹ️ Bienvenida duplicada bloqueada para {member} en {member.guild.name}")
        return

    await try_assign_autorole(member)
    await send_welcome(member)


@tree.command(name="configurar_bienvenida_embed", description="Configura el embed de bienvenida")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def configurar_bienvenida_embed(
    interaction: discord.Interaction,
    canal: discord.TextChannel,
    titulo: str,
    descripcion: str,
    imagen_url: str | None = None,
    color_hex: str | None = None,
):
    if not is_guild_admin(interaction):
        await interaction.response.send_message("⛔ Solo admins pueden usar este comando.", ephemeral=True)
        return

    try:
        color_value = parse_hex_color(color_hex)
    except ValueError as error:
        await interaction.response.send_message(f"⚠️ {error}", ephemeral=True)
        return

    guild_settings = get_guild_config(interaction.guild_id)
    guild_settings["welcome_channel_id"] = canal.id
    guild_settings["embed_title"] = titulo
    guild_settings["embed_description"] = descripcion
    guild_settings["embed_image_url"] = imagen_url.strip() if imagen_url else ""
    guild_settings["embed_color"] = color_value
    save_config()

    await interaction.response.send_message(
        "✅ Embed configurado. Usa `{user}` o `@user` para mencionar al miembro y escribe saltos de línea con Shift+Enter. Prueba con `/simular_bienvenida`.",
        ephemeral=True,
    )


@tree.command(
    name="configurar_bienvenida_modal",
    description="Configura bienvenida con cuadro de texto multilínea",
)
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def configurar_bienvenida_modal(
    interaction: discord.Interaction,
    canal: discord.TextChannel,
    imagen_url: str | None = None,
    color_hex: str | None = None,
):
    if not is_guild_admin(interaction):
        await interaction.response.send_message("⛔ Solo admins pueden usar este comando.", ephemeral=True)
        return

    guild_settings = get_guild_config(interaction.guild_id)
    current_title = guild_settings.get("embed_title") or "¡Bienvenido/a!"
    current_description = guild_settings.get("embed_description") or "{user} se acaba de unir al servidor."
    current_image = guild_settings.get("embed_image_url") or ""
    current_color = guild_settings.get("embed_color", discord.Color.blurple().value)

    try:
        color_value = parse_hex_color(color_hex) if color_hex else current_color
    except ValueError as error:
        await interaction.response.send_message(f"⚠️ {error}", ephemeral=True)
        return

    modal = WelcomeEmbedModal(
        guild_id=interaction.guild_id,
        canal_id=canal.id,
        imagen_url=imagen_url.strip() if imagen_url is not None else current_image,
        color_value=color_value,
        default_title=current_title,
        default_description=current_description,
    )
    await interaction.response.send_modal(modal)


@tree.command(name="configurar_autorrol", description="Configura el rol automático al entrar")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def configurar_autorrol(interaction: discord.Interaction, rol: discord.Role):
    if not is_guild_admin(interaction):
        await interaction.response.send_message("⛔ Solo admins pueden usar este comando.", ephemeral=True)
        return

    guild_settings = get_guild_config(interaction.guild_id)
    guild_settings["autorole_id"] = rol.id
    save_config()

    await interaction.response.send_message(
        f"✅ Autorrol configurado: {rol.mention}",
        ephemeral=True,
    )


@tree.command(name="quitar_autorrol", description="Desactiva el autorrol")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def quitar_autorrol(interaction: discord.Interaction):
    if not is_guild_admin(interaction):
        await interaction.response.send_message("⛔ Solo admins pueden usar este comando.", ephemeral=True)
        return

    guild_settings = get_guild_config(interaction.guild_id)
    guild_settings.pop("autorole_id", None)
    save_config()

    await interaction.response.send_message("✅ Autorrol desactivado.", ephemeral=True)


@tree.command(name="simular_bienvenida", description="Simula el mensaje de bienvenida")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def simular_bienvenida(interaction: discord.Interaction, miembro: discord.Member | None = None):
    target = miembro or interaction.user
    if not isinstance(target, discord.Member):
        await interaction.response.send_message(
            "No pude identificar al miembro para simular la bienvenida.", ephemeral=True
        )
        return

    sent = await send_welcome(target)
    if sent:
        await interaction.response.send_message("✅ Bienvenida simulada enviada.", ephemeral=True)
        return

    await interaction.response.send_message(
        "⚠️ No hay bienvenida embed configurada. Usa `/configurar_bienvenida_embed`.",
        ephemeral=True,
    )


@tree.command(name="apagar_bot", description="Apaga el bot")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def apagar_bot(interaction: discord.Interaction):
    if not is_guild_admin(interaction):
        await interaction.response.send_message("⛔ Solo admins pueden usar este comando.", ephemeral=True)
        return

    await interaction.response.send_message("🛑 Apagando bot...", ephemeral=True)
    await client.close()


@tree.command(name="reiniciar_bot", description="Reinicia el bot")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def reiniciar_bot(interaction: discord.Interaction):
    if not is_guild_admin(interaction):
        await interaction.response.send_message("⛔ Solo admins pueden usar este comando.", ephemeral=True)
        return

    await interaction.response.send_message("🔄 Reiniciando bot...", ephemeral=True)
    await asyncio.sleep(1)
    os.execv(sys.executable, [sys.executable, *sys.argv])


load_config()

# En Replit, levanta el keep-alive para que UptimeRobot mantenga el bot vivo
if os.getenv("REPL_ID"):
    from keep_alive import keep_alive
    keep_alive()

client.run(TOKEN)
