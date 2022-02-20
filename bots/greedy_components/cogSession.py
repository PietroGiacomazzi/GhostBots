
from typing import AnyStr, Callable
from discord.ext import commands
import discord

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB


class GreedyGhostCog_Session(gb.GreedyGhostCog): 

    @commands.group(name = 'session', brief='Controlla le sessioni di gioco', description = "Le sessioni sono basate sui canali: un canale può ospitare una sessione alla volta, ma la stessa cronaca può avere sessioni attive in più canali.")
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
    @gs.command_security(gs.genIsAdminOrChronicleStoryteller(target_chronicle=0))
    async def start(self, ctx: commands.Context, *args):
        if len(args) != 1:
            await self.bot.atSendLang(ctx, "string_error_wrong_number_arguments")
            return

        chronicleid = args[0].lower()
        response = ''

        sessions = self.bot.dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
        if len(sessions):
            response = "C'è già una sessione in corso in questo canale"
        else:
            self.bot.dbm.db.insert('GameSession', chronicle=chronicleid, channel=ctx.channel.id)
            chronicle = self.bot.dbm.db.select('Chronicle', where='id=$chronicleid', vars=dict(chronicleid=chronicleid))[0]
            response = f"Sessione iniziata per la cronaca {chronicle['name']}"
            # TODO lista dei pg?
            # TODO notifica i giocatori di pimp attivi

        await self.bot.atSend(ctx, response)

    @session.command(name = 'list', brief = 'Elenca le sessioni aperte', description = 'Elenca le sessioni aperte. richiede di essere admin o storyteller')
    @gs.command_security(gs.IsAdminOrStoryteller)
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
                lines.append(f"**{session['chronicle']}** in: {channel.category}/{channel.name}")
            elif isinstance(channel, discord.abc.PrivateChannel):
                lines.append(f"**{session['chronicle']}** in un canale privato")
        if not len(lines):
            lines.append("Nessuna!")
        response = "Sessioni attive:\n" + ("\n".join(lines))
        await self.bot.atSend(ctx, response)

    @session.command(name = 'end', brief = 'Termina la sessione corrente', description = 'Termina la sessione corrente. Richiede di essere admin o storyteller della sessione in corso.')
    @gs.command_security(gs.CanEditRunningSession)
    async def end(self, ctx: commands.Context):
        response = ''
        
        n = self.bot.dbm.db.delete('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
        if n:
            response = f'sessione terminata'
        else: # non dovrebbe mai accadere
            response = f'la cronaca non ha una sessione aperta in questo canale'
    
        await self.bot.atSend(ctx, response)