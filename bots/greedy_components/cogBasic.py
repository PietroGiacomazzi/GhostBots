
from discord.ext import commands

from greedy_components import greedyBase as gb

class GreedyGhostCog_Basic(gb.GreedyGhostCog):
    """ Does basic functionality for the bot """
   
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