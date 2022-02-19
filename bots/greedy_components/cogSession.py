
from typing import AnyStr, Callable
from discord.ext import commands
import discord

from greedy_components import greedyBase as gb

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB


class GreedyGhostCog_Session(gb.GreedyGhostCog): 

    @commands.group(brief='Controlla le sessioni di gioco', description = "Le sessioni sono basate sui canali: un canale può ospitare una sessione alla volta, ma la stessa cronaca può avere sessioni attive in più canali.")
    async def session(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            sessions = self.bot.dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
            if len(sessions):
                chronicle = self.bot.dbm.db.select('Chronicle', where='id=$chronicle', vars=dict(chronicle=sessions[0]['chronicle']))
                cn = chronicle[0]['name']
                await self.bot.atSend(ctx, f"Sessione attiva: {cn}")
            else:
                await self.bot.atSend(ctx, "Nessuna sessione attiva in questo canale!")
            

    @session.command(brief = 'Inizia una sessione', description = '.session start <nomecronaca>: inizia una sessione per <nomecronaca> (richiede essere admin o storyteller della cronaca da iniziare) (richiede essere admin o storyteller della cronaca da iniziare)')
    async def start(self, ctx: commands.Context, *args):
        issuer = str(ctx.message.author.id)
        if len(args) != 1:
            await self.bot.atSendLang(ctx, "string_error_wrong_number_arguments")
            return

        chronicleid = args[0].lower()
        vc, _ = self.bot.dbm.isValidChronicle(chronicleid)
        if not vc:
            await self.bot.atSend(ctx, "Id cronaca non valido")
            return
            
        st, _ = self.bot.dbm.isChronicleStoryteller(issuer, chronicleid)
        ba, _ = self.bot.dbm.isBotAdmin(issuer)
        can_do = st or ba

        sessions = self.bot.dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
        if len(sessions):
            response = "C'è già una sessione in corso in questo canale"
        elif can_do:
            self.bot.dbm.db.insert('GameSession', chronicle=chronicleid, channel=ctx.channel.id)
            chronicle = self.bot.dbm.db.select('Chronicle', where='id=$chronicleid', vars=dict(chronicleid=chronicleid))[0]
            response = f"Sessione iniziata per la cronaca {chronicle['name']}"
            # TODO lista dei pg?
            # TODO notifica i giocatori di pimp attivi
        else:
            response = "Non hai il ruolo di Storyteller per la questa cronaca"
        await self.bot.atSend(ctx, response)

    @session.command(name = 'list', brief = 'Elenca le sessioni aperte', description = 'Elenca le sessioni aperte. richiede di essere admin o storyteller')
    async def session_list(self, ctx: commands.Context):
        issuer = ctx.message.author.id
        st, _ = self.bot.dbm.isStoryteller(issuer) # TODO: elenca solo le sue?
        ba, _ = self.bot.dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise gb.BotException("no.")
        
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
            #elif isinstance(channel, discord.abc.PrivateChannel):
            #    pvt += 1
        if not len(lines):
            lines.append("Nessuna!")
        response = "Sessioni attive:\n" + ("\n".join(lines))
        await self.bot.atSend(ctx, response)
        

    @session.command(brief = 'Termina la sessione corrente', description = 'Termina la sessione corrente. Richiede di essere admin o storyteller della sessione in corso.')
    async def end(self, ctx: commands.Context):
        response = ''
        issuer = str(ctx.message.author.id)
        sessions = self.bot.dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
        if len(sessions):
            ba, _ = self.bot.dbm.isBotAdmin(issuer)
            st, _ = self.bot.dbm.isChronicleStoryteller(issuer, sessions[0]['chronicle'])
            can_do = ba or st
            if can_do:
                n = self.bot.dbm.db.delete('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
                if n:
                    response = f'sessione terminata'
                else: # non dovrebbe mai accadere
                    response = f'la cronaca non ha una sessione aperta in questo canale'
            else:
                response = "Non hai il ruolo di Storyteller per la questa cronaca"
        else:
            response = "Nessuna sessione attiva in questo canale!"
        await self.bot.atSend(ctx, response)