import json
import random
from io import BytesIO

import aiosqlite
import discord
import requests
from discord.ext import commands


class Greet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    greet = discord.SlashCommandGroup("greet", "Commands related to greeting")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        greet_attachments = [
            "https://cdn.discordapp.com/attachments/990389611660468254/1087258438964351006/GREETINGS_WORT-1637136825528532992.mp4"
        ]

        if before.pending and not after.pending:
            async with aiosqlite.connect("data/database.db") as db:
                async with db.execute(
                    "SELECT greet_channel_id, greet_attachments FROM guilds WHERE guild_id = ?",
                    (after.guild.id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row is None:
                        return
                    else:
                        greet_channel_id = row[0]
                        # greet_attachments = json.loads(row[1])

            greet_channel = after.guild.get_channel(greet_channel_id)

            if greet_channel:
                greet_file = requests.get(random.choice(greet_attachments))

                await greet_channel.send(
                    f"welcome, {after.mention}! make sure to read the server <#882978936022253588> so you don't miss a thing :-)",
                    file=discord.File(
                        BytesIO(greet_file.content), filename="greetings.mp4"
                    ),
                    allowed_mentions=discord.AllowedMentions.all(),
                )

    # Set greet channel
    @greet.command(
        name="category",
        description="Sets the greet channel",
    )
    @discord.default_permissions(manage_channels=True)
    async def create(
        self,
        ctx,
        channel: discord.Option(
            discord.TextChannel, "The channel to set as the green channel"
        ),
    ):
        await ctx.defer(ephemeral=True)

        async with aiosqlite.connect("data/database.db") as db:
            async with db.execute(
                "SELECT * FROM guilds WHERE guild_id = ?", (ctx.guild.id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description=f"This server is not in the database.",
                            color=discord.Colour.red(),
                        ),
                        ephemeral=True,
                    )
                    return
            await db.execute(
                "UPDATE guilds SET greet_channel_id = ? WHERE guild_id = ?",
                (channel.id, ctx.guild.id),
            )
            await db.commit()

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"Greetings will ben sent in `{channel.name}`.",
                color=discord.Colour.green(),
            ),
            ephemeral=True,
        )


def setup(bot):
    bot.add_cog(Greet(bot))
