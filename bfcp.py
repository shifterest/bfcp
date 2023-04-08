import json
import logging
import sys

import aiosqlite
import discord
from environs import Env
from loguru import logger


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


async def initialize_db():
    async with aiosqlite.connect("database.db") as db:
        await db.execute(
            """
                CREATE TABLE IF NOT EXISTS spaces (
                    space_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    owner_id INTEGER,
                    bump_on_message INTEGER,
                    bump_on_thread_message INTEGER
                );
            """
        )
        await db.execute(
            """
                CREATE TABLE IF NOT EXISTS guilds (
                    guild_id INTEGER PRIMARY KEY,
                    greet_channel_id INTEGER,
                    greet_attachments TEXT,
                    space_category_id INTEGER,
                    max_spaces_per_owner INTEGER,
                    pinned_channel_ids TEXT,
                    whitelisted_role_ids TEXT,
                    bump_on_message INTEGER,
                    bump_on_thread_message INTEGER
                );
            """
        )


# Add guild to database
async def initialize_guild(guild):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT * FROM guilds WHERE guild_id = ?", (guild.id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                await db.execute(
                    "INSERT INTO guilds VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        guild.id,
                        None,
                        json.dumps([]),
                        None,
                        1,
                        json.dumps([]),
                        json.dumps([]),
                        True,
                        True,
                    ),
                )
                await db.commit()
                logger.info(f"Added {guild.name} (ID {guild.id}) to database.")


# Logging
discord_logger = logging.getLogger("discord")
discord_logger.setLevel(logging.INFO)
discord_logger.addHandler(InterceptHandler())
logger.add(
    "logs/discord-{time}.log",
    format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}",
)

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

    await initialize_db()

    for guild in bot.guilds:
        await initialize_guild(guild)


# Add new guilds
@bot.event
async def on_guild_join(guild):
    await initialize_guild(guild)


# Log in
bot.run(env.str("TOKEN"))
