from discord.ext import commands
import discord, MySQLdb, logging
from discord.ext.commands import UserConverter
from discord.ext import commands

from greedy_components import greedyBase as gb
from greedy_components import cogPCmgmt
from greedy_components import greedySecurity as gs
from greedy_components.greedyConverters import NoYesConverter

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB
import support.security as sec

_log = logging.getLogger(__name__)

class GreedyGhostCog_Basic(gb.GreedyGhostCog):
    """ Does basic functionality for the bot:
        Error handling
        Member syncing
        Guild syncing
    """
    #executed once on bot boot
    #@bot.event
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.bot.user} is connected to the following guilds:\n')
        for guild in self.bot.guilds:
            print(f'{guild.name} (id: {guild.id})')
        #add self to user list
        iu, _ = self.bot.dbm.validators.getValidateBotUser(self.bot.user.id).validate()
        if not iu:
            self.bot.dbm.registerUser(self.bot.user.id, self.bot.user.name, self.bot.config['BotOptions']['default_language'])
        # notify debug user that bot is online
        await self.bot.logToDebugUser("Bot is Online!")
    

    @commands.Cog.listener()
    async def on_command_error(self, ctx: gb.GreedyContext, error: Exception):
        place  =  f'guild {ctx.channel.guild.name} ({ctx.channel.guild.id}), channel {ctx.channel.name} ({ctx.channel.id})' if isinstance(ctx.channel, discord.abc.GuildChannel) else 'a private channel'
        _log.info(f'Error in command "{ctx.message.content}" from user {ctx.message.author.name} ({ctx.message.author.id}) in {place}: {error}')
        lid = ctx.getLID()
        error = getattr(error, 'original', error)
        #ignored = (commands.CommandNotFound, )
        #if isinstance(error, ignored):
        #    print(error)
        if isinstance(error, commands.CommandNotFound):
            try:
                msgsplit = ctx.message.content.split(" ")
                msgsplit[0] = msgsplit[0][1:] # toglie prefisso
                msgsplit = [y for y in msgsplit if y != '']  # toglie stringhe vuote
                charid = msgsplit[0]
                ic, character = self.bot.dbm.validators.getValidateCharacter(charid).validate()
                if ic:
                    pgmanage_cog: cogPCmgmt.GreedyGhostCog_PCmgmt = self.bot.get_cog(cogPCmgmt.GreedyGhostCog_PCmgmt.__name__)
                    if pgmanage_cog is not None:
                        command_args = (character, *msgsplit[1:])
                        command: commands.Command = pgmanage_cog.bot.get_command('pgmanage')
                        ctx.args = [pgmanage_cog, ctx, *command_args]
                        await command.call_before_hooks(ctx)
                        await ctx.invoke(command, *command_args)
                    else:
                        await self.bot.atSendLang(ctx, "string_error_wat")# TODO error cog not loaded
                else:
                    await self.bot.atSendLang(ctx, "string_error_wat")
                return
            except Exception as e:
                error = e
        if isinstance(error, gb.BotException):
            await self.bot.atSend(ctx, f'{error}')
        elif isinstance(error, lng.LangSupportErrorGroup):
            await self.bot.atSend(ctx, self.bot.formatException(ctx, error))
        elif isinstance(error, lng.LangSupportException):
            await self.bot.atSend(ctx, self.bot.languageProvider.formatException(lid, error))
        elif isinstance(error, gb.GreedyCommandError):
            await self.bot.atSend(ctx, self.bot.languageProvider.formatException(lid, error))
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send_help(ctx.command)
        elif isinstance(error, lng.LangException):
            await self.bot.atSend(ctx, f'{error}')
        else:
            if isinstance(error, MySQLdb.OperationalError):
                if error.args[0] == 2006:
                    await self.bot.atSendLang(ctx, "string_error_database_noanswer")
                    self.bot.dbm.reconnect()
                else:
                    await self.bot.atSendLang(ctx, "string_error_database_generic")
            elif isinstance(error, MySQLdb.IntegrityError):
                await self.bot.atSendLang(ctx, "string_error_database_dataviolation")
            else:
                await self.bot.atSendLang(ctx, "string_error_unhandled_exception")
            
            self.bot.logToDebugUser(f"Unhandled exception from command '{ctx.message.content}'. Error type is {type(error)}, error:\n{error}")
    
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
            