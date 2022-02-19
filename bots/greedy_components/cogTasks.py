
from discord.ext import commands, tasks
import discord

from greedy_components import greedyBase as gb

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB


class GreedyGhostCog_Tasks(gb.GreedyGhostCog): 
    def __init__(self, *args, **kwargs):
        super(GreedyGhostCog_Tasks, self).__init__(*args, **kwargs)
        self.userMaintenance.start()

    def cog_unload(self):
        self.userMaintenance.cancel()

    @tasks.loop(seconds=3600*24)
    async def userMaintenance(self):
        usersSeenDict = {}
        for usr in self.bot.dbm.getUsers():
            usersSeenDict[int(usr['userid'])] = False

        added = []
        removed = []
        
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.id in usersSeenDict:
                    if not usersSeenDict[member.id]:
                        self.bot.dbm.updateUser(member.id, member.name)
                else:
                    self.bot.dbm.registerUser(member.id, member.name, self.bot.config['BotOptions']['default_language'])
                    added.append(member.name)
                
                usersSeenDict[member.id] = True
        
        for userid in usersSeenDict:
            if not usersSeenDict[userid]:
                if self.bot.dbm.tryRemoveUser(userid, self.bot.user.id):
                    removed.append(str(userid))
        
        await self.bot.logToDebugUser(f'user maintenance complete: added {len(added)} users, removed {len(removed)}')
        
    @userMaintenance.before_loop
    async def before_printer(self):
        await self.bot.wait_until_ready()
