import aiosqlite
import discord
from discord.ext import commands

from stuff.db import Guild, Owner, Space


class Cockpit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    guild_group = discord.SlashCommandGroup("guild", "Commands to configure the guild")

    space_group = discord.SlashCommandGroup("space", "Commands related to spaces")
    config_group = space_group.create_subgroup("config")

    # Overwrites
    def overwrites(owner, guild, whitelisted_role_ids):
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
        override_roles = [
            guild.get_role(id)
            for id in whitelisted_role_ids
            if guild.get_role(id) and owner.get_role(id)
        ]
        if override_roles:
            overwrites[guild.default_role] = discord.PermissionOverwrite(
                view_channel=False, send_messages=False
            )
            for role in override_roles:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True)
        else:
            overwrites[guild.default_role] = discord.PermissionOverwrite(
                send_messages=False
            )
        return overwrites

    # Bump spaces
    @commands.Cog.listener()
    async def on_message(self, message):
        channel = message.channel

        if not channel.type in (
            discord.ChannelType.text,
            discord.ChannelType.public_thread,
        ):
            return

        space_db = Space()
        if channel.type == discord.ChannelType.public_thread:
            await space_db.async_init(channel.id, channel.parent.guild.id)
        else:
            await space_db.async_init(channel.id, channel.guild.id)
        if (
            not space_db.exists
            or (
                channel.type == discord.ChannelType.public_thread
                and not space_db.bump_on_thread_message
            )
            or (
                channel.type == discord.ChannelType.text
                and not space_db.bump_on_message
            )
        ):
            return

        if channel.type == discord.ChannelType.public_thread:
            channel = channel.parent

        guild_db = Guild()
        await guild_db.async_init(channel.guild.id)
        if not guild_db.exists and channel.id in guild_db.pinned_channel_ids:
            return

        if channel.category_id == guild_db.space_category_id:
            position = 0

            for id in guild_db.pinned_channel_ids:
                pinned_channel = message.guild.get_channel(id)
                if pinned_channel and pinned_channel.category_id == channel.category_id:
                    position = max(position, pinned_channel.position)
            if channel.position != position + 1:
                await channel.edit(position=position + 1)

    # Display guild info
    @guild_group.command(
        name="info", description="Displays information about this server"
    )
    async def create(self, ctx):
        await ctx.defer()

        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if await guild_db.check_exists(ctx):
            greet_channel = (
                f"<#{guild_db.greet_channel_id}>"
                if guild_db.greet_channel_id
                else "None"
            )
            greet_attachments = (
                ", ".join(guild_db.greet_attachments)
                if guild_db.greet_attachments
                else "None"
            )
            space_category = (
                f"<#{guild_db.space_category_id}>"
                if guild_db.space_category_id
                else "None"
            )
            space_owner_role = (
                f"<@&{guild_db.space_owner_role_id}>"
                if guild_db.space_owner_role_id
                else "None"
            )
            pinned_channels = (
                ", ".join(f"<#{id}>" for id in guild_db.pinned_channel_ids)
                if guild_db.pinned_channel_ids
                else "None"
            )
            whitelisted_roles = (
                ", ".join(f"<@&{id}>" for id in guild_db.whitelisted_role_ids)
                if guild_db.whitelisted_role_ids
                else "None"
            )
            bump_on_message = "Yes" if guild_db.bump_on_message else "No"
            bump_on_thread_message = "Yes" if guild_db.bump_on_thread_message else "No"
            await ctx.send_followup(
                embed=discord.Embed(
                    title=f"About {ctx.guild.name}",
                    description=f"""Greet channel: **{greet_channel}**
                    Greet attachments: **{greet_attachments}**
                    Space category: **{space_category}**
                    Space owner role: **{space_owner_role}**
                    Maximum spaces per owner: **{guild_db.max_spaces_per_owner}**
                    Pinned channels: **{pinned_channels}**
                    Whitelisted roles: **{whitelisted_roles}**
                    Bump on message by default: **{bump_on_message}**
                    Bump on thread message by default: **{bump_on_thread_message}**""",
                )
            )

    # Display space info
    @space_group.command(name="info", description="Displays information about a space")
    async def create(
        self,
        ctx,
        space: discord.Option(discord.TextChannel, "The space to get info for"),
    ):
        await ctx.defer()

        space_db = Space()
        await space_db.async_init(space.id, ctx.guild.id)
        if await space_db.check_exists(ctx, True):
            bump_on_message = "Yes" if space_db.bump_on_message else "No"
            bump_on_thread_message = "Yes" if space_db.bump_on_thread_message else "No"
            await ctx.send_followup(
                embed=discord.Embed(
                    title=f"About {space.mention}",
                    description=f"""Owner: **<@{space_db.owner_id}>**
                    Bump on message: **{bump_on_message}**
                    Bump on thread message: **{bump_on_thread_message}**""",
                )
            )

    # Create space for specific owner
    @guild_group.command(
        name="create-space", description="Creates a space given an owner"
    )
    async def create(
        self,
        ctx,
        owner: discord.Option(discord.User, "The owner of the space", required=False),
        name: discord.Option(
            str, "The name of the space", required=False, min_length=1
        ),
    ):
        await ctx.defer()

        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if not await guild_db.check_exists(ctx) and not await guild_db.check_category(
            ctx
        ):
            return

        owner_db = Owner()
        await owner_db.async_init(ctx.guild.id, owner.id)
        if not await owner_db.check_max_spaces(ctx, guild_db.max_spaces_per_owner):
            return

        owner = owner or ctx.author
        name = name or f"{ctx.author.display_name}-space"
        category = ctx.guild.get_channel(guild_db.space_category_id)
        space = await category.create_text_channel(
            name,
            overwrites=Cockpit.overwrites(
                owner, ctx.guild, guild_db.whitelisted_role_ids
            ),
        )

        await Space.add(
            (
                space.id,
                space.guild.id,
                owner.id,
                guild_db.bump_on_message,
                guild_db.bump_on_thread_message,
            )
        )

        space_owner_role = ctx.guild.get_role(guild_db.space_owner_role_id)
        if space_owner_role:
            try:
                await owner.add_roles(space_owner_role)
            except discord.Forbidden:
                await ctx.send_followup(
                    embed=discord.Embed(
                        description=f"Failed to modify {space_owner_role.mention}> for {owner.mention}.",
                        color=discord.Colour.red(),
                    )
                )
                return

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

    # Add space to database
    @guild_group.command(
        name="add-space", description="Adds an existing space to the database"
    )
    async def create(
        self,
        ctx,
        space: discord.Option(discord.TextChannel, "The space to add to the database"),
        owner: discord.Option(discord.User, "The owner of the space"),
    ):
        await ctx.defer()

        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if not await guild_db.check_exists(ctx) and not await guild_db.check_category(
            ctx
        ):
            return

        space_db = Space()
        await space_db.async_init(space.id, space.guild.id)
        if not await space_db.check_exists(ctx, False):
            return

        owner_db = Owner()
        await owner_db.async_init(ctx.guild.id, owner.id)
        if not await owner_db.check_max_spaces(ctx, guild_db.max_spaces_per_owner):
            return

        await Space.add(
            (
                space.id,
                space.guild.id,
                owner.id,
                guild_db.bump_on_message,
                guild_db.bump_on_thread_message,
            )
        )

        space_owner_role = ctx.guild.get_role(guild_db.space_owner_role_id)
        if space_owner_role:
            try:
                await owner.add_roles(space_owner_role)
            except discord.Forbidden:
                await ctx.send_followup(
                    embed=discord.Embed(
                        description=f"Failed to modify {space_owner_role.mention} for {owner.mention}.",
                        color=discord.Colour.red(),
                    )
                )
                return

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"{space.mention} now owned by {owner.mention}.",
                color=discord.Colour.green(),
            )
        )

    # Set owner for a space
    @guild_group.command(
        name="set-space-owner",
        description="Sets an owner for a space",
    )
    async def create(
        self,
        ctx,
        space: discord.Option(discord.TextChannel, "The space to set the owner for"),
        owner: discord.Option(discord.User, "The new owner of the space"),
    ):
        await ctx.defer()

        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if not await guild_db.check_exists(ctx) and not await guild_db.check_category(
            ctx
        ):
            return

        space_db = Space()
        await space_db.async_init(space.id, space.guild.id)
        if not await space_db.check_exists(ctx, True):
            return

        await space_db.set_owner(owner.id)

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"{space.mention} now owned by {owner.mention}.",
                color=discord.Colour.green(),
            )
        )

    # Set category for spaces
    @guild_group.command(
        name="set-space-category",
        description="Sets or unsets a category for spaces",
    )
    async def create(
        self,
        ctx,
        category: discord.Option(discord.CategoryChannel, "The category to set/unset"),
    ):
        await ctx.defer()

        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if await guild_db.check_exists(ctx):
            if guild_db.space_category_id == category.id:
                await guild_db.set_category(None)
                await ctx.send_followup(
                    embed=discord.Embed(
                        description="Category for spaces unset.",
                        color=discord.Colour.green(),
                    )
                )
            else:
                await guild_db.set_category(category.id)
                await ctx.send_followup(
                    embed=discord.Embed(
                        description=f"Category for spaces set to **{category.mention}**.",
                        color=discord.Colour.green(),
                    )
                )

    # Set role for space owners
    @guild_group.command(
        name="set-space-owner-role",
        description="Sets or unsets a role for space owners",
    )
    async def create(
        self,
        ctx,
        role: discord.Option(discord.Role, "The role to set/unset"),
        propagate: discord.Option(
            bool,
            "Whether to add/remove the role from all space owners",
            default="False",
        ),
    ):
        await ctx.defer()

        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if await guild_db.check_exists(ctx):
            if guild_db.space_owner_role_id == role.id:
                await guild_db.set_owner_role(None)
                if propagate:
                    for member in ctx.guild.members:
                        owner_db = Owner()
                        await owner_db.async_init(ctx.guild.id, member.id)
                        if owner_db.exists and role in member.roles:
                            try:
                                await member.remove_roles(role)
                            except discord.Forbidden:
                                await ctx.send_followup(
                                    embed=discord.Embed(
                                        description=f"Failed to modify {role.mention} for {member.mention}.",
                                        color=discord.Colour.red(),
                                    )
                                )
                                return
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description="Role for space owners removed and unset.",
                            color=discord.Colour.green(),
                        )
                    )
                else:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description="Role for space owners unset.",
                            color=discord.Colour.green(),
                        )
                    )
            else:
                if propagate:
                    old_space_owner_role = ctx.guild.get_role(
                        guild_db.space_owner_role_id
                    )
                await guild_db.set_owner_role(role.id)
                if propagate and old_space_owner_role:
                    for member in ctx.guild.members:
                        owner_db = Owner()
                        await owner_db.async_init(ctx.guild.id, member.id)
                        if owner_db.exists and role not in member.roles:
                            try:
                                await member.remove_roles(old_space_owner_role)
                            except discord.Forbidden:
                                await ctx.send_followup(
                                    embed=discord.Embed(
                                        description=f"Failed to modify {old_space_owner_role.mention} for {member.mention}.",
                                        color=discord.Colour.red(),
                                    )
                                )
                                return

                            try:
                                await member.add_roles(role)
                            except discord.Forbidden:
                                await ctx.send_followup(
                                    embed=discord.Embed(
                                        description=f"Failed to modify {role.mention} for {member.mention}.",
                                        color=discord.Colour.red(),
                                    )
                                )
                                return
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description=f"Role for space owners added and set to {role.mention}.",
                            color=discord.Colour.green(),
                        )
                    )
                else:
                    await ctx.send_followup(
                        embed=discord.Embed(
                            description=f"Role for space owners set to {role.mention}.",
                            color=discord.Colour.green(),
                        )
                    )

    # Set maximum spaces per owner
    @guild_group.command(
        name="set-max-spaces-per-owner",
        description="Sets the maximum amount of spaces per owner for this server",
    )
    async def create(
        self,
        ctx,
        value: discord.Option(int, min_value=1),
    ):
        await ctx.defer()

        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if await guild_db.check_exists(ctx):
            await guild_db.set_max_spaces(value)
            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"Maximum amount of spaces per owner for this server set to `{value}`.",
                    color=discord.Colour.green(),
                ),
            )

    # Pin/unpin channel
    @guild_group.command(
        name="pin-channel",
        description="Pins or unpins a channel from the spaces category",
    )
    async def create(
        self,
        ctx,
        channel: discord.Option(discord.TextChannel, "The channel to pin/unpin"),
    ):
        await ctx.defer()

        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if await guild_db.check_exists(ctx):
            if channel.id in guild_db.pinned_channel_ids:
                await guild_db.remove_from_pinned(channel.id)
                await ctx.send_followup(
                    embed=discord.Embed(
                        description=f"{channel.mention} pinned.",
                        color=discord.Colour.green(),
                    ),
                )
            else:
                await guild_db.add_to_pinned(channel.id)
                await ctx.send_followup(
                    embed=discord.Embed(
                        description=f"{channel.mention} unpinned.",
                        color=discord.Colour.green(),
                    ),
                )

    # Add/remove role from whitelist
    @guild_group.command(
        name="modify-whitelist",
        description="Adds or removes a role from the default whitelist",
    )
    async def create(
        self,
        ctx,
        role: discord.Option(discord.Role, "The role to add/remove"),
    ):
        await ctx.defer()

        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if await guild_db.check_exists(ctx):
            if role.id in guild_db.whitelisted_role_ids:
                await guild_db.remove_from_whitelist(role.id)
                await ctx.send_followup(
                    embed=discord.Embed(
                        description=f"{role.mention} added to the whitelist.",
                        color=discord.Colour.green(),
                    ),
                )
            else:
                await guild_db.add_to_whitelist(role.id)
                await ctx.send_followup(
                    embed=discord.Embed(
                        description=f"{role.mention} removed from the whitelist.",
                        color=discord.Colour.green(),
                    ),
                )

    # Set default bump on message
    @guild_group.command(
        name="set-bump-on-message",
        description="Configures whether sending a message in a space bumps it",
    )
    async def create(
        self,
        ctx,
        value: discord.Option(bool, "The value to set"),
    ):
        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if await guild_db.check_exists(ctx):
            await guild_db.set_bump(value)
            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"Bump on message for this server set to `{value}`.",
                    color=discord.Colour.green(),
                )
            )

    # Set bump on thread message
    @guild_group.command(
        name="set-bump-on-thread-message",
        description="Configures whether sending a message in a space's threads bumps it",
    )
    async def create(
        self,
        ctx,
        value: discord.Option(bool, "The value to set"),
    ):
        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if await guild_db.check_exists(ctx):
            await guild_db.set_bump_thread(value)
            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"Bump on thread message for this server set to `{value}`.",
                    color=discord.Colour.green(),
                )
            )

    # Sort spaces
    @guild_group.command(
        name="sort-spaces", description="Sorts spaces by activity in descending order"
    )
    async def sort(self, ctx):
        # this'll take a while
        await ctx.defer()

        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if not await guild_db.check_exists(ctx) and not await guild_db.check_category(
            ctx
        ):
            return

        if ctx.guild.get_channel(guild_db.space_category_id):
            channels = ctx.guild.get_channel(guild_db.space_category_id).text_channels
            pinned_channels = []
            spaces = []

            for channel in channels:
                if channel.id in guild_db.pinned_channel_ids:
                    pinned_channels.append(channel.id)
                    continue

                space_db = Space()
                await space_db.async_init(channel.id, channel.guild.id)
                if space_db.exists:
                    spaces.append(channel)

            if not spaces:
                await ctx.send_followup(
                    embed=discord.Embed(description="There are no spaces to sort."),
                )
                return

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

    # Clean space database
    @guild_group.command(
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
                            if not ctx.guild.get_member(owner_id):
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
                                    description=f"{len(space_ids_to_clean)} spaces and {len(owner_ids_to_clean)} owners cleaned from the database.",
                                    color=discord.Colour.green(),
                                )
                            )
                else:
                    await ctx.send_followup(
                        embed=discord.Embed(description="There are no spaces to clean.")
                    )

    # Create space for self
    @space_group.command(name="create", description="Creates a space given an owner")
    async def create(
        self,
        ctx,
        name: discord.Option(
            str, "The name of the space", required=False, min_length=1
        ),
    ):
        await ctx.defer()

        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if not await guild_db.check_exists(ctx) and not await guild_db.check_category(
            ctx
        ):
            return

        owner_db = Owner()
        await owner_db.async_init(ctx.guild.id, ctx.author.id)
        if not await owner_db.check_max_spaces(ctx, guild_db.max_spaces_per_owner):
            return

        name = name or f"{ctx.author.display_name}-space"
        category = ctx.guild.get_channel(guild_db.space_category_id)
        space = await category.create_text_channel(
            name,
            overwrites=Cockpit.overwrites(
                ctx.author, ctx.guild, guild_db.whitelisted_role_ids
            ),
        )

        await Space.add(
            (
                space.id,
                space.guild.id,
                ctx.author.id,
                guild_db.bump_on_message,
                guild_db.bump_on_thread_message,
            )
        )

        space_owner_role = ctx.guild.get_role(guild_db.space_owner_role_id)
        if space_owner_role:
            try:
                await ctx.author.add_roles(space_owner_role)
            except discord.Forbidden:
                await ctx.send_followup(
                    embed=discord.Embed(
                        description=f"Failed to modify <@&{guild_db.space_owner_role_id}> for {ctx.author.mention}.",
                        color=discord.Colour.red(),
                    )
                )
                return

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"Check your space out at {space.mention}!",
                color=discord.Colour.green(),
            )
        )

    # Restore space permissions
    @space_group.command(
        name="restore", description="Restores default permissions for a space"
    )
    async def create(
        self,
        ctx,
        space: discord.Option(
            discord.TextChannel, "The space to restore permissions for"
        ),
    ):
        guild_db = Guild()
        await guild_db.async_init(ctx.guild.id)
        if not await guild_db.check_exists(ctx) and not await guild_db.check_category(
            ctx
        ):
            return

        space_db = Space()
        await space_db.async_init(space.id, space.guild.id)
        if not await space_db.check_exists(ctx, True):
            return

        await space.edit(
            overwrites=Cockpit.overwrites(
                ctx.author, ctx.guild, guild_db.whitelisted_role_ids
            )
        )

        await ctx.send_followup(
            embed=discord.Embed(
                description=f"Permissions for {space.mention} successfully restored.",
                color=discord.Colour.green(),
            ),
        )

    # Set bump on message
    @config_group.command(
        name="bump-on-message",
        description="Configures whether sending a message in a space bumps it",
    )
    async def create(
        self,
        ctx,
        space: discord.Option(discord.TextChannel, "The space to configure"),
        value: discord.Option(bool, "The value to set"),
    ):
        space_db = Space()
        await space_db.async_init(space.id, space.guild.id)
        if not await space_db.check_exists(
            ctx, True
        ) and not await space_db.check_owner(ctx):
            await space_db.set_bump(value)
            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"Bump on message for {space.mention} set to `{value}`.",
                    color=discord.Colour.green(),
                )
            )

    # Set bump on thread message
    @config_group.command(
        name="bump-on-thread-message",
        description="Configures whether sending a message in a space's threads bumps it",
    )
    async def create(
        self,
        ctx,
        space: discord.Option(discord.TextChannel, "The space to configure"),
        value: discord.Option(bool, "The value to set"),
    ):
        space_db = Space()
        await space_db.async_init(space.id, space.guild.id)
        if not await space_db.check_exists(
            ctx, True
        ) and not await space_db.check_owner(ctx):
            await space_db.set_bump_thread(value)
            await ctx.send_followup(
                embed=discord.Embed(
                    description=f"Bump on thread message for {space.mention} set to `{value}`.",
                    color=discord.Colour.green(),
                )
            )


def setup(bot):
    bot.add_cog(Cockpit(bot))
