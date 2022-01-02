
from typing import AnyStr, Callable
from discord.ext import commands

from greedy_components import greedyBase as gb

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB

create_description = "Argomenti: nome breve (senza spazi), @menzione al proprietario (oppure Discord ID), nome completo del personaggio (spazi ammessi)"
link_description = "Argomenti: nome breve del pg, nome breve della cronaca"
unlink_description = "Argomenti: nome breve del pg, nome breve della cronaca"
addt_description = "Argomenti: nome breve del pg, nome breve del tratto, valore"
modt_description = "Argomenti: nome breve del pg, nome breve del tratto, nuovo valore"
rmt_description = "Argomenti: nome breve del pg, nome breve del tratto"

pgmod_help = {
        "create": [create_description, "Crea un personaggio"],
        "addt": [addt_description, "Aggiunge tratto ad un personaggio"],
        "modt": [modt_description, "Modifica un tratto di un personaggio"],
        "rmt": [rmt_description, "Rimuovi un tratto ad un personaggio"],
        "link": [link_description, "Aggiunge un personaggio ad una cronaca"],
        "unlink": [unlink_description, "Disassocia un personaggio da una cronaca"]
        }

class GreedyGhostCog_PCMod(commands.Cog):
    def __init__(self, bot: gb.GreedyGhost):
        self.bot = bot

    @commands.group(brief='Gestione personaggi')
    async def pgmod(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            response = 'Azioni disponibili:\n\n' + '\n'.join(list(map(lambda k: f'{k} - {pgmod_help[k][1]}', pgmod_help)))
            await self.bot.atSend(ctx, response)

    @pgmod.command(brief = "Crea un personaggio", description = create_description)
    async def create(self, ctx : commands.Context, *args):
        if len(args) < 3:
            await self.bot.atSend(ctx, create_description)
            return

        chid = args[0].lower()
        v, owner = await self.bot.validateDiscordMentionOrID(args[1])
        if not v:
            raise gb.BotException("Menziona il proprietario del personaggio con @nome on con il suo discord ID")

        fullname = " ".join(list(args[2:]))

        # permission checks
        issuer = str(ctx.message.author.id)
        if issuer != owner: # chiunque può crearsi un pg, ma per crearlo a qualcun'altro serve essere ST/admin
            st, _ = self.bot.dbm.isStoryteller(issuer)
            ba, _ = self.bot.dbm.isBotAdmin(issuer)
            if not (st or ba):
                raise gb.BotException("Per creare un pg ad un altra persona è necessario essere Admin o Storyteller")
        
        t = self.bot.dbm.db.transaction()
        try:
            iu, _ = self.bot.dbm.isUser(owner)
            if not iu:
                user = await self.bot.fetch_user(owner)
                self.bot.dbm.registerUser(owner, user.name, self.bot.config['BotOptions']['default_language'])
            self.bot.dbm.newCharacter(chid, fullname, owner)
        except:
            t.rollback()
            raise
        else:
            t.commit()
        
        await self.bot.atSend(ctx, f'Il personaggio {fullname} è stato inserito!')

    @pgmod.command(brief = "Aggiunge un personaggio ad una cronaca", description = link_description)
    async def link(self, ctx: commands.Context, *args):
        if len(args) != 2:
            await self.bot.atSend(ctx, link_description)
            return 
        
        # validation
        charid = args[0].lower()
        isChar, character = self.bot.dbm.isValidCharacter(charid)
        if not isChar:
            raise gb.BotException(f"Il personaggio {charid} non esiste!")
        
        chronid = args[1].lower()
        vc, chronicle = self.bot.dbm.isValidChronicle(chronid)
        if not vc:
            raise gb.BotException(f"La cronaca {chronid} non esiste!") 

        # permission checks
        issuer = str(ctx.message.author.id)
        st, _ = self.bot.dbm.isChronicleStoryteller(issuer, chronicle['id'])
        ba, _ = self.bot.dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise gb.BotException("Per associare un pg ad una cronaca necessario essere Admin o Storyteller di quella cronaca")
        
        is_linked, _ = self.bot.dbm.isCharacterLinkedToChronicle(charid, chronid)
        if is_linked:
            await self.bot.atSend(ctx, f"C'è già un associazione tra {character['fullname']} e {chronicle['name']}")
        else:
            self.bot.dbm.db.insert("ChronicleCharacterRel", chronicle=chronid, playerchar=charid)
            await self.bot.atSend(ctx, f"{character['fullname']} ora gioca a {chronicle['name']}")


    @pgmod.command(brief = "Disassocia un personaggio da una cronaca", description = unlink_description)
    async def unlink(self, ctx: commands.Context, *args):
        if len(args) != 2:
            await self.bot.atSend(ctx, unlink_description)
            return 
        
        # validation
        charid = args[0].lower()
        isChar, character = self.bot.dbm.isValidCharacter(charid)
        if not isChar:
            raise gb.BotException(f"Il personaggio {charid} non esiste!")

        chronid = args[1].lower()
        vc, chronicle = self.bot.dbm.isValidChronicle(chronid)
        if not vc:
            raise gb.BotException(f"La cronaca {chronid} non esiste!")

        # permission checks
        issuer = str(ctx.message.author.id)
        st, _ = self.bot.dbm.isChronicleStoryteller(issuer, chronicle['id'])
        ba, _ = self.bot.dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise gb.BotException("Per rimuovere un pg da una cronaca necessario essere Admin o Storyteller di quella cronaca")
        
        is_linked, _ = self.bot.dbm.isCharacterLinkedToChronicle(charid, chronid)
        if is_linked:
            self.bot.dbm.db.delete("ChronicleCharacterRel", where = 'playerchar=$playerchar and chronicle=$chronicleid', vars=dict(chronicleid=chronid, playerchar=charid))
            await self.bot.atSend(ctx, f"{character['fullname']} ora non gioca più a  {chronicle['name']}")
        else:
            await self.bot.atSend(ctx, f"Non c\'è un\'associazione tra {character['fullname']} e {chronicle['name']}")


    def pgmodPermissionCheck_Character(self, issuer_id: str, character: object, channel_id: str) -> bool: # TODO: move to dbm and add optional exception parameter
        owner_id = character['owner']
        char_id = character['id']
        
        st, _ =  self.bot.dbm.isStorytellerForCharacter(issuer_id, char_id)
        ba, _ = self.bot.dbm.isBotAdmin(issuer_id)
        co = False
        if owner_id == issuer_id and not (st or ba):
            #1: unlinked
            cl, _ = self.bot.dbm.isCharacterLinked(char_id)
            #2 active session
            sa, _ = self.bot.dbm.isSessionActiveForCharacter(char_id, channel_id)
            co = co or (not cl) or sa            

        return (st or ba or co)
        
    def pgmodPermissionCheck_CharacterExc(self, issuer_id: str, character: object, channel_id: str) -> bool:
        pc = self.pgmodPermissionCheck_Character(issuer_id, character, channel_id)
        if not pc:
            raise gb.BotException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Admin o Storyteller")
        else:
            return pc


    @pgmod.command(brief = "Aggiunge tratto ad un personaggio", description = addt_description)
    async def addt(self, ctx: commands.Context, *args):
        if len(args) < 3:
            await self.bot.atSend(ctx, addt_description)
            return 

        charid = args[0].lower()
        traitid = args[1].lower()
        isChar, character = self.bot.dbm.isValidCharacter(charid)
        if not isChar:
            raise gb.BotException(f"Il personaggio {charid} non esiste!")

        # permission checks
        issuer = str(ctx.message.author.id)

        self.pgmodPermissionCheck_CharacterExc(issuer, character, ctx.channel.id)

        istrait, trait = self.bot.dbm.isValidTrait(traitid)
        if not istrait:
            raise gb.BotException(f"Il tratto {traitid} non esiste!")
        
        ptraits = self.bot.dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id'])).list()
        if len(ptraits):
            raise gb.BotException(f"{character['fullname']} ha già il tratto {trait['name']} ")
        
        ttype = self.bot.dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        if ttype['textbased']:
            textval = " ".join(args[2:])
            self.bot.dbm.db.insert("CharacterTrait", trait=traitid, playerchar=charid, cur_value = 0, max_value = 0, text_value = textval, pimp_max = 0)
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.TEXT_VALUE, textval, '', ctx.message.content)
            await self.bot.atSend(ctx, f"{character['fullname']} ora ha {trait['name']} {textval}")
        else:
            pimp = 6 if trait['traittype'] in ['fisico', 'sociale', 'mentale'] else 0
            self.bot.dbm.db.insert("CharacterTrait", trait=traitid, playerchar=charid, cur_value = args[2], max_value = args[2], text_value = "", pimp_max = pimp)
            self.bot.dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.MAX_VALUE, args[2], '', ctx.message.content)
            await self.bot.atSend(ctx, f"{character['fullname']} ora ha {trait['name']} {args[2]}")

    @pgmod.command(brief = "Modifica un tratto di un personaggio", description = modt_description)
    async def modt(self, ctx: commands.Context, *args):
        if len(args) < 3:
            await self.bot.atSend(ctx, modt_description)
            return 
        charid = args[0].lower()
        traitid = args[1].lower()
        isChar, character = self.bot.dbm.isValidCharacter(charid)
        if not isChar:
            raise gb.BotException(f"Il personaggio {charid} non esiste!")

        # permission checks
        issuer = str(ctx.message.author.id)
        
        self.pgmodPermissionCheck_CharacterExc(issuer, character, ctx.channel.id)

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
    
    
    @pgmod.command(brief = "Rimuovi un tratto ad un personaggio", description = rmt_description)
    async def rmt(self, ctx: commands.Context, *args):
        if len(args) < 2:
            await self.bot.atSend(ctx, rmt_description)
            return

        charid = args[0].lower()
        traitid = args[1].lower()
        isChar, character = self.bot.dbm.isValidCharacter(charid)
        if not isChar:
            raise gb.BotException(f"Il personaggio {charid} non esiste!")

        # permission checks
        issuer = str(ctx.message.author.id)
        
        self.pgmodPermissionCheck_CharacterExc(issuer, character, ctx.channel.id)

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

  