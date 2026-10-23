import os
import asyncio
import logging
from threading import Thread
import discord
from discord.ext import commands
from flask import Flask
# ==================================================
# SETTINGS
# ==================================================
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "+"
if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing! Add it in Render Environment."
    )
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("podcast_bot")
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)
# Store the stage ID for each server
podcast_stages = {}
# Prevent two podcast commands running at the same time
podcast_locks = {}
# ==================================================
# RENDER WEB SERVER
# ==================================================
app = Flask(__name__)
@app.route("/")
def home():
    return "Podcast Bot is Online!", 200
@app.route("/health")
def health():
    return "OK", 200
def run_web():
    port = int(os.environ.get("PORT", "10000"))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )
def start_web():
    Thread(
        target=run_web,
        daemon=True,
        name="render-web"
    ).start()
# ==================================================
# BOT READY
# ==================================================
@bot.event
async def on_ready():
    logger.info("Logged in as: %s", bot.user)
    logger.info("Podcast Bot is ready!")
    for guild in bot.guilds:
        for channel in guild.stage_channels:
            if channel.name == "بودكاست":
                podcast_stages[guild.id] = channel.id
                break
# ==================================================
# HELPER: FIND PODCAST STAGE
# ==================================================
def find_podcast_stage(guild):
    stage_id = podcast_stages.get(guild.id)
    if stage_id:
        channel = guild.get_channel(stage_id)
        if isinstance(channel, discord.StageChannel):
            return channel
    for channel in guild.stage_channels:
        if channel.name == "بودكاست":
            podcast_stages[guild.id] = channel.id
            return channel
    return None
# ==================================================
# COMMAND: +تست
# Requires Administrator permission
# ==================================================
@bot.command(name="تست")
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def test_podcast(ctx):
    guild = ctx.guild
    lock = podcast_locks.setdefault(
        guild.id,
        asyncio.Lock()
    )
    async with lock:
        # Check whether a stage already exists
        existing_stage = find_podcast_stage(guild)
        if existing_stage:
            await ctx.send(
                f"البودكاست شغال بالفعل: {existing_stage.mention}"
            )
            return
        # Stage channels require a Community server
        if "COMMUNITY" not in guild.features:
            await ctx.send(
                "ما قدرت أنشئ Stage لأن السيرفر يحتاج تفعيل Community.\n"
                "افتح إعدادات السيرفر في ديسكورد، ثم فعّل Community "
                "وأكمل متطلبات ديسكورد، وبعدها جرّب +تست مرة ثانية."
            )
            logger.warning(
                "Cannot create Stage: server %s is not Community.",
                guild.id
            )
            return
        # Check the bot's own permissions
        me = guild.me
        if me is None:
            try:
                me = await guild.fetch_member(bot.user.id)
            except discord.HTTPException:
                await ctx.send(
                    "تعذر التحقق من صلاحيات البوت. حاول مرة ثانية."
                )
                return
        bot_permissions = me.guild_permissions
        if not (
            bot_permissions.administrator
            or bot_permissions.manage_channels
        ):
            await ctx.send(
                "البوت يحتاج صلاحية Manage Channels "
                "أو Administrator لإنشاء الستيج وحذفه."
            )
            return
        # Create the Stage channel
        # Fixed: removed unsupported topic argument
        try:
            stage = await guild.create_stage_channel(
                name="بودكاست",
                reason=f"Podcast started by {ctx.author}"
            )
            podcast_stages[guild.id] = stage.id
        except discord.Forbidden:
            await ctx.send(
                "ديسكورد رفض إنشاء الستيج بسبب الصلاحيات. "
                "تأكد من صلاحيات البوت وترتيب رتبته."
            )
            logger.exception(
                "Permission error creating Stage in guild %s",
                guild.id
            )
            return
        except discord.HTTPException as error:
            logger.exception(
                "Discord API error creating Stage in guild %s",
                guild.id
            )
            if error.code == 50024:
                message = (
                    "ديسكورد رفض إنشاء Stage بهذا النوع من القنوات. "
                    "تحقق من إعدادات السيرفر ومتطلبات Community."
                )
            elif error.code == 50013:
                message = (
                    "البوت لا يملك الصلاحيات اللازمة لإنشاء الستيج."
                )
            elif error.status == 429:
                message = (
                    "ديسكورد طلب الانتظار بسبب كثرة الطلبات. "
                    "انتظر قليلًا ثم جرّب."
                )
            else:
                message = (
                    f"تعذر إنشاء الستيج. "
                    f"رمز الخطأ: {error.code}"
                )
            await ctx.send(message)
            return
        await ctx.send(
            f"تم إنشاء ستيج البودكاست: {stage.mention}\n"
            "بدأ إرسال رسالة الاختبار للأعضاء بالخاص."
        )
        # Send a DM to each non-bot member
        success = 0
        failed = 0
        try:
            async for member in guild.fetch_members(limit=None):
                if member.bot:
                    continue
                try:
                    await member.send(
                        f"تست {member.mention}",
                        allowed_mentions=discord.AllowedMentions(
                            users=[member],
                            everyone=False,
                            roles=False
                        )
                    )
                    success += 1
                except (discord.Forbidden, discord.HTTPException):
                    failed += 1
                # Reduce request frequency
                await asyncio.sleep(0.5)
        except discord.Forbidden:
            logger.exception(
                "Cannot fetch guild members in guild %s",
                guild.id
            )
            await ctx.send(
                "أنشأت الستيج، لكن البوت لا يستطيع جلب الأعضاء. "
                "تأكد من تفعيل Server Members Intent."
            )
            return
        except discord.HTTPException:
            logger.exception(
                "Failed to fetch members in guild %s",
                guild.id
            )
            await ctx.send(
                "أنشأت الستيج، لكن حصل خطأ أثناء جلب الأعضاء."
            )
            return
        logger.info(
            "Podcast test in %s: %s sent, %s failed.",
            guild.name,
            success,
            failed
        )
        await ctx.send(
            "انتهى إرسال الاختبار.\n"
            f"تم الإرسال: {success}\n"
            f"تعذر الإرسال: {failed}"
        )
