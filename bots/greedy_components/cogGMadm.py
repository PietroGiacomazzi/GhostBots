
from typing import AnyStr, Callable
from discord.ext import commands
from discord.ext.commands import context

from greedy_components import greedyBase as gb

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB


listChronicles_description = "Nessun argomento richiesto"
newChronicle_description = "Argomenti: <id> <nome completo> \n\nId non ammette spazi."
unlink_description = "Argomenti: nome breve del pg, nome breve della cronaca"
newTrait_description = "Argomenti: <id> <tipo> <tracker> <standard> <nome completo>\n\nInvocare il comando senza argomenti per ottenere più informazioni"
updt_description = "Argomenti: <vecchio_id> <nuovo_id> <tipo> <tracker> <standard> <nome completo>\n\nInvocare il comando senza argomenti per ottenere più informazioni"
#delet_description = "Argomenti: nome breve del pg, nome breve del tratto"
link_description = "Argomenti: <id cronaca>,  [<@menzione storyteller/Discord ID>] (se diverso da se stessi)" # TODO help_gmadm_stlink
unlink_description = "Argomenti: <id cronaca>, [<@menzione storyteller/Discord ID>] (se diverso da se stessi)" #TODO help_gmadm_stunlink
name_description = "Argomenti: <@menzione utente/Discord ID>" # TODO help_gmadm_stname
unname_description = "Argomenti: <@menzione utente/Discord ID>" # TODO help_gmadm_stunname

gmadm_help = {
        "listChronicles": [listChronicles_description, "Elenca le cronache"],
        "newChronicle": [newChronicle_description, "Crea una nuova cronaca associata allo ST che invoca il comando"],
        "newTrait": [newTrait_description, "Crea nuovo tratto"],
        "updt": [updt_description, "Modifica un tratto"],
        #"delet": [delet_description, "Cancella un tratto (non implementato)"], #non implementato
        "link": [link_description, "Associa uno storyteller ad una cronaca"],
        "unlink": [unlink_description, "Disassocia uno storyteller da una cronaca"],
        "name": [name_description, "Nomina storyteller"],
        "unname": [unname_description, "De-nomina storyteller"]
        # todo: lista storyteller
        # todo: dissociazioni varie
        }

query_addTraitToPCs = """
        insert into CharacterTrait
            select t.id as trait, 
            pc.id as playerchar, 
            0 as cur_value, 
            0 as max_value, 
            "" as text_value,
            case 
            WHEN t.trackertype = 0 and (t.traittype ='fisico' or t.traittype = 'sociale' or t.traittype='mentale') THEN 6
            else 0
            end
            as pimp_max
            from Trait t, PlayerCharacter pc
            where t.standard = true
            and t.id = $traitid;
        """

query_addTraitToPCs_safe = """
    insert into CharacterTrait
        select t.id as trait, 
        pc.id as playerchar, 
        0 as cur_value, 
        0 as max_value, 
        "" as text_value,
        case 
        WHEN t.trackertype = 0 and (t.traittype ='fisico' or t.traittype = 'sociale' or t.traittype='mentale') THEN 6
        else 0
        end
        as pimp_max
        from Trait t, PlayerCharacter pc
        where t.standard = true
        and t.id = $traitid
        and not exists (
            select trait
            from CharacterTrait ct
            where ct.trait = $traitid and ct.playerchar = pc.id
        );
    """

query_addTraitLangs = """
    insert into LangTrait select l.langId as langId, t.id as traitId, $traitid as traitShort, $traitname as traitName from Trait t join Languages l where t.id = $traitid;
"""

