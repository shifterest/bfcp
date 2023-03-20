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
        channel = message.channel

        if channel.type == discord.ChannelType.public_thread:
            channel = channel.parent
        elif channel.type != discord.ChannelType.text:
            return

        if channel.id in env.list("PINNED_CHANNEL_IDS", subcast=int):
            return

        if channel.category_id == env.int("CATEGORY_ID"):
            position = 0

            # determine position of last pinned channel in the same category
            for id in env.list("PINNED_CHANNEL_IDS", subcast=int):
                pinned_channel = message.guild.get_channel(id)
                if pinned_channel and pinned_channel.category_id == channel.category_id:
                    position = max(position, pinned_channel.position)

            await channel.edit(position=position + 1)

    # create space
    @space.command(
        name="create",
        description="Creates a space given an owner",
        guild_ids=env.list("GUILD_ID", subcast=int),
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
        await ctx.defer(ephemeral=True)
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
        for id in env.list("OVERWRITE_ROLE_IDS", subcast=int):
            overwrites[ctx.guild.get_role(id)] = discord.PermissionOverwrite(
                view_channel=True
            )

        space = await space_category.create_text_channel(
            space_full_name, overwrites=overwrites
        )

        await ctx.send_followup("👍", ephemeral=True)

        await ctx.channel.send(
            f"**{owner.mention}, check your space out at {space.mention}!**",
            allowed_mentions=discord.AllowedMentions.all(),
        )

    @space.command(
        name="sort",
        description="Sorts spaces by last usage in descending order",
        guild_ids=env.list("GUILD_ID"),
    )
    async def sort(self, ctx):
        # this'll take a while
        await ctx.defer(ephemeral=True)

        if ctx.guild.get_channel(env.int("CATEGORY_ID")):
            channels = ctx.guild.get_channel(env.int("CATEGORY_ID")).text_channels
        else:
            await ctx.send_followup("**❌ · Category not found**")
            return

        first_pos = channels[0].position
        pinned_channels = []
        channel_timestamps = {}
        empty_channel_timestamps = {}

        # fetch relevant info, separate empty channels
        for channel in channels:
            try:
                message = await channel.fetch_message(channel.last_message_id)
                timestamp = message.created_at

                for thread in channel.threads:
                    thread_message = await thread.fetch_message(thread.last_message_id)
                    thread_timestamp = thread_message.created_at
                    if timestamp < thread_timestamp:
                        timestamp = thread_timestamp

                channel_timestamps[channel.id] = timestamp
            except (discord.NotFound, discord.HTTPException) as e:
                if e.code in [10008, 50013]:
                    empty_channel_timestamps[channel.id] = channel.created_at

        # separate pinned channels
        for id in env.list("PINNED_CHANNEL_IDS", subcast=int):
            for channel in channels:
                if id == channel.id:
                    pinned_channels.append(id)
                    if id in channel_timestamps:
                        channel_timestamps.pop(id)
                    else:
                        empty_channel_timestamps.pop(id)

        # sort channels
        ordered_channels = (
            pinned_channels
            + sorted(channel_timestamps, reverse=True, key=channel_timestamps.get)
            + sorted(
                empty_channel_timestamps, reverse=True, key=empty_channel_timestamps.get
            )
        )

        for i, id in enumerate(ordered_channels):
            channel = ctx.guild.get_channel(id)
            if channel.position != first_pos + i:
                channel.edit(position=first_pos + i)

        await ctx.send_followup("👍", ephemeral=True)


def setup(bot):
    bot.add_cog(Space(bot))
