import discord
from discord.ext import commands
from discord.ext.commands import UserConverter

from greedy_components import greedyBase as gb

from greedy_components import greedySecurity as gs
from greedy_components.greedyConverters import NoYesConverter

import support.security as sec

class GreedyGhostCog_GuildMembers(gb.GreedyGhostCog):
    """ Handles syncing of Gulds and members to database and allows for guild authorization and member registration """
    # member monitoring

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        iu, _ = self.bot.dbm.validators.getValidateBotUser(member.id).validate()
        ig, guild = self.bot.dbm.validators.getValidateGuild(member.guild.id).validate()
        if not iu and ig and guild["authorized"]:
            self.bot.dbm.registerUser(member.id, member.name, self.bot.config['BotOptions']['default_language'])

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        self.bot.checkAndRemoveUser(member)

    @commands.Cog.listener()
    async def on_member_update(self, member_before: discord.Member, member_after: discord.Member):
        iu, _ = self.bot.dbm.validators.getValidateBotUser(member_after.id).validate()
        if iu:
            self.bot.dbm.updateUser(member_after.id, member_after.name)

    # this command is not needed anymore and is here only in case the bot misses someone joining and we don't want to wait up to 1 day for the user maintenance task to catch up
    # remember: if we register a User that is not actually in a guild that the bot can see, the registration will be removed when the maintenance task runs
    @commands.command(name = 'register', brief='Registra un utente nel database')
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def register(self, ctx: commands.Context, user: UserConverter): 

        userid = user.id

        iu, _ = self.bot.dbm.validators.getValidateBotUser(userid).validate()
        if not iu:
            self.bot.dbm.registerUser(userid, user.name, self.bot.config['BotOptions']['default_language'])
            await self.bot.atSendLang(ctx, "string_mgs_user_registered")
        else:
            await self.bot.atSendLang(ctx, "string_mgs_user_already_registered")

    # guild monitoring

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.bot.checkAndJoinGuild(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        guild_map = self.bot.getGuildActivationMap()
        for member in guild.members:
            self.bot.checkAndRemoveUser(member, guild_map)
        self.bot.dbm.removeGuild(guild.id)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        ig, _ = self.bot.dbm.validators.getValidateGuild(after.id).validate()
        if ig:
            self.bot.dbm.updateGuildName(after.id, after.name)

    @commands.command(name = 'gauth', brief='Abilita il server ad utilizzare le funzionalità del bot')
    @commands.before_invoke(gs.command_security(sec.IsAdmin))
    async def guild_authorization(self, ctx: commands.Context, authorize: NoYesConverter = None): 
        guild_ctx = ctx.guild
        if guild_ctx is None:
            raise gb.GreedyCommandError("string_error_not_available_outside_guild")

        await self.bot.checkAndJoinGuild(guild_ctx)

        guild_db = self.bot.dbm.validators.getValidateGuild(guild_ctx.id).get()

        if authorize is None:
            status_str = None
            if guild_db["authorized"]:
                status_str = "string_msg_guild_authstatus_enabled"
            else:
                status_str = "string_msg_guild_authstatus_disabled"
            status = self.bot.getStringForUser(ctx, status_str)
            await self.bot.atSendLang(ctx, "string_msg_guild_authstatus", status)
        elif authorize:
            self.bot.dbm.updateGuildAuthorization(guild_ctx.id, True)
            for member in guild_ctx.members:
                iu, _ = self.bot.dbm.validators.getValidateBotUser(member.id).validate()
                if not iu:
                    self.bot.dbm.registerUser(member.id, member.name, self.bot.config['BotOptions']['default_language'])
            await self.bot.atSendLang(ctx, "string_msg_guild_authstatus", self.bot.getStringForUser(ctx, "string_msg_guild_authstatus_enabled"))
        else:
            self.bot.dbm.updateGuildAuthorization(guild_ctx.id, False)
            guild_map = self.bot.getGuildActivationMap()
            for member in guild_ctx.members:
                self.bot.checkAndRemoveUser(member, guild_map)
            await self.bot.atSendLang(ctx, "string_msg_guild_authstatus", self.bot.getStringForUser(ctx, "string_msg_guild_authstatus_disabled"))
            