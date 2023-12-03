import random, logging
from discord.ext import commands

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs
import support.security as sec

_log = logging.getLogger(__name__)

class GreedyGhostCog_Misc(gb.GreedyGhostCog):

    @commands.command(name='coin', help = 'Testa o Croce.')
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def coin(self, ctx: commands.Context):
        moneta = ["string_heads", "string_tails"]
        await self.bot.atSendLang(ctx, random.choice(moneta))

    @commands.command(name = 'salut', brief='Lascia che il Greedy Ghost ti saluti.')
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def salut(self, ctx: commands.Context):
        await self.bot.atSend(ctx, 'Shalom!')

    @commands.command(name = 'respect', brief='Pay respect.')
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def respect(self, ctx: commands.Context):
        await self.bot.atSend(ctx, ':regional_indicator_f:')

    @commands.command(name = 'ping', brief='Fa sapere il ping del Bot')
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def ping(self, ctx: commands.Context):
        await self.bot.atSend(ctx, f' Ping: {int(self.bot.latency * 1000)}ms')

    @commands.command(name = 'divina', aliases=['divinazione' , 'div'] , brief='Presagire il futuro con una domanda' , help = 'Inserire comando + domanda')
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def divina(self, ctx: commands.Context, *, question: str):
        responses=['Certamente.',
            'Sicuramente.' ,
            'Probabilmente si.' ,
            'Forse.' ,
            'Mi sa di no.' ,
            'Probabilmente no.' ,
            'Sicuramente no.',
            'Per come la vedo io, si.',
            'Non è scontato.',
            'Meglio chiedere a Rossellini.',
            'Le prospettive sono buone.',
            'Ci puoi contare.',
            'Difficile dare una risposta.',
            'Sarebbe meglio non risponderti adesso.',
            'Sarebbe uno spoiler troppo grosso.',
            'Non ci contare.',
            'I miei contatti mi dicono di no.'
            ]
        await self.bot.atSend(ctx, f'Domanda: {question}\n\nRisposta: {random.choice(responses)}')
