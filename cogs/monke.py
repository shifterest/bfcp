import discord
from discord.ext import commands
from environs import Env

# environmental variables
env = Env()
env.read_env()


class Monke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    monke = discord.SlashCommandGroup("monke", "Monke-related commands")

    # create space
    @monke.command(
        name="trust",
        description="Gives someone monke powers",
        guild_ids=env.list("GUILD_ID", subcast=int),
    )
    async def create(
        self,
        ctx,
        member: discord.Option(
            discord.SlashCommandOptionType.user, "The member to give monke powers"
        ),
    ):
        await ctx.defer(ephemeral=True)

        role = ctx.guild.get_role(env.int("MONKE_ROLE_ID"))

        if role in member.roles:
            await ctx.send_followup("👎, user already has monke powers", ephemeral=True)
        else:
            await member.add_roles(role)
            await ctx.send_followup("👍", ephemeral=True)

            await ctx.channel.send(
                member.mention, allowed_mentions=discord.AllowedMentions.all()
            )


def setup(bot):
    bot.add_cog(Monke(bot))
