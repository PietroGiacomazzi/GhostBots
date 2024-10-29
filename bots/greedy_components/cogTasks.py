from discord.ext import commands, tasks
import logging, discord

from greedy_components import greedyBase as gb

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB

_log = logging.getLogger(__name__)

class GreedyGhostCog_Tasks(gb.GreedyGhostCog): 
    def __init__(self, *args, **kwargs):
        super(GreedyGhostCog_Tasks, self).__init__(*args, **kwargs)
        self.userMaintenance.start()

    def cog_unload(self):
        self.userMaintenance.cancel()

    @tasks.loop(seconds=3600*24)
    async def userMaintenance(self):
        _log.info("running user maintenance...")
        did_something = False

        # First off, verify that the guild table is correct

        guildSeenDict = {}
        for gld in self.bot.dbm.getGuilds():
            guildSeenDict[int(gld['guildid'])] = False
        
        added_guilds = []
        removed_guilds = []

        for guild in self.bot.guilds:
            if await self.bot.checkAndJoinGuild(guild):
                added_guilds.append(guild.name)
                did_something = True
            else:
                self.bot.dbm.updateGuildName(guild.id, guild.name)
            guildSeenDict[guild.id] = True
        
        for guildid in guildSeenDict:
            if not guildSeenDict[guildid]:
                self.bot.dbm.removeGuild(guildid)
                removed_guilds.append(guildid)
                did_something = True

        if (len(added_guilds) > 0 or len(removed_guilds)> 0):
            await self.bot.logToDebugUser(f'[user maintenance] Guilds: added {len(added_guilds)}, removed {len(removed_guilds)}')

        guild_map = self.bot.getGuildActivationMap()
        
        # Now check users. 

        # get registered users in the DB. 
        usersSeenDict = {}
        for usr in self.bot.dbm.getUsers(): 
            usersSeenDict[int(usr['userid'])] = False

        added = []
        removed = []
        
        # loop through all visible users. 
        for guild in self.bot.guilds:
            for member in guild.members:
                if self.bot.isMemberAllowedInBot(member, guild_map): # only mark as seen if the user is in an authorized guild
                    if member.id in usersSeenDict:
                        if not usersSeenDict[member.id]:
                            self.bot.dbm.updateUser(member.id, member.name)
                            #did_something = True # Updating a name is not really doing something
                    else:
                        self.bot.dbm.registerUser(member.id, member.name, self.bot.config['BotOptions']['default_language'])
                        added.append(member.name)
                        did_something = True
                    
                    usersSeenDict[member.id] = True
        
        for userid in usersSeenDict:
            if not usersSeenDict[userid]:
                if self.bot.user.id != userid and self.bot.dbm.tryRemoveUser(userid, self.bot.user.id):
                    removed.append(str(userid))
                    did_something = True
        
        if (len(added) > 0 or len(removed)> 0):
            await self.bot.logToDebugUser(f'[user maintenance] Users: added {len(added)}, removed {len(removed)}')
        
        if did_something:
            await self.bot.logToDebugUser(f'[user maintenance] Maintenance complete.')
        
        _log.info("user maintenance complete.")
        
    @userMaintenance.before_loop
    async def before_printer(self):
        await self.bot.wait_until_ready()
