
import os
import logging
import threading
import asyncio
from urllib.parse import urlparse

import discord
import requests
from discord import app_commands
from discord.ext import commands
from flask import Flask, jsonify

# ==================== CONFIG ====================

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
PORT = int(os.getenv("PORT", "10000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("delte-bot")

# ==================== WEB SERVER ====================

app = Flask(__name__)

@app.get("/")
def home():
    return "Delte Bot is Online!", 200

@app.get("/health")
def health():
    return jsonify(
        status="ok",
        bot_ready=bot.is_ready()
    ), 200

def run_web():
    app.run(
        host="0.0.0.0",
        port=PORT,
        use_reloader=False
    )

# ==================== DISCORD BOT ====================

intents = discord.Intents.default()
bot = commands.Bot(
    command_prefix="+",
    intents=intents
)

def validate_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
        return (
            parsed.scheme == "https"
            and parsed.hostname == "links.lootlabs.gg"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )
    except (ValueError, TypeError):
        return False

def get_redirect_url(url: str) -> str:
    with requests.get(
        url,
        allow_redirects=True,
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0"},
        stream=True,
    ) as response:
        return response.url

@bot.event
async def on_ready():
    log.info("Connected as %s", bot.user)

    try:
        if GUILD_ID and GUILD_ID.isdigit():
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            log.info("Synced %s guild commands", len(synced))
        else:
            synced = await bot.tree.sync()
            log.info("Synced %s global commands", len(synced))
    except Exception:
        log.exception("Slash command sync failed")

# ==================== /DELTE ====================

@bot.tree.command(
    name="delte",
    description="استخراج الرابط بعد التحويلات العادية"
)
@app_commands.describe(url="ضع رابط LootLabs هنا")
@app_commands.checks.cooldown(1, 5.0)
async def delte(
    interaction: discord.Interaction,
    url: str
):
    url = url.strip()

    if len(url) > 4000 or not validate_url(url):
        await interaction.response.send_message(
            "❌ الرابط غير صالح. استخدم رابط HTTPS من "
            "links.lootlabs.gg فقط.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    log.info(
        "URL submitted by user_id=%s guild_id=%s",
        interaction.user.id,
        interaction.guild_id,
    )

    try:
        final_url = await asyncio.to_thread(
            get_redirect_url,
            url
        )

        embed = discord.Embed(
            title="تم فحص الرابط",
            description="نتيجة التحويلات العادية للرابط:",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="الرابط الناتج",
            value=f"<{final_url}>",
            inline=False,
        )
        embed.set_footer(text="Delte Bot")

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )

    except requests.RequestException:
        await interaction.followup.send(
            "❌ تعذر الوصول للرابط أو استخراج التحويل.",
            ephemeral=True,
        )
    except Exception:
        log.exception("Failed to process URL")
        await interaction.followup.send(
            "❌ حدث خطأ أثناء فحص الرابط.",
            ephemeral=True,
        )

# ==================== ERROR HANDLER ====================

@delte.error
async def delte_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    if isinstance(error, app_commands.CommandOnCooldown):
        message = (
            f"انتظر {error.retry_after:.1f} ثانية ثم جرّب."
        )
    else:
        log.error(
            "Command failed",
            exc_info=(type(error), error, error.__traceback__),
        )
        message = "حدث خطأ. راجع سجلات Render."

    if interaction.response.is_done():
        await interaction.followup.send(
            message,
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            message,
            ephemeral=True
        )

# ==================== START ====================

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError(
            "أضف DISCORD_TOKEN في Environment Variables"
        )

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    bot.run(TOKEN)
