
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

    @commands.command(brief='Registra un utente nel database')
    async def register(self, ctx: commands.Context, *args):
        issuer = str(ctx.message.author.id)

        userid = None
        if len(args) < 1:
            userid = issuer
        else:
            # only admins/storytellers can register other users
            st, _ =  self.bot.dbm.isStoryteller(issuer) # TODO make a permission checker object 
            ba, _ = self.bot.dbm.isBotAdmin(issuer)
            if st or ba:
                v, userid = await self.bot.validateDiscordMentionOrID(args[0])
                if not v:
                    raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_invalid_mention_or_id"))
            else:
                raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_permission_only_st_adm"))

        iu, _ = self.bot.dbm.isUser(userid)
        if not iu:
            user = await self.bot.fetch_user(userid)
            self.bot.dbm.registerUser(userid, user.name, self.bot.config['BotOptions']['default_language'])
            self.bot.atSendLang("string_mgs_user_registered")
        else:
            self.bot.atSendLang("string_mgs_user_already_registered")