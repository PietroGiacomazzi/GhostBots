
from typing import AnyStr, Callable
from discord.ext import commands

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB

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
    async def pgmod(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            response = 'Azioni disponibili:\n\n' + '\n'.join(list(map(lambda k: f'{k} - {pgmod_help[k][1]}', pgmod_help)))
            await self.bot.atSend(ctx, response)

    @pgmod.command(name = 'create', brief = "Crea un personaggio", description = create_description)
    @gs.command_security(gs.genCanCreateCharactertoSomeone(target_user = 1))
    async def create(self, ctx : commands.Context, *args):
        if len(args) < 3:
            await self.bot.atSend(ctx, create_description)
            return

        chid = args[0].lower()
        v, owner = await self.bot.validateDiscordMentionOrID(args[1])
        if not v:
            raise gb.BotException("Menziona il proprietario del personaggio con @nome on con il suo discord ID")

        fullname = " ".join(list(args[2:]))
        
        self.bot.dbm.newCharacter(chid, fullname, owner)
        
        await self.bot.atSend(ctx, f'Il personaggio {fullname} è stato inserito!')

    @pgmod.command(name = 'link', brief = "Aggiunge un personaggio ad una cronaca", description = link_description)
    @gs.command_security(gs.genIsAdminOrChronicleStoryteller(target_chronicle = 1))
    async def link(self, ctx: commands.Context, *args):
        if len(args) != 2:
            await self.bot.atSend(ctx, link_description)
            return 
        
        charid = args[0].lower()
        character = self.bot.dbm.getCharacter(charid)
        
        chronid = args[1].lower()
        chronicle = self.bot.dbm.getChronicle(chronid)
        
        is_linked, _ = self.bot.dbm.isCharacterLinkedToChronicle(character['id'], chronid)
        if is_linked:
            await self.bot.atSend(ctx, f"C'è già un associazione tra {character['fullname']} e {chronicle['name']}")
        else:
            self.bot.dbm.db.insert("ChronicleCharacterRel", chronicle=chronid, playerchar=character['id'])
            await self.bot.atSend(ctx, f"{character['fullname']} ora gioca a {chronicle['name']}")


    @pgmod.command(name = 'unlink', brief = "Disassocia un personaggio da una cronaca", description = unlink_description)
    @gs.command_security(gs.genIsAdminOrChronicleStoryteller(target_chronicle = 1))
    async def unlink(self, ctx: commands.Context, *args):
        if len(args) != 2:
            await self.bot.atSend(ctx, unlink_description)
            return 
        
        # validation
        charid = args[0].lower()
        character = self.bot.dbm.getCharacter(charid)

        chronid = args[1].lower()
        chronicle = self.bot.dbm.getChronicle(chronid)
        
        is_linked, _ = self.bot.dbm.isCharacterLinkedToChronicle(character['id'], chronid)
        if is_linked:
            self.bot.dbm.db.delete("ChronicleCharacterRel", where = 'playerchar=$playerchar and chronicle=$chronicleid', vars=dict(chronicleid=chronid, playerchar=character['id']))
            await self.bot.atSend(ctx, f"{character['fullname']} ora non gioca più a  {chronicle['name']}")
        else:
            await self.bot.atSend(ctx, f"Non c\'è un\'associazione tra {character['fullname']} e {chronicle['name']}")

    @pgmod.command(name = 'addt', brief = "Aggiunge tratto ad un personaggio", description = addt_description)
    @gs.command_security(gs.genCanEditCharacter(target_character = 0))
    async def addt(self, ctx: commands.Context, *args):
        if len(args) < 3:
            await self.bot.atSend(ctx, addt_description)
            return 

        charid = args[0].lower()
        character = self.bot.dbm.getCharacter(charid)
        traitid = args[1].lower()

        # permission checks
        issuer = str(ctx.message.author.id)

        istrait, trait = self.bot.dbm.isValidTrait(traitid)
        if not istrait:
            raise gb.BotException(f"Il tratto {traitid} non esiste!")
        
        ptraits = self.bot.dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id'])).list()
        if len(ptraits):
            raise gb.BotException(f"{character['fullname']} ha già il tratto {trait['name']} ")
        
        ttype = self.bot.dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        if ttype['textbased']:
            textval = " ".join(args[2:])
            self.bot.dbm.db.insert("CharacterTrait", trait=traitid, playerchar=character['id'], cur_value = 0, max_value = 0, text_value = textval, pimp_max = 0)
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.TEXT_VALUE, textval, '', ctx.message.content)
            await self.bot.atSend(ctx, f"{character['fullname']} ora ha {trait['name']} {textval}")
        else:
            pimp = 6 if trait['traittype'] in ['fisico', 'sociale', 'mentale'] else 0
            self.bot.dbm.db.insert("CharacterTrait", trait=traitid, playerchar=character['id'], cur_value = args[2], max_value = args[2], text_value = "", pimp_max = pimp)
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.MAX_VALUE, args[2], '', ctx.message.content)
            await self.bot.atSend(ctx, f"{character['fullname']} ora ha {trait['name']} {args[2]}")

    @pgmod.command(name = 'modt', brief = "Modifica un tratto di un personaggio", description = modt_description)
    @gs.command_security(gs.genCanEditCharacter(target_character = 0))
    async def modt(self, ctx: commands.Context, *args):
        if len(args) < 3:
            await self.bot.atSend(ctx, modt_description)
            return 

        character = self.bot.dbm.getCharacter(args[0].lower())
        traitid = args[1].lower()

        # permission checks
        issuer = str(ctx.message.author.id)
        
        istrait, trait = self.bot.dbm.isValidTrait(traitid)
        if not istrait:
            raise gb.BotException(f"Il tratto {traitid} non esiste!")
        
        ptraits = self.bot.dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id'])).list()
        if not len(ptraits):
            raise gb.BotException(f"{character['fullname']} non ha il tratto {trait['name']} ")
        
        ttype = self.bot.dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        if ttype['textbased']:
            textval = " ".join(args[2:])
            self.bot.dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']), text_value = textval)
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.TEXT_VALUE, textval, ptraits[0]['text_value'], ctx.message.content)
            await self.bot.atSend(ctx, f"{character['fullname']} ora ha {trait['name']} {textval}")
        else:
            self.bot.dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']), cur_value = args[2], max_value = args[2])
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.MAX_VALUE, args[2], ptraits[0]['max_value'], ctx.message.content)
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.CUR_VALUE, args[2], ptraits[0]['cur_value'], ctx.message.content)
            await self.bot.atSend(ctx, f"{character['fullname']} ora ha {trait['name']} {args[2]}")
    
    
    @pgmod.command(name = 'rmt', brief = "Rimuovi un tratto ad un personaggio", description = rmt_description)
    @gs.command_security(gs.genCanEditCharacter(target_character = 0))
    async def rmt(self, ctx: commands.Context, *args):
        if len(args) < 2:
            await self.bot.atSend(ctx, rmt_description)
            return

        character = self.bot.dbm.getCharacter(args[0].lower())
        traitid = args[1].lower()

        # permission checks
        issuer = str(ctx.message.author.id)
        
        istrait, trait = self.bot.dbm.isValidTrait(traitid)
        if not istrait:
            raise gb.BotException(f"Il tratto {traitid} non esiste!")
        
        ptraits = self.bot.dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id'])).list()
        if not len(ptraits):
            raise gb.BotException(f"{character['fullname']} non ha il tratto {trait['name']} ")
        ttype = self.bot.dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        
        updated_rows = self.bot.dbm.db.delete("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']))
        if ttype['textbased']:
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.DELETE, "", ptraits[0]['text_value'], ctx.message.content)
        else:
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.DELETE, "", f"{ptraits[0]['cur_value']}/{ptraits[0]['max_value']}", ctx.message.content)
            
        if updated_rows > 0:
            await self.bot.atSend(ctx, f"Rimosso {trait['name']} da {character['fullname']} ({updated_rows})")
        else:
            await self.bot.atSend(ctx, f"Nessun tratto rimosso")

    @pgmod.command(name = 'reassign', brief = pgmod_help["reassign"][1], description = pgmod_help["reassign"][0])
    @gs.command_security(gs.genCanEditCharacter(target_character = 0))
    async def reassign(self, ctx: commands.Context, *args):
        if len(args) < 2:
            await self.bot.atSend(ctx, pgmod_help["reassign"][0])
            return
        
        charid = args[0].lower()
        character = self.bot.dbm.getCharacter(charid)
        
        v, owner = await self.bot.validateDiscordMentionOrID(args[1])
        if not v:
            raise gb.BotException("Menziona il proprietario del personaggio con @nome on con il suo discord ID")
        
        user =  self.bot.dbm.getUser(owner) 
        username = user['name']
        
        self.bot.dbm.reassignCharacter(charid, owner)
        
        await self.bot.atSendLang(ctx, "string_msg_character_reassigned_to_user", character["fullname"], username)
