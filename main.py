import os
import asyncio
from threading import Thread
import discord
from discord.ext import commands
from flask import Flask
# ==================== الإعدادات ====================
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "+"
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing!")
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)
# حفظ الستيج الذي أنشأه البوت لكل سيرفر
podcast_stages = {}
# ==================== سيرفر الويب لـ Render ====================
app = Flask(__name__)
@app.route("/")
def home():
    return "Podcast Bot is Online!"
@app.route("/health")
def health():
    return "OK"
def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )
def start_web():
    thread = Thread(target=run_web, daemon=True)
    thread.start()
# ==================== تشغيل البوت ====================
@bot.event
async def on_ready():
    print(f"Logged in as: {bot.user}")
    print("Podcast Bot is ready!")
# ==================== أمر +تست ====================
@bot.command(name="تست")
@commands.guild_only()
@commands.has_permissions(manage_channels=True)
async def test_podcast(ctx):
    guild = ctx.guild
    # التحقق من وجود ستيج سابق
    existing_stage_id = podcast_stages.get(guild.id)
    existing_stage = (
        guild.get_channel(existing_stage_id)
        if existing_stage_id
        else None
    )
    if existing_stage:
        await ctx.send("البودكاست شغال بالفعل.")
        return
    # البحث عن ستيج باسم بودكاست عند إعادة تشغيل البوت
    if existing_stage is None:
        existing_stage = discord.utils.get(
            guild.stage_channels,
            name="بودكاست"
        )
    if existing_stage:
        podcast_stages[guild.id] = existing_stage.id
        await ctx.send(
            f"الستيج موجود بالفعل: {existing_stage.mention}"
        )
        return
    # إنشاء الستيج
    try:
        stage = await guild.create_stage_channel(
            name="بودكاست",
            reason=f"Podcast started by {ctx.author}"
        )
        podcast_stages[guild.id] = stage.id
    except discord.Forbidden:
        await ctx.send(
            "ما عندي صلاحية إنشاء الستيج. "
            "تأكد من صلاحية Manage Channels."
        )
        return
    except discord.HTTPException as error:
        await ctx.send(f"تعذر إنشاء الستيج: {error}")
        return
    await ctx.send(f"تم إنشاء الستيج: {stage.mention}")
    # إرسال رسالة خاصة لكل عضو غير البوتات
    success = 0
    failed = 0
    for member in guild.members:
        if member.bot:
            continue
        try:
            await member.send(f"تست {member.mention}")
            success += 1
        except (discord.Forbidden, discord.HTTPException):
            failed += 1
        # تخفيف سرعة إرسال الطلبات
        await asyncio.sleep(0.15)
    print(
        f"Podcast test in {guild.name}: "
        f"{success} DMs sent, {failed} failed."
    )
# ==================== أمر +خلصنا ====================
@bot.command(name="خلصنا")
@commands.guild_only()
@commands.has_permissions(manage_channels=True)
async def finish_podcast(ctx):
    guild = ctx.guild
    stage_id = podcast_stages.get(guild.id)
    stage = guild.get_channel(stage_id) if stage_id else None
    # البحث عن الستيج إذا لم يكن محفوظا في الذاكرة
    if stage is None:
        stage = discord.utils.get(
            guild.stage_channels,
            name="بودكاست"
        )
    if stage is None:
        podcast_stages.pop(guild.id, None)
        await ctx.send("ما فيه ستيج بودكاست موجود.")
        return
    try:
        await stage.delete(
            reason=f"Podcast finished by {ctx.author}"
        )
        podcast_stages.pop(guild.id, None)
        # لا يرسل البوت رسائل خاصة عند إنهاء البودكاست
        await ctx.send("تم حذف ستيج البودكاست.")
    except discord.Forbidden:
        await ctx.send("ما عندي صلاحية حذف الستيج.")
    except discord.HTTPException as error:
        await ctx.send(f"تعذر حذف الستيج: {error}")
# ==================== معالجة الأخطاء ====================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "ما عندك صلاحية استخدام الأمر. "
            "تحتاج صلاحية Manage Channels."
        )
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("الأمر هذا يعمل داخل السيرفر فقط.")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        print(f"Command error: {error}")
        try:
            await ctx.send("صار خطأ أثناء تنفيذ الأمر.")
        except discord.HTTPException:
            pass
# ==================== بدء التشغيل ====================
if __name__ == "__main__":
    start_web()
    bot.run(TOKEN)
