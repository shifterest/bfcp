import json

import aiosqlite
import discord
from discord.ext import commands


class Cockpit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    space = discord.SlashCommandGroup("space", "Commands related to spaces")
    config = space.create_subgroup("configure")
    guild = space.create_subgroup("guild")

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
    @space.command(name="add", description="Adds an existing space to the database")
    @discord.default_permissions(manage_channels=True)
    async def create(
        self,
        ctx,
        space: discord.Option(discord.TextChannel, "The space to add to the database"),
        owner: discord.Option(discord.User, "The owner of the space"),
    ):
        await ctx.defer(ephemeral=True)

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
                        ),
                        ephemeral=True,
                    )
                    return
                else:
                    max_spaces_per_owner = row[0]
                    bump_on_message = row[1]
                    bump_on_thread_message = row[2]

            async with db.execute(
                "SELECT * FROM spaces WHERE guild_id = ? AND owner_id = ?",
                (ctx.guild.id, owner.id),
            ) as cursor:
                rows = await cursor.fetchall()
                if len(rows) >= max_spaces_per_owner:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description="This owner has reached the maximum amount of spaces for this server.",
                        ),
                        ephemeral=True,
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
                description=f"{space.mention} is now configured and owned by {owner.mention}.",
                color=discord.Colour.green(),
            ),
            ephemeral=True,
        )

    # set category for spaces
    @guild.command(
        name="category",
        description="Sets a category in which spaces will be managed",
    )
    @discord.default_permissions(manage_channels=True)
    async def create(
        self,
        ctx,
        category: discord.Option(
            discord.CategoryChannel, "The category in which spaces will be managed"
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
                "UPDATE guilds SET space_category_id = ? WHERE guild_id = ?",
                (category.id, ctx.guild.id),
            )
            await db.commit()

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"Spaces will be managed in `{category.name}`.",
                color=discord.Colour.green(),
            ),
            ephemeral=True,
        )

    # set maximum spaces per owner
    @guild.command(
        name="max-spaces-per-owner",
        description="Sets a maximum amount of spaces per owner",
    )
    @discord.default_permissions(manage_channels=True)
    async def create(
        self,
        ctx,
        value: discord.Option(int, min_value=1),
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
                "UPDATE guilds SET max_spaces_per_owner = ? WHERE guild_id = ?",
                (value, ctx.guild.id),
            )
            await db.commit()

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"Maximum amount of spaces per owner set to {value}.",
                color=discord.Colour.green(),
            ),
            ephemeral=True,
        )

    # add/remove role to whitelist
    @guild.command(
        name="whitelist",
        description="Adds or removes a role to and from the default whitelist",
    )
    @discord.default_permissions(manage_channels=True)
    async def create(
        self,
        ctx,
        role: discord.Option(discord.Role, "The role to add/remove"),
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
                ephemeral=True,
            )
        else:
            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"{role.mention} was removed from the whitelist.",
                    color=discord.Colour.green(),
                ),
                ephemeral=True,
            )

    # pin/unpin channel
    @space.command(
        name="pin",
        description="Pins or unpins a channel to or from the spaces category",
    )
    @discord.default_permissions(manage_channels=True)
    async def create(
        self,
        ctx,
        channel: discord.Option(discord.TextChannel, "The channel to pin/unpin"),
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
                ephemeral=True,
            )
        else:
            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"{channel.mention} is now unpinned.",
                    color=discord.Colour.green(),
                ),
                ephemeral=True,
            )

    # configure default bump on message
    @guild.command(
        name="bump-on-message",
        description="Configures whether sending a message in a space bumps it",
    )
    @discord.default_permissions(manage_channels=True)
    async def create(
        self,
        ctx,
        value: discord.Option(bool, "The value to set for this configuration"),
    ):
        await Cockpit.configure_guild("bump-on-thread", ctx, value)

    # configure default bump on thread message
    @guild.command(
        name="bump-on-thread-message",
        description="Configures whether sending a message in a space's threads bumps it",
    )
    @discord.default_permissions(manage_channels=True)
    async def create(
        self,
        ctx,
        value: discord.Option(bool, "The value to set for this configuration"),
    ):
        await Cockpit.configure_guild("bump-on-thread-message", ctx, value)

    # sort spaces
    @space.command(
        name="sort", description="Sorts spaces by activity in descending order"
    )
    @discord.default_permissions(manage_channels=True)
    async def sort(self, ctx):
        # this'll take a while
        await ctx.defer(ephemeral=True)

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
                        ephemeral=True,
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
                    ephemeral=True,
                )
                return
        else:
            await ctx.send_followup(
                embed=discord.Embed(
                    description="The category for spaces configured for this server was not found.",
                    color=discord.Colour.red(),
                ),
                ephemeral=True,
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
            ephemeral=True,
        )

    # clean space database
    @space.command(
        name="clean",
        description="Cleans unresolved spaces and/or owners in this server from the database",
    )
    @discord.default_permissions(manage_channels=True)
    async def create(
        self,
        ctx,
        ignore_owners: discord.Option(
            bool,
            "Whether to ignore spaces whos owners are not in the server",
            required=False,
        ),
    ):
        await ctx.defer(ephemeral=True)

        async with aiosqlite.connect("data/database.db") as db:
            async with db.execute(
                "SELECT space_id, owner_id FROM spaces WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                rows = await cursor.fetchall()
                if rows:
                    space_ids = [
                        row[0] for row in rows if not ctx.guild.get_channel(row[0])
                    ]
                    if space_ids:
                        space_params = ", ".join("?" * len(space_ids))
                        await db.execute(
                            f"DELETE FROM spaces WHERE space_id IN ({space_params})",
                            space_ids,
                        )
                        await db.commit()
                    if ignore_owners:
                        await ctx.send_followup(
                            embed=discord.Embed(
                                description=f"{len(space_ids)} spaces cleaned from the database.",
                                color=discord.Colour.green(),
                            ),
                            ephemeral=True,
                        )
                    else:
                        owner_ids = [
                            row[1] for row in rows if not ctx.guild.get_member(row[1])
                        ]
                        if owner_ids:
                            owner_params = ", ".join("?" * len(owner_ids))
                            await db.execute(
                                f"DELETE FROM spaces WHERE owner_id IN ({owner_params})",
                                owner_ids,
                            )
                            await db.commit()
                            await ctx.send_followup(
                                embed=discord.Embed(
                                    description=f"{len(space_ids)} spaces and {len(owner_ids)} owners cleaned from the database.",
                                    color=discord.Colour.green(),
                                ),
                                ephemeral=True,
                            )
                else:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description="There are no spaces to clean."
                        ),
                        ephemeral=True,
                    )
                    return

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
        await ctx.defer(ephemeral=True)

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
                        ),
                        ephemeral=True,
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
                        ),
                        ephemeral=True,
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
            ),
            ephemeral=True,
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
        await ctx.defer(ephemeral=True)

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
                        ephemeral=True,
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
                        ephemeral=True,
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
            ephemeral=True,
        )

    # configure space
    async def configure_space(option, ctx, space, value):
        await ctx.defer(ephemeral=True)

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
                        ),
                        ephemeral=True,
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
                    ),
                    ephemeral=True,
                )
            else:
                await ctx.send_followup(
                    embed=discord.Embed(
                        description=f"You do not own {space.mention}.",
                        color=discord.Colour.green(),
                    ),
                    ephemeral=True,
                )

    # configure guild
    async def configure_guild(option, ctx, value):
        await ctx.defer(ephemeral=True)

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
                ),
                ephemeral=True,
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
