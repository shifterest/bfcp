from datetime import datetime
import logging
import os

import discord
from environs import Env

# logging
logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)

now = datetime.now()
log_file = f"discord_{now.year}_{now.month}_{now.day}.log"

if not os.path.exists("./logs/"):
    os.makedirs("./logs/")
handler = logging.FileHandler(filename=f"./logs/{log_file}", encoding="utf-8", mode="w")
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)

# activity status
activity = discord.Activity(name="in the cockpit", type=discord.ActivityType.playing)
intents = discord.Intents.all()
bot = discord.Bot(activity=activity, intents=intents)

# log in
@bot.event
async def on_ready():
    print(f"logged in as {bot.user}")


bot.load_extension("cogs")

# environmental variables
env = Env()
env.read_env()

# reload cogs
# @bot.slash_command(
#     name="reload",
#     description="Reloads the bot",
#     guild_ids=env.list("GUILD_ID"),
# )
# async def reload(ctx):
#     bot.reload_extension("cogs")
#     print(f"reloaded cogs")

#     await ctx.respond("👍")


bot.run(env.str("TOKEN"))
