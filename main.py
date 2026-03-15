import os
import time
from datetime import timedelta
import discord
from discord import app_commands
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
AUTOROLE_ID = os.getenv("AUTOROLE_ID")
WELCOME_CHANNEL_ID = os.getenv("WELCOME_CHANNEL_ID")

if not TOKEN:
    raise ValueError("Falta DISCORD_TOKEN en el archivo .env")

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
_synced = False
recent_join_events: dict[tuple[int, int], float] = {}
recent_command_sends: dict[tuple[int, int, int, str], float] = {}
JOIN_DEDUP_SECONDS = 30
COMMAND_DEDUP_SECONDS = 8


def prune_old_entries(cache: dict, ttl_seconds: int) -> None:
    now = time.monotonic()
    stale_keys = [key for key, ts in cache.items() if now - ts > ttl_seconds]
    for key in stale_keys:
        cache.pop(key, None)


def should_send_join_welcome(member: discord.Member) -> bool:
    prune_old_entries(recent_join_events, JOIN_DEDUP_SECONDS)
    key = (member.guild.id, member.id)
    now = time.monotonic()
    last_seen = recent_join_events.get(key)
    if last_seen is not None and now - last_seen < JOIN_DEDUP_SECONDS:
        return False

    recent_join_events[key] = now
    return True


def should_send_command_message(interaction: discord.Interaction, canal: discord.TextChannel, mensaje: str) -> bool:
    prune_old_entries(recent_command_sends, COMMAND_DEDUP_SECONDS)
    author_id = interaction.user.id
    guild_id = interaction.guild_id or 0
    key = (guild_id, author_id, canal.id, mensaje.strip())
    now = time.monotonic()
    last_seen = recent_command_sends.get(key)
    if last_seen is not None and now - last_seen < COMMAND_DEDUP_SECONDS:
        return False

    recent_command_sends[key] = now
    return True


async def was_recent_welcome_sent(channel: discord.abc.Messageable, member: discord.Member) -> bool:
    if not isinstance(channel, discord.TextChannel):
        return False

    now = discord.utils.utcnow()
    async for msg in channel.history(limit=25):
        if msg.author.id != client.user.id:
            continue
        if now - msg.created_at > timedelta(seconds=90):
            break

        if msg.embeds:
            first_embed = msg.embeds[0]
            same_title = first_embed.title == "🌟 ¡Bienvenido a Impact! 🌟"
            mentions_user = member.mention in (first_embed.description or "")
            if same_title and mentions_user:
                return True

    return False


async def was_recent_command_message_sent(channel: discord.TextChannel, mensaje: str) -> bool:
    now = discord.utils.utcnow()
    async for msg in channel.history(limit=15):
        if msg.author.id != client.user.id:
            continue
        if now - msg.created_at > timedelta(seconds=20):
            break
        if (msg.content or "").strip() == mensaje.strip():
            return True

    return False


def get_welcome_channel(guild: discord.Guild) -> discord.abc.Messageable | None:
    me = guild.me
    if me is None:
        return None

    if WELCOME_CHANNEL_ID and WELCOME_CHANNEL_ID.isdigit():
        configured_channel = guild.get_channel(int(WELCOME_CHANNEL_ID))
        if isinstance(configured_channel, discord.TextChannel):
            if configured_channel.permissions_for(me).send_messages:
                return configured_channel
            print(f"⚠️ No tengo permiso para enviar en el canal configurado ({WELCOME_CHANNEL_ID})")

    if guild.system_channel and guild.system_channel.permissions_for(me).send_messages:
        return guild.system_channel

    for channel in guild.text_channels:
        if channel.permissions_for(me).send_messages:
            return channel

    return None


