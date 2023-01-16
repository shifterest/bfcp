import asyncio
import discord
import logging
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


# auto-move spaces
@bot.event
async def on_message(message):
    # ignore threads, etc.
    if message.channel.type != discord.ChannelType.text:
        return
    # ignore pinned channels
    if message.channel.id in env.list("PINNED_CHANNEL_IDS", subcast=int):
        return
    if message.channel.category_id == env.int("CATEGORY_ID"):
        position = 0

        # determine position of last pinned channel in the same category
        for id in env.list("PINNED_CHANNEL_IDS", subcast=int):
            channel = bot.get_channel(id)
            if channel.category_id == message.channel.category_id:
                position = max(position, channel.position)

        await message.channel.edit(position=position + 1)
        print(f"moved {message.channel.name} to position {position + 1}")


@bot.slash_command(
    name="sort",
    description="Sorts spaces by last usage in descending order",
    guild_ids=env.list("GUILD_ID"),
)
async def sort(ctx):
    # this'll take a while
    await ctx.defer()

    # get all channels under category
    categories = ctx.guild.categories
    channels = next(
        (
            category.channels
            for category in categories
            if category.id == env.int("CATEGORY_ID")
        ),
        [],
    )

    first_pos = channels[0].position
    pinned_channels = []
    channels_dates = {}
    empty_channels_dates = {}

    # fetch relevant info, separate empty channels
    for channel in channels:
        try:
            message = await channel.fetch_message(channel.last_message_id)
            channels_dates[channel.id] = message.created_at
        except (discord.NotFound, discord.HTTPException):
            empty_channels_dates[channel.id] = channel.created_at

    # separate pinned channels
    for id in env.list("PINNED_CHANNEL_IDS", subcast=int):
        for channel in channels:
            if id == channel.id:
                pinned_channels.append(id)
                if id in channels_dates:
                    channels_dates.pop(id)
                else:
                    empty_channels_dates.pop(id)

    # sort channels
    ordered_channels = (
        pinned_channels
        + sorted(channels_dates, reverse=True, key=channels_dates.get)
        + sorted(empty_channels_dates, reverse=True, key=empty_channels_dates.get)
    )

    for i, id in enumerate(ordered_channels):
        await bot.get_channel(id).edit(position=first_pos + i)
        await asyncio.sleep(0.5)

    await ctx.send_followup("👍")


# Work in progress!
# @bot.slash_command(
#     name="metube",
#     description="Sends an URL to a MeTube instance",
#     guild_ids=env.list("GUILD_ID"),
#     options=discord.Option(
#         name="url",
#         input_type=discord.SlashCommandOptionType.string,
#         required=True,
#         description="The URL to send to a MeTube instance",
#     ),
# )
# async def metube(ctx):
#     await ctx.send_followup("👍")


bot.run(env.str("TOKEN"))
