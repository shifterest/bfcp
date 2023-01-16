import asyncio

import discord
from discord.ext import commands
from environs import Env

# environmental variables
env = Env()
env.read_env()


class Space(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    space = discord.SlashCommandGroup("space", "Space-related commands")

    # auto-move spaces
    @commands.Cog.listener()
    async def on_message(self, message):
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
                channel = message.guild.get_channel(id)
                if channel.category_id == message.channel.category_id:
                    position = max(position, channel.position)

            await message.channel.edit(position=position + 1)

    @space.command(
        name="create",
        description="Creates a space given an owner",
        guild_ids=env.list("GUILD_ID"),
    )
    async def create(
        self,
        ctx,
        owner: discord.Option(
            discord.SlashCommandOptionType.user, "The owner of the space"
        ),
        emoji: discord.Option(
            str, "An emoji prepending the channel's name", required=False
        ),
        name: discord.Option(
            str, "The name of the channel", required=False, min_length=1
        ),
    ):
        await ctx.defer()
        space_category = ctx.guild.get_channel(env.int("CATEGORY_ID"))
        space_emoji = emoji or "✨"
        space_name = name or f"{owner.display_name}-space"
        space_full_name = space_emoji + env.str("DELIMITER") + space_name
        overwrites = {
            owner: discord.PermissionOverwrite(
                view_channel=True,
                manage_channels=True,
                manage_permissions=True,
                manage_webhooks=True,
                read_messages=True,
                send_messages=True,
            ),
            ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False),
        }

        space = await space_category.create_text_channel(
            space_full_name, overwrites=overwrites
        )

        await ctx.send_followup(f"**👍 · {space.mention} created**")

    @space.command(
        name="sort",
        description="Sorts spaces by last usage in descending order",
        guild_ids=env.list("GUILD_ID"),
    )
    async def sort(self, ctx):
        # this'll take a while
        await ctx.defer()

        channels = ctx.guild.get_channel(env.int("CATEGORY_ID")).text_channels
        first_pos = channels[0].position
        pinned_channels = []
        channels_dates = {}
        empty_channels_dates = {}

        # fetch relevant info, separate empty channels
        for channel in channels:
            try:
                message = await channel.fetch_message(channel.last_message_id)
                channels_dates[channel.id] = message.created_at
            except (discord.NotFound, discord.HTTPException) as e:
                if e.code in [10008, 50013]:
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
            await ctx.guild.get_channel(id).edit(position=first_pos + i)
            await asyncio.sleep(0.5)

        await ctx.send_followup("👍")


def setup(bot):
    bot.add_cog(Space(bot))
