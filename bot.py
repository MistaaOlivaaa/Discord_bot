import discord
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands
import yt_dlp
import asyncio
from typing import Optional, Dict
import os
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()
# Read bot token from environment variable DISCORD_TOKEN
TOKEN = os.getenv("DISCORD_TOKEN")

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'ytsearch',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

intents = discord.Intents.default()
# Slash commands don't need the Message Content intent; leave it disabled to avoid privileged intent requirement.
intents.message_content = False
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)
music_queues: Dict[int, dict] = {}


def get_queue(guild_id: int) -> dict:
    if guild_id not in music_queues:
        music_queues[guild_id] = {'queue': [], 'now_playing': None, 'is_playing': False}
    return music_queues[guild_id]


async def search_youtube(query: str) -> Optional[dict]:
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'default_search': 'ytsearch',
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'source_address': '0.0.0.0',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
            if info:
                if 'entries' in info:
                    info = info['entries'][0]
                return {
                    'title': info.get('title', 'Unknown'),
                    'webpage_url': info.get('webpage_url', ''),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                }
    except Exception as e:
        print(f"Error searching YouTube: {e}")
        import traceback
        traceback.print_exc()
    return None


async def get_audio_url(webpage_url: str) -> Optional[str]:
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'source_address': '0.0.0.0',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(webpage_url, download=False))
            if info:
                return info.get('url', '')
    except Exception as e:
        print(f"Error extracting audio URL: {e}")
        import traceback
        traceback.print_exc()
    return None


def create_now_playing_embed(song_info: dict, requested_by: discord.Member) -> discord.Embed:
    embed = discord.Embed(title="🎵 Now Playing", description=song_info['title'], color=discord.Color.blurple())
    duration = song_info['duration']
    minutes, seconds = divmod(duration, 60)
    duration_str = f"{int(minutes)}:{int(seconds):02d}"
    embed.add_field(name="Duration", value=duration_str, inline=True)
    embed.add_field(name="Requested by", value=requested_by.mention, inline=True)
    if song_info.get('thumbnail'):
        embed.set_thumbnail(url=song_info['thumbnail'])
    embed.set_footer(text=f"Requested by {requested_by.name}")
    return embed


def create_queue_embed(guild_id: int) -> discord.Embed:
    queue_data = get_queue(guild_id)
    queue = queue_data['queue']
    embed = discord.Embed(title="🎶 Music Queue", color=discord.Color.blurple())
    if not queue:
        embed.description = "Queue is empty"
        return embed
    queue_text = ""
    for i, song in enumerate(queue[:10], 1):
        queue_text += f"{i}. {song['title']}\n"
    if len(queue) > 10:
        queue_text += f"\n... and {len(queue) - 10} more songs"
    embed.description = queue_text
    embed.set_footer(text=f"Total songs in queue: {len(queue)}")
    return embed


class MusicControls(View):
    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="⏸ Pause", style=discord.ButtonStyle.primary)
    async def pause_button(self, interaction: discord.Interaction, button: Button):
        guild = self.bot.get_guild(self.guild_id)
        if guild and guild.voice_client:
            if guild.voice_client.is_playing():
                guild.voice_client.pause()
                await interaction.response.send_message("⏸ Music paused", ephemeral=True)
            else:
                await interaction.response.send_message("Nothing is playing", ephemeral=True)
        else:
            await interaction.response.send_message("Bot is not in a voice channel", ephemeral=True)

    @discord.ui.button(label="⏭ Skip", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button: Button):
        guild = self.bot.get_guild(self.guild_id)
        if guild and guild.voice_client:
            if guild.voice_client.is_playing():
                guild.voice_client.stop()
                await interaction.response.send_message("⏭ Skipped to next song", ephemeral=True)
            else:
                await interaction.response.send_message("Nothing is playing", ephemeral=True)
        else:
            await interaction.response.send_message("Bot is not in a voice channel", ephemeral=True)

    @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: Button):
        guild = self.bot.get_guild(self.guild_id)
        if guild and guild.voice_client:
            queue_data = get_queue(self.guild_id)
            queue_data['queue'].clear()
            queue_data['is_playing'] = False
            guild.voice_client.stop()
            await interaction.response.send_message("⏹ Music stopped and queue cleared", ephemeral=True)
        else:
            await interaction.response.send_message("Bot is not in a voice channel", ephemeral=True)


