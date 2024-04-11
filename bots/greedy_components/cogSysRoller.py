from discord.ext import commands
import logging

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs
from greedy_components import greedyRoll as gr
from greedy_components import greedyConverters as gc

from support import gamesystems as gms
import support.security as sec

from greedy_components.cogRoller import roll_longdescription

_log = logging.getLogger(__name__)

class GreedyGhostCog_SysRoller(gb.GreedyGhostCog):

    async def execute_roll(self, ctx: commands.Context, character, gamesystemid: str, args: list):
        handler = gr.getHandler(gms.getGamesystem(gamesystemid))()
        parser = handler.rollParserCls()(character)
        setup = parser.parseRoll(ctx, args)
        setup.validate()
        rd = setup.roll()
        outputter = handler.rollOutputterCls()()
        response = outputter.output(rd, ctx)
        await self.bot.atSendLang(ctx, response)

    @commands.command(name='roll', aliases=['r', 'tira', 'lancia', 'rolla'], brief = 'Tira dei dadi', description = roll_longdescription) 
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def roll(self, ctx: commands.Context, *args):
        if len(args) == 0:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_x_what", "roll")+ " diomadonna") # xd

        gamesystemid = self.bot.getGameSystemIdByChannel(ctx.channel.id)
        
        args_list = list(args)
        await self.execute_roll(ctx, None, gamesystemid, args_list)

    @commands.command(name='rollas', aliases=['ra'], brief = 'Tira dei dadi partendo da un personaggio', description = roll_longdescription) 
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.genCanViewCharacter(target_character=2)))))
    async def roll_as_character(self, ctx: commands.Context, character: gc.CharacterConverter, *args):
        if len(args) == 0:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_x_what", "roll")+ " diomadonna") # xd

        gamesystemid = self.bot.dbm.getGameSystemIdByCharacter(character, self.bot.getGameSystemIdByChannel(ctx.channel.id)) 
        
        args_list = list(args)
        await self.execute_roll(ctx, character, gamesystemid, args_list)

    @commands.command(name='rollgs', aliases=['rgs'], brief = 'Tira dadi con un sistema specifico', description = roll_longdescription) 
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def roll_gamesystem(self, ctx: commands.Context, gamesystemid: gc.GameSystemConverter, *args):
        if len(args) == 0:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_x_what", "roll")+ " diomadonna") # xd
        
        args_list = list(args)
        await self.execute_roll(ctx, None, gamesystemid, args_list)

