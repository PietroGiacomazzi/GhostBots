
from typing import AnyStr, Callable
from discord.ext import commands

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs
from greedy_components import greedyConverters as gc


import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB

class GreedyGhostCog_Lang(gb.GreedyGhostCog):

    @commands.command(name = 'lang', brief='Impostazioni di lingua', description = "Permette di cambiare impostazioni di lingua del bot")
    @commands.before_invoke(gs.command_security(gs.IsUser))
    async def lang(self, ctx:commands.Context, language: gc.LanguageConverter = None):
        issuer = ctx.message.author.id
        if not language:
            await self.bot.atSendLang(ctx, "string_your_lang_is", self.bot.getLID(ctx.message.author.id))
        else:
            langId = language['langId']
            _ = self.bot.dbm.validators.getValidateBotUser(issuer).get()
            self.bot.dbm.db.update("People", where='userid  = $userid', vars=dict(userid =issuer), langId = langId)
            lid = language['langId']
            await self.bot.atSendLang(ctx, "string_lang_updated_to", lid)
    
    @commands.command(name = 'translate', brief='Permette di aggiornare la traduzione di un tratto in una lingua' , help = "")
    @commands.before_invoke(gs.command_security(gs.IsAdminOrStoryteller))
    async def translate(self, ctx: commands.Command, language: gc.LanguageConverter, trait: gc.TraitConverter, traitlang: gc.GreedyShortIdConverter = None, *args):
        traitId = trait['id']
        langId = language['langId']

        #TODO: use getters for searching LangTrait

        if traitlang == None: # consulto
            traits = self.bot.dbm.db.select("LangTrait", where = 'traitId = $traitId and langId = $langId', vars = dict(traitId=traitId, langId = langId))
            if len(traits):
                trait = traits[0]
                await self.bot.atSendLang(ctx, "string_msg_trait_X_in_Y_has_translation_Z1_Z2", traitId, language['langName'], trait['traitName'], trait['traitShort'])
            else:
                await self.bot.atSendLang(ctx, "string_msg_trait_X_not_translated_Y", traitId, language['langName'])
        elif len(args) != 0: # update/inserimento
            traits = self.bot.dbm.db.select("LangTrait", where = 'traitId = $traitId and langId = $langId', vars = dict(traitId=traitId, langId = langId))
            tratiNameLang = " ".join(list(args))
            if len(traits): # update
                trait = traits[0]
                u = self.bot.dbm.db.update("LangTrait", where = 'traitId = $traitId and langId = $langId', vars = dict(traitId=traitId, langId = langId), traitShort = traitlang, traitName = tratiNameLang)
                if u == 1:
                    await self.bot.atSendLang(ctx, "string_msg_trait_X_in_Y_has_translation_Z1_Z2", traitId, language['langName'], tratiNameLang, traitlang)
                else:
                    await self.bot.atSendLang(ctx, "string_error_update_wrong_X_rows_affected", u)
            else:
                self.bot.dbm.db.insert("LangTrait", langId = langId, traitId=traitId, traitShort = traitlang, traitName = tratiNameLang)
                await self.bot.atSendLang(ctx, "string_msg_trait_X_in_Y_has_translation_Z1_Z2", traitId, language['langName'], tratiNameLang, traitlang)
        else:
            await self.bot.atSendLang(ctx, "string_help_translate")