async def play_next(guild_id: int):
    queue_data = get_queue(guild_id)
    guild = bot.get_guild(guild_id)
    if not guild or not guild.voice_client:
        return
    if not queue_data['queue']:
        queue_data['is_playing'] = False
        await guild.voice_client.disconnect()
        return
    song_info = queue_data['queue'].pop(0)
    queue_data['now_playing'] = song_info
    try:
        audio_url = await get_audio_url(song_info['webpage_url'])
        if not audio_url:
            await play_next(guild_id)
            return
        audio_source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)
        guild.voice_client.play(audio_source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), bot.loop))
        requested_by = song_info.get('requested_by', 'Unknown')
        embed = create_now_playing_embed(song_info, requested_by)
        view = MusicControls(bot, guild_id)
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                await channel.send(embed=embed, view=view)
                break
    except Exception as e:
        print(f"Error playing song: {e}")
        import traceback
        traceback.print_exc()
        await play_next(guild_id)


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.tree.command(name="play", description="Play a song from YouTube")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ You must be in a voice channel to use this command!", ephemeral=True)
        return
    await interaction.response.defer()
    song_info = await search_youtube(query)
    if not song_info:
        await interaction.followup.send("❌ Could not find that song on YouTube")
        return
    song_info['requested_by'] = interaction.user
    guild_id = interaction.guild.id
    queue_data = get_queue(guild_id)
    voice_client = interaction.guild.voice_client
    if not voice_client:
        try:
            voice_client = await asyncio.wait_for(interaction.user.voice.channel.connect(), timeout=10.0)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Connection to voice channel timed out. Please try again.")
            return
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Could not connect to voice channel: {e}")
            return
    queue_data['queue'].append(song_info)
    if not queue_data['is_playing']:
        queue_data['is_playing'] = True
        await play_next(guild_id)
        await interaction.followup.send(f"▶️ Now playing: **{song_info['title']}**")
    else:
        embed = discord.Embed(title="✅ Added to Queue", description=song_info['title'], color=discord.Color.green())
        embed.add_field(name="Position", value=f"#{len(queue_data['queue'])}", inline=True)
        await interaction.followup.send(embed=embed)


@bot.tree.command(name="pause", description="Pause the current song")
async def pause(interaction: discord.Interaction):
    if not interaction.guild.voice_client:
        await interaction.response.send_message("❌ Bot is not in a voice channel", ephemeral=True)
        return
    if interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.pause()
        await interaction.response.send_message("⏸ Music paused")
    else:
        await interaction.response.send_message("❌ Nothing is currently playing", ephemeral=True)


@bot.tree.command(name="resume", description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    if not interaction.guild.voice_client:
        await interaction.response.send_message("❌ Bot is not in a voice channel", ephemeral=True)
        return
    if interaction.guild.voice_client.is_paused():
        interaction.guild.voice_client.resume()
        await interaction.response.send_message("▶ Music resumed")
    else:
        await interaction.response.send_message("❌ Music is not paused", ephemeral=True)


@bot.tree.command(name="skip", description="Skip to the next song")
async def skip(interaction: discord.Interaction):
    if not interaction.guild.voice_client:
        await interaction.response.send_message("❌ Bot is not in a voice channel", ephemeral=True)
        return
    if interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭ Skipped to next song")
    else:
        await interaction.response.send_message("❌ Nothing is currently playing", ephemeral=True)


@bot.tree.command(name="queue", description="Show the current music queue")
async def queue(interaction: discord.Interaction):
    embed = create_queue_embed(interaction.guild.id)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="stop", description="Stop music and clear the queue")
async def stop(interaction: discord.Interaction):
    if not interaction.guild.voice_client:
        await interaction.response.send_message("❌ Bot is not in a voice channel", ephemeral=True)
        return
    queue_data = get_queue(interaction.guild.id)
    queue_data['queue'].clear()
    queue_data['is_playing'] = False
    interaction.guild.voice_client.stop()
    await interaction.response.send_message("⏹ Music stopped and queue cleared")


# =============================
# Moderation: Kick and Ban
# =============================

