
from typing import AnyStr, Callable
from discord.ext import commands
import discord
import MySQLdb

from greedy_components import greedyBase as gb
from greedy_components import cogPCmgmt

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB

class GreedyGhostCog_Basic(commands.Cog):
    def __init__(self, bot: gb.GreedyGhost):
        self.bot = bot

    #executed once on bot boot
    #@bot.event
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.bot.user} is connected to the following guilds:\n')
        for guild in self.bot.guilds:
            print(f'{guild.name} (id: {guild.id})')
        #add self to user list
        iu, _ = self.bot.dbm.isUser(self.bot.user.id)
        if not iu:
            self.bot.dbm.registerUser(self.bot.user.id, self.bot.user.name, self.bot.config['BotOptions']['default_language'])
        # notify debug user that bot is online
        await self.bot.logToDebugUser("Bot is Online!")
    

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        issuer = ctx.message.author.id
        lid = self.bot.getLID(issuer)
        error = getattr(error, 'original', error)
        #ignored = (commands.CommandNotFound, )
        #if isinstance(error, ignored):
        #    print(error)
        if isinstance(error, commands.CommandNotFound):
            try:
                msgsplit = ctx.message.content.split(" ")
                msgsplit[0] = msgsplit[0][1:] # toglie prefisso
                charid = msgsplit[0]
                ic, _ = self.bot.dbm.isValidCharacter(charid)
                if ic:
                    pgmanage_cog = self.bot.get_cog(cogPCmgmt.GreedyGhostCog_PCmgmt.__name__)
                    if pgmanage_cog is not None:
                        await pgmanage_cog.pgmanage(ctx, *msgsplit)
                    else:
                        await self.bot.atSendLang(ctx, "string_error_wat")# TODO error cog not loaded
                else:
                    await self.bot.atSendLang(ctx, "string_error_wat")
                return
            except Exception as e:
                error = e
        if isinstance(error, gb.BotException):
            await self.bot.atSend(ctx, f'{error}')
        elif isinstance(error, ghostDB.DBException):
            await self.bot.atSend(ctx, self.bot.languageProvider.formatException(lid, error))
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
            #print("debug user:", int(config['Discord']['debuguser']))
            debug_user = await self.bot.fetch_user(int(self.bot.config['Discord']['debuguser']))
            error_details = self.bot.getStringForUser(ctx, "string_error_details", ctx.message.content, type(error), error) # TODO: This is actually getting the wrong language: language of the user, not the debug user
            if debug_user != '':
                await debug_user.send(error_details)
            else:
                print(error_details) # TODO logs
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        iu, _ = self.bot.dbm.isUser(member.id)
        if not iu:
            self.bot.dbm.registerUser(member.id, member.name, self.bot.config['BotOptions']['default_language'])

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        self.bot.dbm.tryRemoveUser(member.id, self.bot.user.id)

    @commands.Cog.listener()
    async def on_member_update(self, member_before: discord.Member, member_after: discord.Member):
        iu, _ = self.bot.dbm.isUser(member_after.id)
        if iu:
            self.bot.dbm.updateUser(member_after.id, member_after.name)