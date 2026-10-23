import os
import asyncio
import discord
from discord.ext import commands
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "+"
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing!")
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
# تخزين الستيج الذي أنشأه البوت لكل سيرفر
podcast_stages = {}
@bot.event
async def on_ready():
    print(f"Logged in as: {bot.user}")
    print("Podcast Bot is ready!")
@bot.command(name="تست")
@commands.guild_only()
@commands.has_permissions(manage_channels=True)
async def test_podcast(ctx):
    guild = ctx.guild
    # منع إنشاء أكثر من ستيج بواسطة الأمر نفسه
    existing_stage = podcast_stages.get(guild.id)
    if existing_stage:
        channel = guild.get_channel(existing_stage)
        if channel:
            await ctx.send("البودكاست شغال بالفعل.")
            return
    # إنشاء ستيج باسم بودكاست
    try:
        stage = await guild.create_stage_channel(
            name="بودكاست",
            reason=f"Podcast started by {ctx.author}"
        )
        podcast_stages[guild.id] = stage.id
    except discord.Forbidden:
        await ctx.send("ما عندي صلاحية إنشاء Stage.")
        return
    except discord.HTTPException as error:
        await ctx.send(f"تعذر إنشاء الستيج: {error}")
        return
    # تأكيد بدء العملية في القناة
    await ctx.send(f"تم إنشاء الستيج: {stage.mention}")
    # إرسال رسالة خاصة لكل عضو، باستثناء البوتات
    success = 0
    failed = 0
    for member in guild.members:
        if member.bot:
            continue
        try:
            await member.send(
                f"تست {member.mention}"
            )
            success += 1
        except (discord.Forbidden, discord.HTTPException):
            # العضو مقفل الخاص أو تعذر إرسال الرسالة
            failed += 1
        # تخفيف سرعة الطلبات
        await asyncio.sleep(0.15)
    print(
        f"Podcast test in {guild.name}: "
        f"{success} DMs sent, {failed} failed."
    )
@bot.command(name="خلصنا")
@commands.guild_only()
@commands.has_permissions(manage_channels=True)
async def finish_podcast(ctx):
    guild = ctx.guild
    stage_id = podcast_stages.get(guild.id)
    # لو لم يكن الستيج مسجلا في الذاكرة، ابحث عن Stage باسم بودكاست
    stage = guild.get_channel(stage_id) if stage_id else None
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
        await stage.delete(reason=f"Podcast finished by {ctx.author}")
        podcast_stages.pop(guild.id, None)
        # لا يرسل أي رسالة خاصة عند إنهاء البودكاست
        await ctx.send("تم حذف ستيج البودكاست.")
    except discord.Forbidden:
        await ctx.send("ما عندي صلاحية حذف الستيج.")
    except discord.HTTPException as error:
        await ctx.send(f"تعذر حذف الستيج: {error}")
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("ما عندك صلاحية استخدام الأمر.")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("الأمر هذا يعمل داخل السيرفر فقط.")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        print(f"Command error: {error}")
        await ctx.send("صار خطأ أثناء تنفيذ الأمر.")
bot.run(TOKEN)