def _role_higher(a: discord.Member, b: discord.Member) -> bool:
    """Return True if member a's top role is strictly higher than b's top role.
    Guild owners are treated as highest. Equal positions are not higher.
    """
    if a.guild.owner_id == a.id:
        return True
    if a.guild.owner_id == b.id:
        return False
    return a.top_role > b.top_role


@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.default_permissions(kick_members=True)
@app_commands.checks.has_permissions(kick_members=True)
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str | None = None,
):
    # Quick sanity checks
    if member.id == interaction.user.id:
        await interaction.response.send_message("❌ You can't kick yourself.", ephemeral=True)
        return
    # Prevent targeting the bot itself
    if member.id == interaction.client.user.id:
        await interaction.response.send_message("❌ I won't kick myself.", ephemeral=True)
        return
    if member.id == interaction.guild.owner_id:
        await interaction.response.send_message("❌ You can't kick the server owner.", ephemeral=True)
        return
    # Check bot permissions
    if not interaction.guild.me.guild_permissions.kick_members:
        await interaction.response.send_message("❌ I don't have permission to kick members.", ephemeral=True)
        return
    # Role hierarchy checks (user and bot)
    if not _role_higher(interaction.user, member) and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ You can't kick someone with an equal or higher role.", ephemeral=True)
        return
    if not _role_higher(interaction.guild.me, member):
        await interaction.response.send_message("❌ I can't kick that member due to role hierarchy.", ephemeral=True)
        return
    try:
        await member.kick(reason=reason or f"Kicked by {interaction.user}:")
        embed = discord.Embed(
            title="👢 Member Kicked",
            description=f"{member.mention} was kicked.",
            color=discord.Color.orange(),
        )
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Moderator: {interaction.user}")
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I was forbidden from kicking that member.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(f"❌ Failed to kick: {e}", ephemeral=True)


@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.default_permissions(ban_members=True)
@app_commands.checks.has_permissions(ban_members=True)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str | None = None,
):
    if member.id == interaction.user.id:
        await interaction.response.send_message("❌ You can't ban yourself.", ephemeral=True)
        return
    # Prevent targeting the bot itself
    if member.id == interaction.client.user.id:
        await interaction.response.send_message("❌ I won't ban myself.", ephemeral=True)
        return
    if member.id == interaction.guild.owner_id:
        await interaction.response.send_message("❌ You can't ban the server owner.", ephemeral=True)
        return
    if not interaction.guild.me.guild_permissions.ban_members:
        await interaction.response.send_message("❌ I don't have permission to ban members.", ephemeral=True)
        return
    if not _role_higher(interaction.user, member) and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ You can't ban someone with an equal or higher role.", ephemeral=True)
        return
    if not _role_higher(interaction.guild.me, member):
        await interaction.response.send_message("❌ I can't ban that member due to role hierarchy.", ephemeral=True)
        return
    try:
        await member.ban(reason=reason or f"Banned by {interaction.user}")
        embed = discord.Embed(
            title="🔨 Member Banned",
            description=f"{member.mention} was banned.",
            color=discord.Color.red(),
        )
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Moderator: {interaction.user}")
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I was forbidden from banning that member.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(f"❌ Failed to ban: {e}", ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # Handle common permission errors more gracefully
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You don't have the required permissions to use this command.", ephemeral=True
        )
    elif isinstance(error, app_commands.BotMissingPermissions):
        await interaction.response.send_message(
            "❌ I don't have the required permissions to perform this action.", ephemeral=True
        )
    elif isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "❌ You cannot use this command here or right now.", ephemeral=True
        )
    else:
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An unexpected error occurred.", ephemeral=True)
        except Exception:
            pass


if __name__ == "__main__":
    # Sanitize and validate token
    if TOKEN:
        TOKEN = TOKEN.strip().strip('"').strip("'")
        if TOKEN.lower().startswith("bot "):
            TOKEN = TOKEN[4:].strip()
    if not TOKEN or TOKEN.strip() == "" or TOKEN == "your_discord_bot_token_here":
        print("ERROR: DISCORD_TOKEN is not set or is still the placeholder. Edit .env and set DISCORD_TOKEN to your actual Bot token from the Discord Developer Portal (Bot tab). Do not include quotes or the 'Bot ' prefix.")
        raise SystemExit(1)
    bot.run(TOKEN)
