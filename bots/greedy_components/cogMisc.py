
import random
from discord.ext import commands

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs

import lang.lang as lng
import support.utils as utils

class GreedyGhostCog_Misc(gb.GreedyGhostCog):

    @commands.command(name='coin', help = 'Testa o Croce.')
    @gs.command_security(gs.IsUser)
    async def coin(self, ctx: commands.Context):
        moneta = ["string_heads", "string_tails"]
        await self.bot.atSendLang(ctx, random.choice(moneta))

    @commands.command(name = 'salut', brief='Lascia che il Greedy Ghost ti saluti.')
    @gs.command_security(gs.IsUser)
    async def salut(self, ctx: commands.Context):
        await self.bot.atSend(ctx, 'Shalom!')

    @commands.command(name = 'respect', brief='Pay respect.')
    @gs.command_security(gs.IsUser)
    async def respect(self, ctx: commands.Context):
        await self.bot.atSend(ctx, ':regional_indicator_f:')

    @commands.command(name = 'ping', brief='Fa sapere il ping del Bot')
    @gs.command_security(gs.IsUser)
    async def ping(self, ctx: commands.Context):
        await self.bot.atSend(ctx, f' Ping: {int(self.bot.latency * 1000)}ms')

    @commands.command(name = 'divina', aliases=['divinazione' , 'div'] , brief='Presagire il futuro con una domanda' , help = 'Inserire comando + domanda')
    @gs.command_security(gs.IsUser)
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

    # this command is not needed anymore and is here only in case the bot misses someone joining and we don't want to wait up to 1 day for the user maintenance task to catch up
    # remember: if we register a User that is not actually in a guild that the bot can see, the registration will be removed when the maintenance task runs
    @commands.command(brief='Registra un utente nel database')
    @gs.command_security(gs.IsAdminOrStoryteller)
    async def register(self, ctx: commands.Context, *args): 

        if len(args) == 0:
            raise self.bot.getBotExceptionLang(ctx, "help_gmadm_stname") # TODO own error string

        v, userid = await self.bot.validateDiscordMentionOrID(args[0])
        if not v:
            raise self.bot.getBotExceptionLang(ctx, "string_error_invalid_mention_or_id")

        iu, _ = self.bot.dbm.isUser(userid)
        if not iu:
            user = await self.bot.fetch_user(userid)
            self.bot.dbm.registerUser(userid, user.name, self.bot.config['BotOptions']['default_language'])
            await self.bot.atSendLang(ctx, "string_mgs_user_registered")
        else:
            await self.bot.atSendLang(ctx, "string_mgs_user_already_registered")