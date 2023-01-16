import logging

import discord
from environs import Env

# logging stuff
logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)

# environmental variables
env = Env()
env.read_env()

activity = discord.Activity(name="with the cockpit", type=discord.ActivityType.playing)
intents = discord.Intents.default()
bot = discord.Bot(activity=activity, intents=intents)


@bot.event
async def on_ready():
    print(f"logged in as {bot.user}")


cogs = ["space"]

for cog in cogs:
    bot.load_extension(f"cogs.{cog}")


@bot.slash_command(
    name="reload",
    description="Reloads the bot",
    guild_ids=env.list("GUILD_ID"),
)
async def reload(ctx):
    for cog in cogs:
        bot.reload_extension(f"cogs.{cog}")
        print(f"reloaded {cog} cog")
    await ctx.respond("👍")


bot.run(env.str("TOKEN"))
