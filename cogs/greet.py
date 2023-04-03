from io import BytesIO
import requests
import discord
from discord.ext import commands
from environs import Env

# environmental variables
env = Env()
env.read_env()


class Greet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = member.guild.get_channel(env.int("GREET_CHANNEL_ID"))

        if channel.guild.id in env.list("GUILD_ID", subcast=int):
            greet_file = requests.get(env.str("GREET_URL"))

            await channel.send(
                f"welcome, {member.mention}! make sure to read the server <#882978936022253588> so you don't miss a thing :-)",
                file=discord.File(
                    BytesIO(greet_file.content), filename="greetings.mp4"
                ),
                allowed_mentions=discord.AllowedMentions.all(),
            )


def setup(bot):
    bot.add_cog(Greet(bot))
