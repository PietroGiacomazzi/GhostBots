from discord.ext import commands
from discord.ext.commands import context
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

GAMESYSTEMS_CMD = 'gamesystems'
CHANNEL_GAMESYSTEM_CMD = 'channelGS'
CHRONICLE_GAMESYSTEM_CMD = 'chronicleGS'

#
newTrait_description = """Argomenti: <id> <tipo> <tracker> <standard> <nome completo>

<id> non ammette spazi, + e -.
<tipo> ammette un tipo di tracker valido, usare .gmadm traittypes per avere una lista
<tracker> ammette un numero tra i seguenti:
    0: Nessun tracker (Elementi normali di scheda)
    1: Punti con massimo (Volontà, Sangue...)
    2: Danni (salute...)
    3: Punti senza massimo (esperienza...)
<standard> ammette [y, s, 1] per Sì e [n, 0] per No
<nome completo> ammette spazi
"""

listChronicles_description = "Nessun argomento richiesto"
newChronicle_description = "Argomenti: <id> <sistema di gioco> <nome completo> \n\nId non ammette spazi."
unlink_description = "Argomenti: nome breve del pg, nome breve della cronaca"
updt_description = "Argomenti: <vecchio_id> <nuovo_id> <tipo> <tracker> <standard> <nome completo>\n\nInvocare il comando senza argomenti per ottenere più informazioni"
#delet_description = "Argomenti: nome breve del pg, nome breve del tratto"
link_description = "Argomenti: <id cronaca>,  [<@menzione storyteller/Discord ID>] (se diverso da se stessi)" # TODO help_gmadm_stlink
unlink_description = "Argomenti: <id cronaca>, [<@menzione storyteller/Discord ID>] (se diverso da se stessi)" #TODO help_gmadm_stunlink
name_description = "Argomenti: <@menzione utente/Discord ID>" # TODO help_gmadm_stname
unname_description = "Argomenti: <@menzione utente/Discord ID>" # TODO help_gmadm_stunname
traittypes_description = "Nessun argomento richiesto"
GAMESYSTEMS_description = "Nessun argomento richiesto"
CHANNEL_GAMESYSTEM_description = f'Argomenti: [<gamesystem>] (opzionale)\n\n puoi usare .gmadm {GAMESYSTEMS_CMD} per visualizzare i sistemi di gioco disponibili'
CHRONICLE_GAMESYSTEM_description = f'Argomenti: <id cronaca> [<gamesystem>] (opzionale)\n\n puoi usare .gmadm {GAMESYSTEMS_CMD} per visualizzare i sistemi di gioco disponibili'

gmadm_help = {
        "listChronicles": [listChronicles_description, "Elenca le cronache"],
        "newChronicle": [newChronicle_description, "Crea una nuova cronaca associata allo ST che invoca il comando"],
        "newTrait": [newTrait_description, "Crea nuovo tratto"],
        "updt": [updt_description, "Modifica un tratto"],
        #"delet": [delet_description, "Cancella un tratto (non implementato)"], #non implementato
        "link": [link_description, "Associa uno storyteller ad una cronaca"],
        "unlink": [unlink_description, "Disassocia uno storyteller da una cronaca"],
        "name": [name_description, "Nomina storyteller"],
        "unname": [unname_description, "De-nomina storyteller"],
        "traittypes": [traittypes_description, "Elenca i tipi di tratto"],
        GAMESYSTEMS_CMD: [GAMESYSTEMS_description, "Elenca i sistemi di tiro disponibili"],        
        CHANNEL_GAMESYSTEM_CMD: [CHANNEL_GAMESYSTEM_description, "Imposta o consulta il sistema di gioco per questo canale"],
        CHRONICLE_GAMESYSTEM_CMD: [CHRONICLE_GAMESYSTEM_description, "Imposta o consulta il sistema di gioco per la cronaca specificata"]
        # todo: lista storyteller
        # todo: dissociazioni varie
        }

query_addTraitToPCs = """
        insert into CharacterTrait
            select t.id as trait, 
            pc.id as playerchar, 
            0 as cur_value, 
            0 as max_value, 
            "" as text_value
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
        "" as text_value
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
    insert into LangTrait 
        select l.langId as langId, t.id as traitId, $traitid as traitShort, $traitname as traitName 
        from Trait t join Languages l 
        where t.id = $traitid;
"""

