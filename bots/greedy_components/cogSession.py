from discord.ext import commands
import discord, logging

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs
from greedy_components import greedyConverters as gc

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB
import support.security as sec

_log = logging.getLogger(__name__)

class GreedyGhostCog_Session(gb.GreedyGhostCog): 

    @commands.group(name = 'session', brief='Controlla le sessioni di gioco', description = "Le sessioni sono basate sui canali: un canale può ospitare una sessione alla volta, ma la stessa cronaca può avere sessioni attive in più canali.")
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def session(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            sessions = self.bot.dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
            if len(sessions):
                chronicle = self.bot.dbm.db.select('Chronicle', where='id=$chronicle', vars=dict(chronicle=sessions[0]['chronicle']))
                cn = chronicle[0]['name']
                await self.bot.atSend(ctx, f"Sessione attiva: {cn}")
            else:
                await self.bot.atSend(ctx, "Nessuna sessione attiva in questo canale!")
            

    @session.command(name = 'start', brief = 'Inizia una sessione', description = '.session start <nomecronaca>: inizia una sessione per <nomecronaca> (richiede essere admin o storyteller della cronaca da iniziare) (richiede essere admin o storyteller della cronaca da iniziare)')
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.genIsChronicleStoryteller(target_chronicle = 2)))))
    async def start(self, ctx: commands.Context, chronicle: gc.ChronicleConverter):
        chronicleid = chronicle['id'].lower()
        response = ''

        sessions = self.bot.dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
        if len(sessions):
            response = f"C'è già una sessione in corso in questo canale: {sessions[0]['chronicle']}"
        else:
            self.bot.dbm.db.insert('GameSession', chronicle=chronicleid, channel=ctx.channel.id)
            response = f"Sessione iniziata per la cronaca {chronicle['name']}"
            # TODO lista dei pg?
            # TODO notifica i giocatori di pimp attivi
        
        await self.bot.update_presence_status()
        await self.bot.atSend(ctx, response)

    @session.command(name = 'list', brief = 'Elenca le sessioni aperte', description = 'Elenca le sessioni aperte. richiede di essere admin o storyteller')
    @commands.before_invoke(gs.command_security(gs.basicStoryTeller))
    async def session_list(self, ctx: commands.Context):
        sessions = self.bot.dbm.db.select('GameSession').list()
        channels = []
        lines = []
        for s in sessions:
            try:
                ch = await self.bot.fetch_channel(int(s['channel']))
                channels.append(ch)
            except discord.errors.Forbidden as e:
                lines.append(f"**{s['chronicle']}** in: UNKNOWN")
                channels.append(None)
        #pvt = 0
        for session, channel in zip(sessions, channels):
            if isinstance(channel, discord.abc.GuildChannel):
                lines.append(f"**{session['chronicle']}** in: {channel.guild.name}/{channel.category}/{channel.name}")
            elif isinstance(channel, discord.abc.PrivateChannel):
                lines.append(f"**{session['chronicle']}** in un canale privato")
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