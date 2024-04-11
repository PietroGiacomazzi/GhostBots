from discord.ext import commands
import logging

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs
from greedy_components import greedyConverters as gc

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB
import support.security as sec
import support.gamesystems as gms

_log = logging.getLogger(__name__)

create_description = "Argomenti: nome breve (senza spazi), @menzione al proprietario (oppure Discord ID), nome completo del personaggio (spazi ammessi)"
link_description = "Argomenti: nome breve del pg, nome breve della cronaca"
unlink_description = "Argomenti: nome breve del pg, nome breve della cronaca"
addt_description = "Argomenti: nome breve del pg, nome breve del tratto, valore"
modt_description = "Argomenti: nome breve del pg, nome breve del tratto, nuovo valore"
rmt_description = "Argomenti: nome breve del pg, nome breve del tratto"
reassign_description = "Argomenti: nome breve del pg, @menzione al nuovo proprietario (oppure Discord ID)"

pgmod_help = {
        "create": [create_description, "Crea un personaggio"],
        "addt": [addt_description, "Aggiunge tratto ad un personaggio"],
        "modt": [modt_description, "Modifica un tratto di un personaggio"],
        "rmt": [rmt_description, "Rimuovi un tratto ad un personaggio"],
        "link": [link_description, "Aggiunge un personaggio ad una cronaca"],
        "unlink": [unlink_description, "Disassocia un personaggio da una cronaca"],
        "reassign": [reassign_description, "Riassegna un personaggio ad un altro giocatore"]
        }

