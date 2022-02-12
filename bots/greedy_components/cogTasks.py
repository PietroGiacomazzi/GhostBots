
from discord.ext import commands, tasks
import discord

from greedy_components import greedyBase as gb

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB


class GreedyGhostCog_Tasks(commands.Cog): 
    def __init__(self, bot: gb.GreedyGhost):
        self.bot = bot
        self.userMaintenance.start()

    def cog_unload(self):
        self.userMaintenance.cancel()

    @tasks.loop(seconds=3600)
    async def userMaintenance(self):
        usersDict = {}
        for usr in self.bot.dbm.getUsers():
            usersDict[int(usr['userid'])] = (False, usr)
        
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.id in usersDict:
                    seen, _ = usersDict[member.id]
                    if not seen:
                        self.bot.dbm.updateUser(member.id, member.name)
                        seen = True
                        await self.bot.logToDebugUser(f"user maintenance: updated {member.name}")
                else:
                    self.bot.dbm.registerUser(member.id, member.name, self.bot.config['BotOptions']['default_language'])
                    await self.bot.logToDebugUser(f"user maintenance: registered {member.name}")
                    usersDict[member.id] = (True, None)
        
        for userid in usersDict:
            seen, usr = usersDict[userid]
            if not seen:
                self.bot.dbm.removeUser(userid, self.bot.user.id)
                await self.bot.logToDebugUser(f"user maintenance: removed {member.name}")
        
        await self.bot.logToDebugUser("user maintenance complete")

        
    @userMaintenance.before_loop
    async def before_printer(self):
        await self.bot.wait_until_ready()
