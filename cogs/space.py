import json

import aiosqlite
import discord
from discord.ext import commands


class Cockpit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    guild = discord.SlashCommandGroup("guild", "Commands to configure the guild")

    space = discord.SlashCommandGroup("space", "Commands related to spaces")
    config = space.create_subgroup("config")

    # bump spaces
    @commands.Cog.listener()
    async def on_message(self, message):
        channel = message.channel

        if channel.type == discord.ChannelType.public_thread:
            channel = channel.parent
        elif channel.type != discord.ChannelType.text:
            return

        async with aiosqlite.connect("data/database.db") as db:
            async with db.execute(
                "SELECT bump_on_message, bump_on_thread_message FROM spaces WHERE guild_id = ? AND space_id = ?",
                (channel.guild.id, channel.id),
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return
                else:
                    bump_on_message = row[0]
                    bump_on_thread_message = row[1]

        if (
            channel.type == discord.ChannelType.public_thread
            and not bump_on_thread_message
        ) or (channel.type == discord.ChannelType.text and not bump_on_message):
            return

        async with aiosqlite.connect("data/database.db") as db:
            async with db.execute(
                "SELECT space_category_id, pinned_channel_ids FROM guilds WHERE guild_id = ?",
                (channel.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is not None:
                    space_category_id = row[0]
                    pinned_channel_ids = json.loads(row[1])

        if channel.id in pinned_channel_ids:
            return

        if channel.category_id == space_category_id:
            position = 0

            for id in pinned_channel_ids:
                pinned_channel = message.guild.get_channel(id)
                if pinned_channel and pinned_channel.category_id == channel.category_id:
                    position = max(position, pinned_channel.position)

            if channel.position != position + 1:
                await channel.edit(position=position + 1)

    # add space to database
    @guild.command(
        name="add-space", description="Adds an existing space to the database"
    )
    async def create(
        self,
        ctx,
        space: discord.Option(discord.TextChannel, "The space to add to the database"),
        owner: discord.Option(discord.User, "The owner of the space"),
    ):
        await ctx.defer()

        async with aiosqlite.connect("data/database.db") as db:
            async with db.execute(
                "SELECT max_spaces_per_owner, bump_on_message, bump_on_thread_message FROM guilds WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description="The category for spaces is not set for this server.",
                        )
                    )
                    return
                else:
                    max_spaces_per_owner = row[0]
                    bump_on_message = row[1]
                    bump_on_thread_message = row[2]

            async with db.execute(
                "SELECT space_id FROM spaces WHERE guild_id = ? AND owner_id = ?",
                (ctx.guild.id, owner.id),
            ) as cursor:
                rows = await cursor.fetchall()
                for space_id in [row[0] for row in rows]:
                    if space.id == space_id:
                        await ctx.send_followup(
                            embed=discord.Embed(
                                description="This space already exists in the database.",
                            )
                        )
                        return
                if len(rows) >= max_spaces_per_owner:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description="This owner has reached the maximum amount of spaces for this server.",
                        )
                    )
                    return

            async with db.execute(
                "SELECT * FROM spaces WHERE guild_id = ? AND owner_id = ?",
                (ctx.guild.id, owner.id),
            ) as cursor:
                rows = await cursor.fetchall()
                if len(rows) >= max_spaces_per_owner:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description="This owner has reached the maximum amount of spaces for this server.",
                        )
                    )
                    return

            await db.execute(
                "INSERT INTO spaces VALUES (?, ?, ?, ?, ?)",
                (
                    space.id,
                    space.guild.id,
                    owner.id,
                    bump_on_message,
                    bump_on_thread_message,
                ),
            )
            await db.commit()

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"{space.mention} is now owned by {owner.mention}.",
                color=discord.Colour.green(),
            )
        )

    # set category for spaces
    @guild.command(
        name="set-space-category",
        description="Sets a category in which spaces will be managed",
    )
    async def create(
        self,
        ctx,
        category: discord.Option(
            discord.CategoryChannel, "The category in which spaces will be managed"
        ),
    ):
        await ctx.defer()

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
                        )
                    )
                    return
            await db.execute(
                "UPDATE guilds SET space_category_id = ? WHERE guild_id = ?",
                (category.id, ctx.guild.id),
            )
            await db.commit()

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"Spaces will be managed in `{category.name}`.",
                color=discord.Colour.green(),
            )
        )

    # set maximum spaces per owner
    @guild.command(
        name="set-max-spaces-per-owner",
        description="Sets a maximum amount of spaces per owner",
    )
    async def create(
        self,
        ctx,
        value: discord.Option(int, min_value=1),
    ):
        await ctx.defer()

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
                        )
                    )
                    return
            await db.execute(
                "UPDATE guilds SET max_spaces_per_owner = ? WHERE guild_id = ?",
                (value, ctx.guild.id),
            )
            await db.commit()

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"Maximum amount of spaces per owner set to {value}.",
                color=discord.Colour.green(),
            ),
        )

    # add/remove role to whitelist
    @guild.command(
        name="modify-whitelist",
        description="Adds or removes a role to and from the default whitelist",
    )
    async def create(
        self,
        ctx,
        role: discord.Option(discord.Role, "The role to add/remove"),
    ):
        await ctx.defer()

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
                    )
                    return

            async with db.execute(
                "SELECT whitelisted_role_ids FROM guilds WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is not None:
                    whitelisted_role_ids = json.loads(row[0])
                    if role.id in whitelisted_role_ids:
                        whitelisted_role_ids.remove(role.id)
                    else:
                        whitelisted_role_ids.append(role.id)

            await db.execute(
                "UPDATE guilds SET whitelisted_role_ids = ? WHERE guild_id = ?",
                (json.dumps(whitelisted_role_ids), ctx.guild.id),
            )
            await db.commit()

        if role.id in whitelisted_role_ids:
            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"{role.mention} was added to the whitelist.",
                    color=discord.Colour.green(),
                ),
            )
        else:
            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"{role.mention} was removed from the whitelist.",
                    color=discord.Colour.green(),
                ),
            )

    # pin/unpin channel
    @space.command(
        name="pin-channel",
        description="Pins or unpins a channel to or from the spaces category",
    )
    async def create(
        self,
        ctx,
        channel: discord.Option(discord.TextChannel, "The channel to pin/unpin"),
    ):
        await ctx.defer()

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
                    )
                    return

            async with db.execute(
                "SELECT pinned_channel_ids FROM guilds WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is not None:
                    pinned_channel_ids = json.loads(row[0])
                    if channel.id in pinned_channel_ids:
                        pinned_channel_ids.remove(channel.id)
                    else:
                        pinned_channel_ids.append(channel.id)

            await db.execute(
                "UPDATE guilds SET pinned_channel_ids = ? WHERE guild_id = ?",
                (json.dumps(pinned_channel_ids), ctx.guild.id),
            )
            await db.commit()

        if channel.id in pinned_channel_ids:
            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"{channel.mention} is now pinned.",
                    color=discord.Colour.green(),
                ),
            )
        else:
            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"{channel.mention} is now unpinned.",
                    color=discord.Colour.green(),
                ),
            )

    # set default bump on message
    @guild.command(
        name="set-bump-on-message",
        description="Configures whether sending a message in a space bumps it",
    )
    async def create(
        self,
        ctx,
        value: discord.Option(bool, "The value to set for this configuration"),
    ):
        await Cockpit.configure_guild("bump-on-thread", ctx, value)

    # set bump on thread message
    @guild.command(
        name="set-bump-on-thread-message",
        description="Configures whether sending a message in a space's threads bumps it",
    )
    async def create(
        self,
        ctx,
        value: discord.Option(bool, "The value to set for this configuration"),
    ):
        await Cockpit.configure_guild("bump-on-thread-message", ctx, value)

    # sort spaces
    @guild.command(
        name="sort-spaces", description="Sorts spaces by activity in descending order"
    )
    async def sort(self, ctx):
        # this'll take a while
        await ctx.defer()

        async with aiosqlite.connect("data/database.db") as db:
            async with db.execute(
                "SELECT space_category_id, pinned_channel_ids FROM guilds WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description="The category for spaces is not set for this server.",
                        ),
                    )
                    return
                else:
                    space_category_id = row[0]
                    pinned_channel_ids = json.loads(row[1])

        if ctx.guild.get_channel(space_category_id):
            channels = ctx.guild.get_channel(space_category_id).text_channels

            async with aiosqlite.connect("data/database.db") as db:
                async with db.execute(
                    "SELECT space_id FROM spaces WHERE guild_id = ?", (ctx.guild.id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    space_ids = [row[0] for row in rows]

            spaces = [
                c
                for c in channels
                if c.id in space_ids and c.id not in pinned_channel_ids
            ]
            if not spaces:
                await ctx.send_followup(
                    embed=discord.Embed(description="There are no spaces to sort."),
                )
                return
        else:
            await ctx.send_followup(
                embed=discord.Embed(
                    description="The category for spaces configured for this server was not found.",
                    color=discord.Colour.red(),
                ),
            )
            return

        pinned_channels = [c.id for c in channels if c.id in pinned_channel_ids]
        first_pos = channels[0].position
        channel_timestamps = {}
        empty_channel_timestamps = {}

        for space in spaces:
            try:
                message = await space.fetch_message(space.last_message_id)
                timestamp = message.created_at

                for thread in space.threads:
                    thread_message = await thread.fetch_message(thread.last_message_id)
                    thread_timestamp = thread_message.created_at
                    if thread_timestamp > timestamp:
                        timestamp = thread_timestamp

                channel_timestamps[space.id] = timestamp
            except (discord.NotFound, discord.HTTPException) as e:
                if e.code in [10008, 50013]:
                    empty_channel_timestamps[space.id] = channel.created_at

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
                await channel.edit(position=first_pos + i)

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"Spaces were successfully sorted.",
                color=discord.Colour.green(),
            ),
        )

    # clean space database
    @guild.command(
        name="clean-space-db",
        description="Cleans unresolved spaces and/or owners in this server from the database",
    )
    async def create(
        self,
        ctx,
        ignore_owners: discord.Option(
            bool,
            "Whether to ignore spaces whos owners are not in the server",
            required=False,
        ),
    ):
        await ctx.defer()

        async with aiosqlite.connect("data/database.db") as db:
            async with db.execute(
                "SELECT space_id, owner_id FROM spaces WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                rows = await cursor.fetchall()
                if rows:
                    space_ids = [row[0] for row in rows]
                    space_ids_to_clean = []
                    for space_id in space_ids:
                        if not ctx.guild.get_channel(space_id):
                            space_ids_to_clean.append(space_id)
                    if space_ids_to_clean:
                        space_params = ", ".join("?" * len(space_ids_to_clean))
                        await db.execute(
                            f"DELETE FROM spaces WHERE space_id IN ({space_params})",
                            space_ids_to_clean,
                        )
                        await db.commit()
                    if ignore_owners:
                        await ctx.send_followup(
                            embed=discord.Embed(
                                description=f"{len(space_ids_to_clean)} spaces cleaned from the database.",
                                color=discord.Colour.green(),
                            )
                        )
                    else:
                        owner_ids = [row[1] for row in rows]
                        owner_ids_to_clean = []
                        for owner_id in owner_ids:
                            if not ctx.guild.get_channel(owner_id):
                                owner_ids_to_clean.append(owner_id)
                        if owner_ids_to_clean:
                            owner_params = ", ".join("?" * len(owner_ids_to_clean))
                            await db.execute(
                                f"DELETE FROM spaces WHERE owner_id IN ({owner_params})",
                                owner_ids_to_clean,
                            )
                            await db.commit()
                            await ctx.send_followup(
                                embed=discord.Embed(
                                    description=f"{len(space_ids)} spaces and {len(owner_ids_to_clean)} owners cleaned from the database.",
                                    color=discord.Colour.green(),
                                )
                            )
                else:
                    await ctx.send_followup(
                        embed=discord.Embed(description="There are no spaces to clean.")
                    )

    # create space
    @space.command(name="create", description="Creates a space given an owner")
    async def create(
        self,
        ctx,
        owner: discord.Option(discord.User, "The owner of the space", required=False),
        name: discord.Option(
            str, "The name of the channel", required=False, min_length=1
        ),
    ):
        await ctx.defer()

        owner = owner or ctx.author

        async with aiosqlite.connect("data/database.db") as db:
            async with db.execute(
                "SELECT space_category_id, max_spaces_per_owner, whitelisted_role_ids FROM guilds WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description="The category for spaces is not set for this server.",
                        )
                    )
                    return
                else:
                    space_category_id = row[0]
                    max_spaces_per_owner = row[1]
                    whitelisted_role_ids = json.loads(row[2])

            async with db.execute(
                "SELECT * FROM spaces WHERE guild_id = ? AND owner_id = ?",
                (ctx.guild.id, owner.id),
            ) as cursor:
                rows = await cursor.fetchall()
                if len(rows) >= max_spaces_per_owner:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description="This owner has reached the maximum amount of spaces for this server.",
                        )
                    )
                    return

        category = ctx.guild.get_channel(space_category_id)
        if not name:
            name = f"{owner.display_name}-space"
        overwrites = {
            owner: discord.PermissionOverwrite(
                view_channel=True,
                manage_channels=True,
                manage_permissions=True,
                manage_webhooks=True,
                read_messages=True,
                send_messages=True,
            )
        }
        if whitelisted_role_ids:
            overwrites[ctx.guild.default_role] = discord.PermissionOverwrite(
                view_channel=False, send_messages=False
            )
            for id in whitelisted_role_ids:
                if ctx.guild.get_role(id):
                    overwrites[ctx.guild.get_role(id)] = discord.PermissionOverwrite(
                        view_channel=True
                    )
        else:
            overwrites[ctx.guild.default_role] = discord.PermissionOverwrite(
                send_messages=False
            )

        space = await category.create_text_channel(name, overwrites=overwrites)

        async with aiosqlite.connect("data/database.db") as db:
            async with db.execute(
                "SELECT bump_on_message, bump_on_thread_message FROM guilds WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is not None:
                    bump_on_message = row[0]
                    bump_on_thread_message = row[1]

            await db.execute(
                "INSERT INTO spaces VALUES (?, ?, ?, ?, ?)",
                (
                    space.id,
                    space.guild.id,
                    owner.id,
                    bump_on_message,
                    bump_on_thread_message,
                ),
            )
            await db.commit()

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"{space.mention} was successfully created for {owner.mention}.",
                color=discord.Colour.green(),
            )
        )
        await ctx.channel.send(
            owner.mention,
            embed=discord.Embed(
                description=f"Check your space out at {space.mention}!",
            ),
            allowed_mentions=discord.AllowedMentions.all(),
        )

    # restore space permissions
    @space.command(
        name="restore", description="Restores default permissions for a space"
    )
    async def create(
        self,
        ctx,
        space: discord.Option(
            discord.TextChannel, "The space to restore permissions for"
        ),
    ):
        await ctx.defer()

        async with aiosqlite.connect("data/database.db") as db:
            async with db.execute(
                "SELECT whitelisted_role_ids FROM guilds WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description="The category for spaces is not set for this server.",
                        ),
                    )
                    return
                else:
                    whitelisted_role_ids = json.loads(row[0])

            async with db.execute(
                "SELECT owner_id FROM spaces WHERE guild_id = ? AND space_id = ?",
                (ctx.guild.id, space.id),
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description=f"{space.mention} is not a space."
                        ),
                    )
                    return
                else:
                    owner_id = row[0]

            if ctx.author.id == owner_id:
                overwrites = {
                    ctx.author: discord.PermissionOverwrite(
                        view_channel=True,
                        manage_channels=True,
                        manage_permissions=True,
                        manage_webhooks=True,
                        read_messages=True,
                        send_messages=True,
                    )
                }
                if whitelisted_role_ids:
                    overwrites[ctx.guild.default_role] = discord.PermissionOverwrite(
                        view_channel=False, send_messages=False
                    )
                    for id in whitelisted_role_ids:
                        if ctx.guild.get_role(id):
                            overwrites[
                                ctx.guild.get_role(id)
                            ] = discord.PermissionOverwrite(view_channel=True)
                else:
                    overwrites[ctx.guild.default_role] = discord.PermissionOverwrite(
                        send_messages=False
                    )

                await space.edit(overwrites=overwrites)

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"Permissions for {space.mention} successfully restored.",
                color=discord.Colour.green(),
            ),
        )

    # configure space
    async def configure_space(option, ctx, space, value):
        await ctx.defer()

        async with aiosqlite.connect("data/database.db") as db:
            async with db.execute(
                "SELECT owner_id FROM spaces WHERE guild_id = ? AND space_id = ?",
                (ctx.guild.id, space.id),
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description=f"{space.mention} is not a space."
                        )
                    )
                    return
                else:
                    owner_id = row[0]

            if ctx.author.id == owner_id:
                await db.execute(
                    f"UPDATE spaces SET {option} = ? WHERE space_id = ?",
                    (value, space.id),
                )
                await db.commit()

                await ctx.send_followup(
                    embed=discord.Embed(
                        description=f"`{option}` for {space.mention} is now set to `{value}`.",
                        color=discord.Colour.green(),
                    )
                )
            else:
                await ctx.send_followup(
                    embed=discord.Embed(
                        description=f"You do not own {space.mention}.",
                        color=discord.Colour.green(),
                    )
                )

    # configure guild
    async def configure_guild(option, ctx, value):
        await ctx.defer()

        async with aiosqlite.connect("data/database.db") as db:
            await db.execute(
                f"UPDATE guilds SET {option} = ? WHERE guild_id = ?",
                (value, ctx.guild.id),
            )
            await db.commit()

            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"`{option}` for **{ctx.guild.name}** is now set to `{value}`.",
                    color=discord.Colour.green(),
                )
            )

    # configure bump on message
    @config.command(
        name="bump-on-message",
        description="Configures whether sending a message in a space bumps it",
    )
    async def create(
        self,
        ctx,
        space: discord.Option(discord.TextChannel, "The space to configure"),
        value: discord.Option(bool, "The value to set for this configuration"),
    ):
        await Cockpit.configure_space("bump_on_message", ctx, space, value)

    # configure bump on thread message
    @config.command(
        name="bump-on-thread-message",
        description="Configures whether sending a message in a space's threads bumps it",
    )
    async def create(
        self,
        ctx,
        space: discord.Option(discord.TextChannel, "The space to configure"),
        value: discord.Option(bool, "The value to set for this configuration"),
    ):
        await Cockpit.configure_space("bump_on_thread_message", ctx, space, value)


def setup(bot):
    bot.add_cog(Cockpit(bot))