class GreedyGhostCog_GMadm(commands.Cog):
    def __init__(self, bot: gb.GreedyGhost):
        self.bot = bot
        
    @commands.group(brief='Gestione personaggi')
    async def gmadm(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            response = 'Azioni disponibili:\n\n' + '\n'.join(list(map(lambda k: f'{k} - {gmadm_help[k][1]}', gmadm_help)))
            await self.bot.atSend(ctx, response)

    @gmadm.command(brief = "Elenca le cronache", description = listChronicles_description)
    async def listChronicles(self, ctx: commands.Context, *args):
        if len(args) != 0:
            await self.bot.atSend(ctx, listChronicles_description)
            return 

        # permission checks
        issuer = str(ctx.message.author.id)
        #st, _ = dbm.isStoryteller(issuer)
        #ba, _ = dbm.isBotAdmin(issuer)
        #if not (st or ba):
        #    raise gb.BotException("Per creare una cronaca è necessario essere Storyteller")

        query = """
    SELECT cr.id as cid, cr.name as cname, p.name as pname
    FROM Chronicle cr
    JOIN StoryTellerChronicleRel stcr on (cr.id = stcr.chronicle)
    JOIN People p on (stcr.storyteller = p.userid)
"""
        results = self.bot.dbm.db.query(query)
        if len(results) == 0:
            await self.bot.atSend(ctx, "Nessuna cronaca trovata!")
            return

        chronicles = {}
        crst = {}
        for c in results:
            chronicles[c['cid']] = c['cname']
            if not c['cid'] in crst:
                crst[c['cid']] = []
            crst[c['cid']].append(c['pname'])

        await self.bot.atSend(ctx, "Cronache:\n" + "\n".join(list(map(lambda x: f"**{chronicles[x]}** ({x}) (storyteller: {', '.join(crst[x])})", chronicles))))

    @gmadm.command(brief = "Crea una nuova cronaca associata allo ST che invoca il comando", description = newChronicle_description)
    async def newChronicle(self, ctx: commands.Context, *args):
        if len(args) < 2:
            self.bot.atSend(newChronicle_description)
            return 

        shortname = args[0].lower()
        fullname = " ".join(list(args[1:])) # squish

        # permission checks
        issuer = str(ctx.message.author.id)
        st, _ = self.bot.dbm.isStoryteller(issuer)
        # no botadmin perchè non è necessariente anche uno storyteller e dovrei fare n check in più e non ho voglia
        if not (st):
            raise gb.BotException("Per creare una cronaca è necessario essere Storyteller")

        # todo existence
        t = self.bot.dbm.db.transaction()
        try:
            self.bot.dbm.db.insert("Chronicle", id=shortname, name = fullname)
            self.bot.dbm.db.insert("StoryTellerChronicleRel", storyteller=issuer, chronicle=shortname)
        except:
            t.rollback()
            raise
        else:
            t.commit()
            issuer_user = await self.bot.fetch_user(issuer)
        
        await self.bot.atSend(ctx, f"Cronaca {fullname} inserita ed associata a {issuer_user}")

    @gmadm.command(brief = "Crea nuovo tratto", description = newTrait_description)
    async def newTrait(self, ctx: commands.Context, *args):
        if len(args) < 5:
            helptext = "Argomenti: <id> <tipo> <tracker> <standard> <nome completo>\n\n"
            helptext += "Gli id non ammettono spazi.\n\n"
            helptext += "<standard> ammette [y, s, 1] per Sì e [n, 0] per No\n\n"
            ttypes = self.bot.dbm.db.select('TraitType', what = "id, name")
            ttypesl = ttypes.list()
            helptext += "Tipi di tratto: \n"
            helptext += "\n".join(list(map(lambda x : f"\t**{x['id']}**: {x['name']}", ttypesl)))
            #helptext += "\n".join(list(map(lambda x : ", ".join(list(map(lambda y: y+": "+str(x[y]), x.keys()))), ttypesl)))
            helptext += """\n\nTipi di tracker:
        **0**: Nessun tracker (Elementi normali di scheda)
        **1**: Punti con massimo (Volontà, Sangue...)
        **2**: Danni (salute...)
        **3**: Punti senza massimo (esperienza...)
    """
            await self.bot.atSend(ctx, helptext)
            return
        
        # permission checks
        issuer = ctx.message.author.id
        st, _ = self.bot.dbm.isStoryteller(issuer)
        ba, _ = self.bot.dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise gb.BotException("Per creare un tratto è necessario essere Admin o Storyteller")
        
        traitid = args[0].lower()
        istrait, trait = self.bot.dbm.isValidTrait(traitid)
        if istrait:
            raise gb.BotException(f"Il tratto {traitid} esiste già!")

        if not utils.validateTraitName(traitid):
            raise gb.BotException(f"'{traitid}' non è un id valido!")

        traittypeid = args[1].lower()
        istraittype, traittype = self.bot.dbm.isValidTraitType(traittypeid)
        if not istraittype:
            raise gb.BotException(f"Il tipo di tratto {traittypeid} non esiste!")

        if not args[2].isdigit():
            raise gb.BotException(f"{args[2]} non è un intero >= 0!")
        tracktype = int(args[2])
        if not tracktype in [0, 1, 2, 3]: # TODO dehardcode
            raise gb.BotException(f"{tracktype} non è tracker valido!")

        stdarg = args[3].lower()
        std = stdarg in ['y', 's', '1']
        if not std and not stdarg in ['n', '0']:
            raise gb.BotException(f"{stdarg} non è un'opzione valida")
        
        traitname = " ".join(args[4:])

        response = ""
        t = self.bot.dbm.db.transaction()
        try:
            self.bot.dbm.db.insert("Trait", id = traitid, name = traitname, traittype = traittypeid, trackertype = tracktype, standard = std, ordering = 1.0)
            # we insert it in all available languages and we assume that it will be translated later:
            # better have it in the wrong language than not having it at all
            self.bot.dbm.db.query(query_addTraitLangs, vars = dict(traitid=traitid, traitname=traitname))
            response = f'Il tratto {traitname} è stato inserito'
            if std:
                self.bot.dbm.db.query(query_addTraitToPCs, vars = dict(traitid=traitid))
                response +=  f'\nIl nuovo talento standard {traitname} è stato assegnato ai personaggi!'
        except:
            t.rollback()
            raise
        else:
            t.commit()

        await self.bot.atSend(ctx, response)

    @gmadm.command(brief = "Modifica un tratto", description = updt_description)
    async def updt(self, ctx: commands.Context, *args):    
        issuer = ctx.message.author.id
        if len(args) < 6:
            helptext = "Argomenti: <vecchio_id> <nuovo_id> <tipo> <tracker> <standard> <nome completo>\n\n"
            helptext += "Gli id non ammettono spazi.\n\n"
            helptext += "<standard> ammette [y, s, 1] per Sì e [n, 0] per No\n\n"
            ttypes = self.bot.dbm.db.select('TraitType', what = "id, name")
            ttypesl = ttypes.list()
            helptext += "Tipi di tratto: \n"
            helptext += "\n".join(list(map(lambda x : f"\t**{x['id']}**: {x['name']}", ttypesl)))
            #helptext += "\n".join(list(map(lambda x : ", ".join(list(map(lambda y: y+": "+str(x[y]), x.keys()))), ttypesl)))
            helptext += """\n\nTipi di tracker:
        **0**: Nessun tracker (Elementi normali di scheda)
        **1**: Punti con massimo (Volontà, Sangue...)
        **2**: Danni (salute...)
        **3**: Punti senza massimo (esperienza...)
    """
            await self.bot.atSend(ctx, helptext)
            return
        
        # permission checks
        st, _ = self.bot.dbm.isStoryteller(issuer)
        ba, _ = self.bot.dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise gb.BotException("Per modificare un tratto è necessario essere Admin o Storyteller")

        old_traitid = args[0].lower()
        istrait, old_trait = self.bot.dbm.isValidTrait(old_traitid)
        if not istrait:
            raise gb.BotException(f"Il tratto {old_traitid} non esiste!")
        
        new_traitid = args[1].lower()
        istrait, new_trait = self.bot.dbm.isValidTrait(new_traitid)
        if istrait and (old_traitid!=new_traitid):
            raise gb.BotException(f"Il tratto {new_traitid} esiste già!")

        if not utils.validateTraitName(new_traitid):
            raise gb.BotException(f"'{new_traitid}' non è un id valido!")

        traittypeid = args[2].lower()
        istraittype, traittype = self.bot.dbm.isValidTraitType(traittypeid)
        if not istraittype:
            raise gb.BotException(f"Il tipo di tratto {traittypeid} non esiste!")

        if not args[3].isdigit():
            raise gb.BotException(f"{args[2]} non è un intero >= 0!")
        tracktype = int(args[3])
        if not tracktype in [0, 1, 2, 3]: # todo dehardcode
            raise gb.BotException(f"{tracktype} non è tracker valido!")

        stdarg = args[4].lower()
        std = stdarg in ['y', 's', '1']
        if not std and not stdarg in ['n', '0']:
            raise gb.BotException(f"{stdarg} non è un'opzione valida")

        traitname = " ".join(args[5:])
        
        response = f'Il tratto {traitname} è stato aggiornato'
        t = self.bot.dbm.db.transaction()
        try:
            self.bot.dbm.db.update("Trait", where= 'id = $oldid' , vars=dict(oldid = old_traitid), id = new_traitid, name = traitname, traittype = traittypeid, trackertype = tracktype, standard = std, ordering = 1.0)
            # now we update the language description, but only of the current language
            self.bot.dbm.db.update("LangTrait", where= 'traitId = $traitid and langId = $lid' , vars=dict(traitid=new_traitid, lid = self.bot.getLID(issuer)), traitName = traitname)
            if std and not old_trait['standard']:
                self.bot.dbm.db.query(query_addTraitToPCs_safe, vars = dict(traitid=new_traitid))
                response +=  f'\nIl nuovo talento standard {traitname} è stato assegnato ai personaggi!'
            elif not std and old_trait['standard']:
                self.bot.dbm.db.query("""
    delete from CharacterTrait
    where trait = $traitid and max_value = 0 and cur_value = 0 and text_value = '';
    """, vars = dict(traitid=new_traitid))
                response += f'\nIl talento {traitname} è stato rimosso dai personaggi che non avevano pallini'
        except:
            t.rollback()
            raise
        else:
            t.commit()

        await self.bot.atSend(ctx, response)

    @gmadm.command(brief = "Associa uno storyteller ad una cronaca", description = link_description)
    async def link(self, ctx: commands.Context, *args):
        issuer = str(ctx.message.author.id)
        #lid = getLanguage(issuer, dbm)

        if len(args) == 0 or len(args) > 2:
            await self.bot.atSendLang(ctx, "help_gmadm_stlink")
            return 
        
        # validation
        chronid = args[0].lower()
        vc, _ = self.bot.dbm.isValidChronicle(chronid)
        if not vc:
            raise gb.BotException(f"La cronaca {chronid} non esiste!")

        # permission checks
        st, _ = self.bot.dbm.isChronicleStoryteller(issuer, chronid)
        ba, _ = self.bot.dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise gb.BotException("Per collegare Storyteller e cronaca è necessario essere Admin o Storyteller di quella cronaca")

        target_st = None
        if len(args) == 1:
            target_st = issuer
        else:
            vt, target_st = await self.bot.validateDiscordMentionOrID(args[1])
            if not vt:
                raise gb.BotException(f"Menziona lo storyteller con @ o inserisci il suo Discord ID") 
        
        t_st, _ = self.bot.dbm.isStoryteller(target_st)
        if not t_st:
            raise gb.BotException(f"L'utente selezionato non è uno storyteller") 
        t_stc, _ = self.bot.dbm.isChronicleStoryteller(target_st, chronid)
        if t_stc:
            raise gb.BotException(f"L'utente selezionato è già Storyteller per {chronid}")  

        # link
        self.bot.dbm.db.insert("StoryTellerChronicleRel", storyteller=target_st, chronicle=chronid)
        await self.bot.atSend(ctx, f"Cronaca associata")

    @gmadm.command(brief = "Disassocia uno storyteller da una cronaca", description = unlink_description)
    async def unlink(self, ctx: context.Context, *args):
        issuer = str(ctx.message.author.id)
        #lid = getLanguage(issuer, dbm)

        if len(args) == 0 or len(args) > 2:
            await self.bot.atSendLang(ctx, "help_gmadm_stunlink")
            return 
        
        # validation
        chronid = args[0].lower()
        vc, _ = self.bot.dbm.isValidChronicle(chronid)
        if not vc:
            raise gb.BotException(f"La cronaca {chronid} non esiste!")

        target_st = None
        if len(args) == 1:
            target_st = issuer
        else:
            vt, target_st = await self.bot.validateDiscordMentionOrID(args[1])
            if not vt:
                raise gb.BotException(f"Menziona lo storyteller con @ o inserisci il suo Discord ID") 

        # permission checks
        ba, _ = self.bot.dbm.isBotAdmin(issuer)
        #st, _ = dbm.isChronicleStoryteller(issuer, chronid)
        st = issuer == target_st
        if not (st or ba):
            raise gb.BotException("Gli storyteller possono solo sganciarsi dalle proprie cronache, altrimenti è necessario essere admin")

        t_st, _ = self.bot.dbm.isStoryteller(target_st)
        if not t_st:
            raise gb.BotException(f"L'utente selezionato non è uno storyteller") 
        
        t_stc, _ = self.bot.dbm.isChronicleStoryteller(target_st, chronid)
        if not t_stc:
            raise gb.BotException(f"L'utente selezionato non è Storyteller per {chronid}")  

        # link
        n = self.bot.dbm.db.delete('StoryTellerChronicleRel', where='storyteller=$storyteller and chronicle=$chronicle', vars=dict(storyteller=target_st, chronicle=chronid))
        if n:
            await self.bot.atSend(ctx, f"Cronaca disassociata")
        else:
            await self.bot.atSend(ctx, f"Nessuna cronaca da disassociare")

    @gmadm.command(brief = "Nomina storyteller", description = name_description)
    async def name(self, ctx: commands.Context, *args):
        issuer = str(ctx.message.author.id)
        #lid = getLanguage(issuer, dbm)

        if len(args) != 1:
            await self.bot.atSendLang(ctx, "help_gmadm_stname")
            return

        vt, target_st = await self.bot.validateDiscordMentionOrID(args[0])
        if not vt:
            raise gb.BotException(f"Menziona l'utente con @ o inserisci il suo Discord ID") 

        # permission checks
        ba, _ = self.bot.dbm.isBotAdmin(issuer)

        if not ba:
            raise gb.BotException("Solo gli admin possono nominare gli storyteller")

        t_st, _ = self.bot.dbm.isStoryteller(target_st)
        if t_st:
            raise gb.BotException(f"L'utente selezionato è già uno storyteller")
        
        usr = self.bot.dbm.getUser(target_st)
        name = usr['name']
        
        self.bot.dbm.db.insert("Storyteller",  userid=target_st)
        await self.bot.atSend(ctx, f"{name} ora è Storyteller")
        
    @gmadm.command(brief = "De-nomina storyteller", description = unname_description)
    async def unname(self, ctx: commands.Context, *args):
        issuer = str(ctx.message.author.id)

        if len(args) != 1:
            await self.bot.atSendLang(ctx, "help_gmadm_stunname")
            return 

        vt, target_st = await self.bot.validateDiscordMentionOrID(args[0])
        if not vt:
            raise gb.BotException(f"Menziona l'utente con @ o inserisci il suo Discord ID") 

        # permission checks
        ba, _ = self.bot.dbm.isBotAdmin(issuer)

        if not ba:
            raise gb.BotException("Solo gli admin possono de-nominare gli storyteller")

        usr = self.bot.dbm.getUser(target_st)      
        name = usr['name']

        t_st, _ = self.bot.dbm.isStoryteller(target_st)
        if not t_st:
            raise gb.BotException(f"L'utente selezionato non è uno storyteller")
        
        n = self.bot.dbm.unnameStoryTeller(target_st)
        if n:
            await self.bot.atSend(ctx, f"{name} non è più Storyteller")
        else:
            await self.bot.atSend(ctx, f"Nessuna modifica fatta")
        