async def send_welcome(member: discord.Member) -> bool:
    channel = get_welcome_channel(member.guild)
    if not channel:
        print(f"⚠️ No encontré canal para bienvenida en {member.guild.name}")
        return False

    if await was_recent_welcome_sent(channel, member):
        print(f"ℹ️ Bienvenida ya enviada recientemente para {member} en {member.guild.name}")
        return False

    embed = discord.Embed(
        title="🌟 ¡Bienvenido a Impact! 🌟",
        description=(
            f"👋 {member.mention}, nos alegra que hayas decidido unirte a nuestra comunidad.\n\n"
            "Aquí en Impact no solo encontrarás un servidor de Discord, sino un verdadero punto de encuentro "
            "para aventureros, estrategas y soñadores que comparten la pasión por World of Warcraft y los "
            "mundos fantásticos.\n\n"
            "🔹 ¿Qué puedes esperar?\n"
            "- Un espacio donde siempre habrá alguien dispuesto a ayudarte o a compartir una buena charla.\n"
            "- Eventos, raids y actividades que te pondrán a prueba y te harán crecer como jugador.\n"
            "- Canales dedicados para guías, builds, noticias y curiosidades del universo WoW.\n"
            "- Una comunidad que valora el respeto, la amistad y la diversión por encima de todo.\n\n"
            "⚔️ Tu viaje comienza aquí: explora los canales, preséntate en la sala de bienvenida y no dudes en "
            "preguntar cualquier cosa. Cada nuevo miembro aporta su propia chispa y hace que nuestro servidor "
            "sea más fuerte.\n\n"
            "✨ Recuerda: Impact no es solo un nombre, es lo que juntos dejamos en cada batalla, en cada "
            "conversación y en cada momento compartido.\n\n"
            "¡Prepárate para vivir aventuras épicas y crear recuerdos inolvidables!"
        ),
        color=discord.Color.gold(),
    )
    embed.set_image(url="https://i.imgur.com/z9PiKMr.jpeg")

    await channel.send(embed=embed)
    return True


def is_guild_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    return interaction.user.guild_permissions.manage_guild


async def assign_autorole(member: discord.Member) -> bool:
    if not AUTOROLE_ID or not AUTOROLE_ID.isdigit():
        return False

    role = member.guild.get_role(int(AUTOROLE_ID))
    me = member.guild.me
    if role is None or me is None:
        return False

    if not me.guild_permissions.manage_roles:
        print(f"⚠️ El bot no tiene permiso de administrar roles en {member.guild.name}")
        return False

    if me.top_role <= role:
        print(f"⚠️ El rol del bot debe estar por encima de {role.name} en {member.guild.name}")
        return False

    try:
        await member.add_roles(role, reason="Autorrol al entrar")
        return True
    except discord.Forbidden:
        print(f"⚠️ No se pudo asignar autorrol a {member} por permisos")
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
    if not should_send_join_welcome(member):
        print(f"ℹ️ Bienvenida duplicada evitada para {member} en {member.guild.name}")
        return

    await assign_autorole(member)
    await send_welcome(member)


@tree.command(name="mandar", description="Manda un mensaje por el bot en un canal")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def mandar(interaction: discord.Interaction, canal: discord.TextChannel, mensaje: str):
    if not is_guild_admin(interaction):
        await interaction.response.send_message("⛔ Solo administradores pueden usar este comando.", ephemeral=True)
        return

    if not canal.permissions_for(interaction.guild.me).send_messages:
        await interaction.response.send_message(
            "⚠️ No tengo permiso para enviar mensajes en ese canal.", ephemeral=True
        )
        return

    if not should_send_command_message(interaction, canal, mensaje):
        await interaction.response.send_message(
            "⚠️ Detecté un envío duplicado y lo bloqueé.", ephemeral=True
        )
        return

    if await was_recent_command_message_sent(canal, mensaje):
        await interaction.response.send_message(
            "⚠️ Ese mensaje ya fue enviado hace unos segundos y lo bloqueé.", ephemeral=True
        )
        return

    await canal.send(mensaje)
    await interaction.response.send_message("✅ Mensaje enviado.", ephemeral=True)


@tree.command(name="simular_bienvenida", description="Simula el embed de bienvenida")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def simular_bienvenida(interaction: discord.Interaction, miembro: discord.Member | None = None):
    if not is_guild_admin(interaction):
        await interaction.response.send_message("⛔ Solo administradores pueden usar este comando.", ephemeral=True)
        return

    target = miembro or interaction.user
    if not isinstance(target, discord.Member):
        await interaction.response.send_message("⚠️ No pude identificar el miembro.", ephemeral=True)
        return

    sent = await send_welcome(target)
    if sent:
        await interaction.response.send_message("✅ Bienvenida simulada enviada.", ephemeral=True)
        return

    await interaction.response.send_message(
        "⚠️ No encontré un canal válido para enviar la bienvenida.", ephemeral=True
    )


if os.getenv("REPL_ID"):
    from keep_alive import keep_alive

    keep_alive()

client.run(TOKEN)
