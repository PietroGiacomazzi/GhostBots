from discord.ext import commands
import logging

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs
from greedy_components import greedyRoll as gr
from greedy_components import greedyConverters as gc
from support import gamesystems as gms

from greedy_components.cogRoller import roll_longdescription

_log = logging.getLogger(__name__)

class GreedyGhostCog_SysRoller(gb.GreedyGhostCog):

    async def execute_roll(self, ctx: commands.Context, handler: gr.RollHandler, args: list):
        parser = handler.rollParserCls()()
        setup = parser.parseRoll(ctx, args)
        setup.validate()
        rd = setup.roll()
        outputter = handler.rollOutputterCls()()
        response = outputter.output(rd, ctx)
        await self.bot.atSendLang(ctx, response)

    @commands.command(name='roll', aliases=['r', 'tira', 'lancia', 'rolla'], brief = 'Tira dadi', description = roll_longdescription) 
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def roll(self, ctx: commands.Context, *args):
        if len(args) == 0:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_x_what", "roll")+ " diomadonna") # xd

        gamesystem = self.bot.getGameSystemByChannel(ctx.channel.id)
        handler = gr.getHandler(gms.getGamesystem(gamesystem))()
        
        args_list = list(args)
        await self.execute_roll(ctx, handler, args_list)

    @commands.command(name='rollGS', aliases=['rgs'], brief = 'Tira dadi con un sistema specifico', description = roll_longdescription) 
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def roll_gamesystem(self, ctx: commands.Context, gamesystem: gc.GameSystemConverter, *args):
        if len(args) == 0:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_x_what", "roll")+ " diomadonna") # xd

        parser_class = gr.getParser(gms.getGamesystem(gamesystem))
        parser = parser_class()
        
        args_list = list(args)
        await self.execute_roll(ctx, parser, args_list)

