from discord.ext import commands
import discord, logging

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs
from greedy_components import greedyConverters as gc

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB
import support.security as sec
import support.gamesystems as gms

_log = logging.getLogger(__name__)

class GreedyGhostCog_Session(gb.GreedyGhostCog): 

    async def sendSessionInfo(self, ctx, session, msg: str):
        gamestate_lang = self.bot.getStringForUser(ctx, utils.gamestate_label(session[ghostDB.FIELDNAME_GAMESESSION_GAMESTATEID]))
        await self.bot.atSend(ctx, f"{msg}: {session['name']} ({gamestate_lang})")

    @commands.group(name = 'session', brief='Controlla le sessioni di gioco', description = "Le sessioni sono basate sui canali: un canale può ospitare una sessione alla volta, ma la stessa cronaca può avere sessioni attive in più canali.")
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def session(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            vs, session = self.bot.dbm.validators.getValidateRunningSession(ctx.channel.id).validate()
            if vs:
                await self.sendSessionInfo(ctx, session, "Sessione attiva")
            else:
                await self.bot.atSend(ctx, "Nessuna sessione attiva in questo canale!")
            

    @session.command(name = 'start', brief = 'Inizia una sessione', description = '.session start <nomecronaca>: inizia una sessione per <nomecronaca> (richiede essere admin o storyteller della cronaca da iniziare) (richiede essere admin o storyteller della cronaca da iniziare)')
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.genIsChronicleStoryteller(target_chronicle = 2)))))
    async def start(self, ctx: commands.Context, chronicle: gc.ChronicleConverter):
        chronicleid = chronicle['id'].lower()

        session = None
        msg = ''

        vs, session = self.bot.dbm.validators.getValidateRunningSession(ctx.channel.id).validate()
        if vs:
            msg = "C'è già una sessione in corso in questo canale"
        else:
            self.bot.dbm.db.insert('GameSession', chronicle=chronicleid, channel=ctx.channel.id)
            session = self.bot.dbm.validators.getValidateRunningSession(ctx.channel.id).get()
            msg = "Sessione iniziata per la cronaca"
        
        await self.sendSessionInfo(ctx, session, msg)
        await self.bot.update_presence_status()

    @session.command(name = 'list', brief = 'Elenca le sessioni aperte', description = 'Elenca le sessioni aperte. richiede di essere admin o storyteller')
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def session_list(self, ctx: commands.Context):
        sessions = self.bot.dbm.db.select(ghostDB.TABLENAME_GAMESESSION).list()
        channels = []
        lines = []
        for s in sessions:
            if s[ghostDB.FIELDNAME_GAMESESSION_CHANNEL] > 0:
                try:
                    ch = await self.bot.fetch_channel(int(s[ghostDB.FIELDNAME_GAMESESSION_CHANNEL]))
                    channels.append(ch)
                except discord.errors.Forbidden as e:
                    lines.append(f"**{s[ghostDB.FIELDNAME_GAMESESSION_CHRONICLE]}** in: FORBIDDEN")
                    channels.append(None)
                except Exception as e:
                    lines.append(f"**{s[ghostDB.FIELDNAME_GAMESESSION_CHRONICLE]}** in: ERRROR")
                    self.bot.logToDebugUser(f"Error while getting channel info: {e}")
                    channels.append(None)
            else:
                lines.append(f"**{s[ghostDB.FIELDNAME_GAMESESSION_CHRONICLE]}**, sessione fuori discord")
                channels.append(None)
        #pvt = 0
        for session, channel in zip(sessions, channels):
            if isinstance(channel, discord.abc.GuildChannel):
                lines.append(f"**{session[ghostDB.FIELDNAME_GAMESESSION_CHRONICLE]}** in: {channel.guild.name}/{channel.category}/{channel.name}")
            elif isinstance(channel, discord.abc.PrivateChannel):
                lines.append(f"**{session[ghostDB.FIELDNAME_GAMESESSION_CHRONICLE]}** in un canale privato")
        if not len(lines):
            lines.append("Nessuna!")
        response = "Sessioni attive:\n" + ("\n".join(lines))
        await self.bot.atSend(ctx, response)

    @session.command(name = 'end', brief = 'Termina la sessione corrente', description = 'Termina la sessione corrente. Richiede di essere admin o storyteller della sessione in corso.')
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.CanEditRunningSession))))
    async def end(self, ctx: commands.Context):
        response = ''
        
        n = self.bot.dbm.db.delete('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
        if n:
            response = f'sessione terminata'
        else: # non dovrebbe mai accadere
            response = f'Non c\'è una sessione aperta in questo canale'
    
        await self.bot.update_presence_status()
        await self.bot.atSend(ctx, response)

    @session.command(name = 'quiete', brief = 'Imposta lo stato di quiete', description = 'Imposta lo stato di quiete. Richiede di essere admin o storyteller della sessione in corso.')
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.CanEditRunningSession))))
    async def quiet(self, ctx: commands.Context):
        session = self.bot.dbm.validators.getValidateRunningSession(ctx.channel.id).get()
        gstateid = gms.GameStates.QUIET
        if self.bot.dbm.setGameState(session[ghostDB.FIELDNAME_GAMESESSION_CHANNEL], gstateid) == 1:
            await self.bot.atSendLang(ctx, "string_gamestate_changed", self.bot.getStringForUser(ctx, utils.gamestate_label(gstateid)))
        else:
            await self.bot.atSendLang(ctx, "string_gamestate_nochange", self.bot.getStringForUser(ctx, utils.gamestate_label(gstateid)))

    @session.command(name = 'stress', brief = 'Imposta lo stato di stress', description = 'Imposta lo stato di stress. Richiede di essere admin o storyteller della sessione in corso.')
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.CanEditRunningSession))))
    async def stress(self, ctx: commands.Context):
        session = self.bot.dbm.validators.getValidateRunningSession(ctx.channel.id).get()
        gstateid = gms.GameStates.STRESS
        if self.bot.dbm.setGameState(session[ghostDB.FIELDNAME_GAMESESSION_CHANNEL], gstateid) == 1:
            await self.bot.atSendLang(ctx, "string_gamestate_changed", self.bot.getStringForUser(ctx, utils.gamestate_label(gstateid)))
        else:
            await self.bot.atSendLang(ctx, "string_gamestate_nochange", self.bot.getStringForUser(ctx, utils.gamestate_label(gstateid)))