class GreedyGhostCog_PCMod(gb.GreedyGhostCog):

    @commands.group(brief='Gestione personaggi')
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def pgmod(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            response = utils.discord_text_format_mono('Azioni disponibili:\n\n' + '\n'.join(list(map(lambda k: f'{k} - {pgmod_help[k][1]}', pgmod_help))))
            await self.bot.atSend(ctx, response)

    @pgmod.command(name = 'create', brief = "Crea un personaggio", description = create_description)
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.OR(sec.IsStoryteller, sec.genIsSelf(optional_target_user = 3))))))
    async def create(self, ctx : commands.Context, character_id: gc.GreedyShortIdConverter, user: gc.RegisteredUserConverter, name, *args):
        fullname = " ".join(list([name]+list(args)))

        self.bot.dbm.newCharacter(character_id, fullname, user['userid'])
        await self.bot.atSend(ctx, f'Il personaggio {fullname} è stato inserito!')

    @pgmod.command(name = 'link', brief = "Aggiunge un personaggio ad una cronaca", description = link_description)
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.genIsChronicleStoryteller(target_chronicle = 3)))))
    async def link(self, ctx: commands.Context, character: gc.CharacterConverter, chronicle: gc.ChronicleConverter):
        is_linked, _ = self.bot.dbm.isCharacterLinkedToChronicle(character['id'], chronicle['id'])
        if is_linked:
            await self.bot.atSend(ctx, f"C'è già un'associazione tra {character['fullname']} e {chronicle['name']}")
        else:
            self.bot.dbm.db.insert("ChronicleCharacterRel", chronicle=chronicle['id'], playerchar=character['id'])
            await self.bot.atSend(ctx, f"{character['fullname']} ora gioca a {chronicle['name']}")

    @pgmod.command(name = 'unlink', brief = "Disassocia un personaggio da una cronaca", description = unlink_description)
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.genIsChronicleStoryteller(target_chronicle = 3)))))
    async def unlink(self, ctx: commands.Context, character: gc.CharacterConverter, chronicle: gc.ChronicleConverter):
        is_linked, _ = self.bot.dbm.isCharacterLinkedToChronicle(character['id'], chronicle['id'])
        if is_linked:
            self.bot.dbm.db.delete("ChronicleCharacterRel", where = 'playerchar=$playerchar and chronicle=$chronicleid', vars=dict(chronicleid=chronicle['id'], playerchar=character['id']))
            await self.bot.atSend(ctx, f"{character['fullname']} ora non gioca più a  {chronicle['name']}")
        else:
            await self.bot.atSend(ctx, f"Non c\'è un\'associazione tra {character['fullname']} e {chronicle['name']}")

    @pgmod.command(name = 'addt', brief = "Aggiunge tratto ad un personaggio", description = addt_description)
    @commands.before_invoke(gs.command_security(sec.canEditCharacter_BOT(target_character=2)))
    async def addt(self, ctx: gb.GreedyContext, character: gc.CharacterConverter, trait: gc.TraitConverter, value, *args):
        issuer = str(ctx.message.author.id)
        
        try:
            lid = ctx.getLID()
            ptrait = self.bot.dbm.getTrait_LangSafe(character['id'], trait['id'], lid)
            raise gb.BotException(f"{character['fullname']} ha già il tratto {ptrait['name']} ")
        except ghostDB.DBException:
            pass
        
        ttype = self.bot.dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        val = None
        if ttype['textbased']:
            val = " ".join([value]+list(args))
            self.bot.dbm.db.insert("CharacterTrait", trait=trait['id'], playerchar=character['id'], cur_value = 0, max_value = 0, text_value = val)
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.TEXT_VALUE, val, '', ctx.message.content)
        else:
            val = int(value)
            self.bot.dbm.db.insert("CharacterTrait", trait=trait['id'], playerchar=character['id'], cur_value = val, max_value = val, text_value = "")
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.MAX_VALUE, val, '', ctx.message.content)
        
        await self.bot.atSend(ctx, f"{character['fullname']} ora ha {trait['name']} {val}")

    @pgmod.command(name = 'modt', brief = "Modifica un tratto di un personaggio", description = modt_description)
    @commands.before_invoke(gs.command_security(sec.canEditCharacter_BOT(target_character=2)))
    async def modt(self, ctx: gb.GreedyContext, character: gc.CharacterConverter, trait: gc.TraitConverter, value, *args):
        issuer = str(ctx.message.author.id)
        
        chartrait = self.bot.dbm.getTrait_LangSafe(character['id'], trait['id'], ctx.getLID())
                
        ttype = self.bot.dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        val = None
        if ttype['textbased']:
            val = " ".join([value]+list(args))
            self.bot.dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']), text_value = val)
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.TEXT_VALUE, val, chartrait['text_value'], ctx.message.content)
        else:
            val = int(value)
            text_val = chartrait['text_value'][:val] if int(chartrait['trackertype']) == gms.TrackerType.HEALTH else chartrait['text_value'] # truncate health if shortening health tracker
            self.bot.dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']), cur_value = val, max_value = val, text_value = text_val)
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.MAX_VALUE, val, chartrait['max_value'], ctx.message.content)
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.CUR_VALUE, val, chartrait['cur_value'], ctx.message.content)
        
        await self.bot.atSend(ctx, f"{character['fullname']} ora ha {trait['name']} {val}")
    
    
    @pgmod.command(name = 'rmt', brief = "Rimuovi un tratto ad un personaggio", description = rmt_description)
    @commands.before_invoke(gs.command_security(sec.canEditCharacter_BOT(target_character=2)))
    async def rmt(self, ctx: gb.GreedyContext, character: gc.CharacterConverter, trait: gc.TraitConverter):
        issuer = str(ctx.message.author.id)
        chartrait = self.bot.dbm.getTrait_LangSafe(character['id'], trait['id'], ctx.getLID())
        ttype = self.bot.dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        
        updated_rows = self.bot.dbm.db.delete("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']))
        if ttype['textbased']:
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.DELETE, "", chartrait['text_value'], ctx.message.content)
        else:
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.DELETE, "", f"{chartrait['cur_value']}/{chartrait['max_value']}", ctx.message.content)
        if updated_rows > 0:
            await self.bot.atSend(ctx, f"Rimosso {trait['name']} da {character['fullname']} ({updated_rows})")
        else:
            await self.bot.atSend(ctx, f"Nessun tratto rimosso")

    @pgmod.command(name = 'reassign', brief = pgmod_help["reassign"][1], description = pgmod_help["reassign"][0])
    @commands.before_invoke(gs.command_security(sec.canEditCharacter_BOT(target_character=2)))
    async def reassign(self, ctx: commands.Context, character: gc.CharacterConverter, user: gc.RegisteredUserConverter):
        self.bot.dbm.reassignCharacter(character['id'], user['userid'])        
        await self.bot.atSendLang(ctx, "string_msg_character_reassigned_to_user", character["fullname"], user['name'])