class GreedyGhostCog_GMadm(gb.GreedyGhostCog):
        
    @commands.group(brief='Gestione sistema di gioco')
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def gmadm(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            response = utils.discord_text_format_mono('Azioni disponibili:\n\n' + '\n'.join(list(map(lambda k: f'{k} - {gmadm_help[k][1]}', gmadm_help))))
            await self.bot.atSend(ctx, response)

    @gmadm.command(name = 'listChronicles', brief = gmadm_help['listChronicles'][1], description = listChronicles_description)
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def listChronicles(self, ctx: commands.Context):

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

    @gmadm.command(name = 'newChronicle', brief = gmadm_help['newChronicle'][1], description = newChronicle_description)
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def newChronicle(self, ctx: commands.Context, shortname: gc.GreedyShortIdConverter, gamesystem: gc.GameSystemConverter, *args):
        if len(args) == 0:
            self.bot.atSend(ctx, newChronicle_description)
            return 

        fullname = " ".join(list(args)) # squish

        issuer = str(ctx.message.author.id)

        # todo existence
        t = self.bot.dbm.db.transaction()
        try:
            self.bot.dbm.db.insert("Chronicle", id=shortname, name = fullname, gamesystemid = gamesystem)
            self.bot.dbm.db.insert("StoryTellerChronicleRel", storyteller=issuer, chronicle=shortname)
        except:
            t.rollback()
            raise
        else:
            t.commit()
            issuer_user = await self.bot.fetch_user(issuer)
        
        await self.bot.atSend(ctx, f"Cronaca {fullname} inserita ed associata a {issuer_user}")

    @gmadm.command(name = 'newTrait', brief = gmadm_help['newTrait'][1], description = newTrait_description)
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def newTrait(self, ctx: commands.Context, traitid: gc.GreedyShortIdConverter, traittype: gc.TraitTypeConverter, tracktype: gc.TrackerTypeConverter, std: gc.NoYesConverter, *args):
        if len(args) == 0:
            await self.bot.atSend(ctx, newTrait_description)
            return
                
        istrait, _ = self.bot.dbm.validators.getValidateTrait(traitid).validate()
        if istrait:
            raise gb.BotException(f"Il tratto {traitid} esiste già!")
        
        traittypeid = traittype['id']

        traitname = " ".join(args)

        response = ""
        t = self.bot.dbm.db.transaction()
        try:
            self.bot.dbm.db.insert("Trait", id = traitid, name = traitname, traittype = traittypeid, trackertype = tracktype, standard = std, ordering = 1.0)
            # we insert it in all available languages and we assume that it will be translated later:
            # better have it in the wrong language than not having it at all
            self.bot.dbm.db.query(query_addTraitLangs, vars = dict(traitid=traitid, traitname=traitname))
            if traittypeid in ['capacita', 'conoscenza', 'attitudine']: # todo TraitTypeSettings table
                for gamesystemid in list(map(gms.getGamesystemId, (gms.GameSystems.V20_VTM_HOMEBREW_00, gms.GameSystems.V20_VTM_VANILLA))):
                    self.bot.dbm.db.insert("TraitSetting", traitid = traitid, gamesystemid = gamesystemid, gamestateid = 1, rollpermanent = 0, autopenalty = 1)
            response = f'Il tratto {traitname} è stato inserito'
            if std:
                self.bot.dbm.db.query(query_addTraitToPCs, vars = dict(traitid=traitid))
                response +=  f'\nIl nuovo tratto standard {traitname} è stato assegnato ai personaggi!'
        except:
            t.rollback()
            raise
        else:
            t.commit()

        await self.bot.atSend(ctx, response)

    @gmadm.command(name = 'updt', brief = gmadm_help['updt'][1], description = updt_description)
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def updt(self, ctx: gb.GreedyContext, old_traitid: gc.GreedyShortIdConverter, new_traitid: gc.GreedyShortIdConverter, traittype: gc.TraitTypeConverter, tracktype: gc.TrackerTypeConverter, std: gc.NoYesConverter, *args):    
        if len(args) == 0:
            await self.bot.atSend(ctx, newTrait_description)
            return
        
        istrait, old_trait = self.bot.dbm.validators.getValidateTrait( old_traitid).validate()
        if not istrait:
            raise gb.BotException(f"Il tratto {old_traitid} non esiste!")
        
        istrait, new_trait = self.bot.dbm.validators.getValidateTrait(new_traitid).validate()
        if istrait and (old_traitid!=new_traitid):
            raise gb.BotException(f"Il tratto {new_traitid} esiste già!")

        traittypeid = traittype['id']

        traitname = " ".join(list(args))
        
        response = f'Il tratto {traitname} è stato aggiornato'
        t = self.bot.dbm.db.transaction()
        try:
            self.bot.dbm.db.update("Trait", where= 'id = $oldid' , vars=dict(oldid = old_traitid), id = new_traitid, name = traitname, traittype = traittypeid, trackertype = tracktype, standard = std)
            # now we update the language description, but only of the current language
            self.bot.dbm.db.update("LangTrait", where= 'traitId = $traitid and langId = $lid' , vars=dict(traitid=new_traitid, lid = ctx.getLID()), traitName = traitname)
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

    @gmadm.command(name = 'link', brief = gmadm_help['link'][1], description = link_description)
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.genIsChronicleStoryteller(target_chronicle=2)))))
    async def link(self, ctx: commands.Context, chronicle: gc.ChronicleConverter, storyteller: gc.StorytellerConverter = None):
        issuer = str(ctx.message.author.id)
        
        chronid = chronicle['id']

        target_st = None
        if storyteller == None:
            storyteller = await gc.StorytellerConverter().convert(ctx, issuer)
        target_st = storyteller['userid']
        
        t_stc, _ = self.bot.dbm.isChronicleStoryteller(target_st, chronid)
        if t_stc:
            raise gb.BotException(f"L'utente selezionato è già Storyteller per {chronid}")  

        # link
        self.bot.dbm.db.insert("StoryTellerChronicleRel", storyteller=target_st, chronicle=chronid)
        await self.bot.atSend(ctx, f"Cronaca associata")

    @gmadm.command(name = 'unlink', brief = gmadm_help['unlink'][1], description = unlink_description)
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.genIsChronicleStoryteller(target_chronicle=2), sec.genIsSelf(optional_target_user=3)))))
    async def unlink(self, ctx: context.Context, chronicle: gc.ChronicleConverter, storyteller: gc.StorytellerConverter = None):

        issuer = str(ctx.message.author.id)
        chronid = chronicle['id']
        
        target_st = None
        if storyteller == None:
            storyteller = await gc.StorytellerConverter().convert(ctx, issuer)
        target_st = storyteller['userid'] 

        # link
        n = self.bot.dbm.db.delete('StoryTellerChronicleRel', where='storyteller=$storyteller and chronicle=$chronicle', vars=dict(storyteller=target_st, chronicle=chronid))
        if n:
            await self.bot.atSend(ctx, f"Cronaca disassociata")
        else:
            await self.bot.atSend(ctx, f"Nessuna cronaca da disassociare")

    @gmadm.command(name = 'name', brief = gmadm_help['name'][1], description = name_description)
    @commands.before_invoke(gs.command_security(sec.IsAdmin))
    async def name(self, ctx: commands.Context, user: gc.RegisteredUserConverter):
        
        target_st = user['userid'] 
        name = user['name']

        t_st, _ = self.bot.dbm.validators.getValidateBotStoryTeller(target_st).validate()
        if t_st:
            raise gb.BotException(f"L'utente selezionato è già uno storyteller")
        
        self.bot.dbm.db.insert("Storyteller",  userid=target_st)
        await self.bot.atSend(ctx, f"{name} ora è Storyteller")
        
    @gmadm.command(name = 'unname', brief = gmadm_help['unname'][1], description = unname_description)
    @commands.before_invoke(gs.command_security(sec.IsAdmin))
    async def unname(self, ctx: commands.Context, storyteller: gc.StorytellerConverter):

        target_st = storyteller['userid'] 
        name = storyteller['name']
        
        n = self.bot.dbm.unnameStoryTeller(target_st)
        if n:
            await self.bot.atSend(ctx, f"{name} non è più Storyteller")
        else:
            await self.bot.atSend(ctx, f"Nessuna modifica fatta")
    
    @gmadm.command(name = 'traittypes', brief = gmadm_help['traittypes'][1], description = traittypes_description)
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def traittypes(self, ctx: commands.Context):
        
        ttypesl = self.bot.dbm.db.select('TraitType', what = "id, name").list()
        response = "Tipi di tratto: \n"
        response += "\n".join(list(map(lambda x : f"\t**{x['id']}**: {x['name']}", ttypesl)))
        
        await self.bot.atSend(ctx, response)

    @gmadm.command(name = GAMESYSTEMS_CMD, brief = gmadm_help[GAMESYSTEMS_CMD][1], description = GAMESYSTEMS_description)
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def gamesystems(self, ctx: commands.Context):
        
        gamesystems = self.bot.dbm.db.select(ghostDB.TABLENAME_GAMESYSTEM).list()
        response = "Sistemi di gioco: \n"
        response += "\n".join(list(map(lambda x : f"\t**{x[ghostDB.FIELDNAME_GAMESYSTEM_GAMESYSTEMID]}**", gamesystems)))
        
        await self.bot.atSend(ctx, response)
    
    
    @gmadm.command(name = CHANNEL_GAMESYSTEM_CMD, brief=gmadm_help[CHANNEL_GAMESYSTEM_CMD][1], description = CHANNEL_GAMESYSTEM_description)
    @commands.before_invoke(gs.command_security(sec.IsAdmin))
    async def channel_gamesystem(self, ctx: gb.GreedyContext, gamesystem: gc.GameSystemConverter = None):
        channelid = ctx.channel.id
        is_channel, channel = self.bot.dbm.validators.getValidateChannelGameSystem(channelid).validate()
        if not gamesystem:
            channel_rs = None
            if is_channel:
                channel_rs = channel[ghostDB.FIELDNAME_CHANNELGAMESYSTEM_GAMESYSTEMID]
            priority_rs = self.bot.getGameSystemIdByChannel(channelid)
            response = ''
            if not channel_rs is None:
                response += f'Il sistema di gioco salvato per questo canale è {channel_rs}'
            else:
                response += f'Il canale non ha un sistema di gioco impostato'
            if priority_rs != channel_rs:
                response += f', verrà utilizzato {priority_rs}'
            await self.bot.atSendLang(ctx, response)
        else:
            if is_channel:
                self.bot.dbm.db.update(ghostDB.TABLENAME_CHANNELGAMESYSTEM, where= f'{ghostDB.FIELDNAME_CHANNELGAMESYSTEM_CHANNELID} = $channel', vars=dict(channel= channelid), **{ghostDB.FIELDNAME_CHANNELGAMESYSTEM_GAMESYSTEMID: gamesystem})
            else:
                self.bot.dbm.db.insert(ghostDB.TABLENAME_CHANNELGAMESYSTEM, **{ghostDB.FIELDNAME_CHANNELGAMESYSTEM_CHANNELID: channelid, ghostDB.FIELDNAME_CHANNELGAMESYSTEM_GAMESYSTEMID: gamesystem})
            
            await self.bot.atSendLang(ctx, f'sistema di gioco impostato su {gamesystem}')
                
    @gmadm.command(name = CHRONICLE_GAMESYSTEM_CMD, brief=gmadm_help[CHRONICLE_GAMESYSTEM_CMD][1], description = CHRONICLE_GAMESYSTEM_description)
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.genIsChronicleStoryteller(target_chronicle=2)))))
    async def chronicle_gamesystem(self, ctx: gb.GreedyContext, chronicle: gc.ChronicleConverter, gamesystem: gc.GameSystemConverter = None):
        chronicleid = chronicle[ghostDB.FIELDNAME_CHRONICLE_CHRONICLEID]
        if not gamesystem:
            chronicle_rs = chronicle[ghostDB.FIELDNAME_CHRONICLE_GAMESYSTEMID]
            response = ''
            if not chronicle_rs is None:
                response += f'Il sistema di gioco salvato per {chronicleid} è {chronicle_rs}'
            else:
                channelid = ctx.channel.id
                priority_rs = self.bot.getGameSystemIdByChannel(channelid)
                response += f'{chronicleid} non ha un sistema di gioco impostato, verrà utilizzato {priority_rs}'

            await self.bot.atSendLang(ctx, response)
        else:
            self.bot.dbm.db.update(ghostDB.TABLENAME_CHRONICLE, where= f'{ghostDB.FIELDNAME_CHRONICLE_CHRONICLEID} = $chronicleid', vars=dict(chronicleid= chronicleid), **{ghostDB.FIELDNAME_CHRONICLE_GAMESYSTEMID: gamesystem})

            await self.bot.atSendLang(ctx, f'sistema di gioco per {chronicleid} impostato su {gamesystem}')