# ==================================================
# COMMAND: +خلصنا
# Requires Administrator permission
# ==================================================
@bot.command(name="خلصنا")
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def finish_podcast(ctx):
    guild = ctx.guild
    lock = podcast_locks.setdefault(
        guild.id,
        asyncio.Lock()
    )
    async with lock:
        stage = find_podcast_stage(guild)
        if stage is None:
            podcast_stages.pop(guild.id, None)
            await ctx.send(
                "ما فيه ستيج باسم بودكاست موجود."
            )
            return
        # Check the bot's permissions
        me = guild.me
        if me is None:
            try:
                me = await guild.fetch_member(bot.user.id)
            except discord.HTTPException:
                await ctx.send(
                    "تعذر التحقق من صلاحيات البوت. حاول مرة ثانية."
                )
                return
        permissions = me.guild_permissions
        if not (
            permissions.administrator
            or permissions.manage_channels
        ):
            await ctx.send(
                "البوت يحتاج صلاحية Manage Channels "
                "أو Administrator لحذف الستيج."
            )
            return
        try:
            await stage.delete(
                reason=f"Podcast finished by {ctx.author}"
            )
            podcast_stages.pop(guild.id, None)
            # No private messages are sent by this command
            await ctx.send(
                "تم حذف ستيج البودكاست."
            )
            logger.info(
                "Podcast stage deleted in guild %s",
                guild.id
            )
        except discord.NotFound:
            podcast_stages.pop(guild.id, None)
            await ctx.send(
                "الستيج محذوف بالفعل."
            )
        except discord.Forbidden:
            await ctx.send(
                "ديسكورد رفض حذف الستيج. تحقق من صلاحيات البوت."
            )
            logger.exception(
                "Permission error deleting Stage in guild %s",
                guild.id
            )
        except discord.HTTPException as error:
            logger.exception(
                "Discord API error deleting Stage in guild %s",
                guild.id
            )
            await ctx.send(
                f"تعذر حذف الستيج. رمز الخطأ: {error.code}"
            )
# ==================================================
# COMMAND ERROR HANDLER
# ==================================================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send(
            "الأمر هذا يعمل داخل السيرفر فقط."
        )
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "هذا الأمر خاص بأصحاب صلاحية Administrator."
        )
        return
    if isinstance(error, commands.BotMissingPermissions):
        await ctx.send(
            "البوت ما عنده الصلاحيات المطلوبة لتنفيذ الأمر."
        )
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            "انتظر قليلًا ثم حاول مرة ثانية."
        )
        return
    original = getattr(error, "original", error)
    logger.error(
        "Unhandled command error",
        exc_info=(
            type(original),
            original,
            original.__traceback__
        )
    )
    try:
        await ctx.send(
            "صار خطأ غير متوقع. راجع سجلات Render لمعرفة التفاصيل."
        )
    except discord.HTTPException:
        pass
# ==================================================
# START
# ==================================================
if __name__ == "__main__":
    start_web()
    bot.run(TOKEN)
