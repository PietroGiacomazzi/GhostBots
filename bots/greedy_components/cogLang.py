
from typing import AnyStr, Callable
from discord.ext import commands

from greedy_components import greedyBase as gb

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB

class GreedyGhostCog_Lang(commands.Cog):
    def __init__(self, bot: gb.GreedyGhost):
        self.bot = bot

    @commands.command(brief='Impostazioni di lingua', description = "Permette di cambiare impostazioni di lingua del bot")
    async def lang(self, ctx:commands.Context, *args):
        issuer = ctx.message.author.id
        if len(args) == 0:
            await self.bot.atSendLang(ctx, "string_your_lang_is", self.bot.getLID(ctx.message.author.id))
        elif len(args) == 1:
            _ = self.bot.dbm.getUser(issuer)
            self.bot.dbm.db.update("People", where='userid  = $userid', vars=dict(userid =issuer), langId = args[0])
            lid = args[0]
            await self.bot.atSendLang(ctx, "string_lang_updated_to", lid)
        else:
            raise self.bot.getBotExceptionLang(ctx, "string_invalid_number_of_parameters")
    
    @commands.command(name = 'translate', brief='Permette di aggiornare la traduzione di un tratto in una lingua' , help = "")
    async def translate(self, ctx: commands.Command, *args):
        language = None
        if len(args):
            vl, language = self.bot.dbm.isValidLanguage(args[0]) 
            if not vl:
                raise self.bot.getBotExceptionLang(ctx, "string_error_invalid_language_X", args[0])
        if len(args)>=2:
            vt, _ = self.bot.dbm.isValidTrait(args[1]) 
            if not vt:
                raise self.bot.getBotExceptionLang(ctx, "string_error_invalid_trait_X", args[1])

        if len(args) == 2: # consulto
            traits = self.bot.dbm.db.select("LangTrait", where = 'traitId = $traitId and langId = $langId', vars = dict(traitId=args[1], langId = args[0]))
            if len(traits):
                trait = traits[0]
                await self.bot.atSendLang(ctx, "string_msg_trait_X_in_Y_has_translation_Z1_Z2", args[1], language['langName'], trait['traitName'], trait['traitShort'])
            else:
                await self.bot.atSendLang(ctx, "string_msg_trait_X_not_translated_Y", args[1], language['langName'])
        elif len(args) >= 4: # update/inserimento
            traits = self.bot.dbm.db.select("LangTrait", where = 'traitId = $traitId and langId = $langId', vars = dict(traitId=args[1], langId = args[0]))
            if len(traits): # update
                trait = traits[0]
                u = self.bot.dbm.db.update("LangTrait", where = 'traitId = $traitId and langId = $langId', vars = dict(traitId=args[1], langId = args[0]), traitShort = args[2], traitName = args[3])
                if u == 1:
                    await self.bot.atSendLang(ctx, "string_msg_trait_X_in_Y_has_translation_Z1_Z2", args[1], language['langName'], args[3], args[2])
                else:
                    await self.bot.atSendLang(ctx, "string_error_update_wrong_X_rows_affected", u)
            else:
                self.bot.dbm.db.insert("LangTrait", langId = args[0], traitId=args[1], traitShort = args[2], traitName = args[3])
                await self.bot.atSendLang(ctx, "string_msg_trait_X_in_Y_has_translation_Z1_Z2", args[1], language['langName'], args[3], args[2])
        else:
            await self.bot.atSendLang(ctx, "string_help_translate")