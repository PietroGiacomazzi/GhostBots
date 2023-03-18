from discord.ext import commands
from discord.ext.commands import context

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs
from greedy_components import greedyConverters as gc

import lang.lang as lng
import support.utils as utils
import support.security as sec
import support.ghostAlchemy as ga


class GreedyGhostCog_Alchemy(gb.GreedyGhostCog):
    def __init__(self, bot: gb.GreedyGhost):
        super().__init__(bot)

    @commands.command(name = 'sa', brief='sqlAlchemy tests')
    @commands.before_invoke(gs.command_security(sec.IsAdmin))
    async def sa(self, ctx: gb.GreedyContext): 
        session = ctx.getSession()

        await self.bot.atSendLang(ctx, "porcoddio")
        users = None

        users = list(self.bot.alchemyManager.getUsers(session))
        response = " ".join(map(lambda x: x.name, users))
        await self.bot.atSendLang(ctx, f"Utenti in sessione: {response}")

        await self.bot.atSendLang(ctx, f"Utente classmethod: { ga.User.getRecord(session, '419959747933110292')}")

        response = " ".join(map(lambda x: x.name, users))
        await self.bot.atSendLang(ctx, f"Utenti fuori sessione: {response}")

