
import random
from discord.ext import commands

from greedy_components import greedyBase as gb

import lang.lang as lng
import support.utils as utils

class GreedyGhostCog_Misc(commands.Cog):
    def __init__(self, bot: gb.GreedyGhost):
        self.bot = bot

    @commands.command(name='coin', help = 'Testa o Croce.')
    async def coin(self, ctx: commands.Context):
        moneta = ["string_heads", "string_tails"]
        await self.bot.atSendLang(ctx, random.choice(moneta))

    @commands.command(brief='Lascia che il Greedy Ghost ti saluti.')
    async def salut(self, ctx: commands.Context):
        await self.bot.atSend(ctx, 'Shalom!')

    @commands.command(brief='Pay respect.')
    async def respect(self, ctx: commands.Context):
        await self.bot.atSend(ctx, ':regional_indicator_f:')

    @commands.command(brief='Fa sapere il ping del Bot')
    async def ping(self, ctx: commands.Context):
        await self.bot.atSend(ctx, f' Ping: {int(self.bot.latency * 1000)}ms')

    @commands.command(aliases=['divinazione' , 'div'] , brief='Presagire il futuro con una domanda' , help = 'Inserire comando + domanda')
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
