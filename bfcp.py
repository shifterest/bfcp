import logging
import os
import sys

import discord
from environs import Env
from loguru import logger

from stuff import db


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# Logging
discord_logger = logging.getLogger("discord")
discord_logger.setLevel(logging.INFO)
discord_logger.addHandler(InterceptHandler())
logger.add(
    "logs/discord-{time}.log",
    format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}",
)

if not os.path.exists("data"):
    os.makedirs("data")

# Activity status
activity = discord.Activity(name="in the cockpit", type=discord.ActivityType.playing)
intents = discord.Intents.all()
bot = discord.Bot(activity=activity, intents=intents)

bot.load_extension("cogs")

# Environmental variables
env = Env()
env.read_env()


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")

    # Initialize database
    await db.initialize_db()
    for guild in bot.guilds:
        await db.initialize_guild(guild)


# Add new guilds
@bot.event
async def on_guild_join(guild):
    await db.initialize_guild(guild)


# Log in
bot.run(env.str("TOKEN"))
