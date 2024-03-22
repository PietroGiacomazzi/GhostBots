import random, logging
from dataclasses import dataclass
from discord.ext import commands

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs


import support.vtm_res as vtm_res
import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB

_log = logging.getLogger(__name__)

roll_longdescription = """.roll <cosa> <argomento1> (<parametro1> <parametro2>...) <argomento2> ...
  <cosa> è il numero di dadi in forma XdY (es. ".roll 1d20")
  <argomento> indicazioni aggiuntive che pilotano il tiro con eventuali <parametri>

Argomenti diponibili:

.roll 7d10 somma                      -> Somma i risultati in un unico valore
.roll 7d10 diff 6                     -> Tiro a difficoltà 6
.roll 7d10 danni                      -> Tiro danni
.roll 7d10 +5                         -> Aggiunge 5 successi
.roll 7d10 progressi                  -> Tiro per i progressi
.roll 7d10 lapse                      -> Tiro per i progressi in timelapse
.roll 7d10 multi 3 diff 6             -> Azione multipla con 3 mosse
.roll 7d10 split 6 7                  -> Azione splittata a diff. separate (6 e 7)
.roll 7d10 diff 6 multi 3 split 2 6 7 -> Multipla [3] con split [al 2° tiro] a diff. separate [6,7]

A sessione attiva:

.roll tratto1+tratto2  -> al posto di XdY per usare le statistiche del proprio pg (es. ".roll destrezza+schivare")
.roll iniziativa       -> .roll 1d10 +(destrezza+prontezza+velocità)
.roll riflessi         -> .roll volontà diff (10-prontezza)
.roll assorbi          -> .roll costituzione+robustezza diff 6 danni
.roll <...> penalita   -> Applica la penalità derivata dalla salute
.roll <...> +/- XdY    -> Modifica il numero di dadi del tiro
.roll <...> permanente -> Usa i valori base e non quelli potenziati/spesi (es.: ".roll volontà permanente diff 7")

Note sugli spazi:

Si può spaziare o meno tra i tratti senza problemi:
  ".roll forza + rissa" ok
  ".roll 2d10+ rissa" ok
  ".roll forza +rissa" ok
  ".roll forza+2d10" ok
  ".roll forza+2" ok

Si può omettere lo spazio tra argomento e il 1° parametro:
  ".roll 3d10 diff6" ok
  ".roll 3d10 split6 7" ok
  ".roll 3d10 split67" no"""

strat_list = [
                'sart',
                'sarta',
                'sarts',
                'strt',
                'strart',
                'stat',
                'statr',
                'srtra',
                'srtat',
                'srat',
                'srats',
                'sratr',
                'srart',
                'srast',
                'tart',
                'star',
                'sttar',
                'trast',
                'strar',
                'sbrat',
                'sbratt',
                'srrat',
                'rtsat',
                'stort',
                'sarto',
                'starto',
                'strta',
                'rsat', #dio
                'sbatt',
                'rast',
                'sat',
                'arst',
                'starterino',
                'rstart',
                'atra',
                'startt',
                'srt',
                #
                'START'
                ]

class GreedyGhostCog_Roller(gb.GreedyGhostCog):
    
    @commands.command(name = 'search', brief = "Cerca un tratto", description = "Cerca un tratto:\n\n .search <termine di ricerca> -> elenco dei risultati")
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def search_trait(self, ctx: gb.GreedyContext, *args):
        if len(args) == 0:
            await self.bot.atSendLang("string_error_no_searchterm")
            return

        searchstring = "%" + (" ".join(args)) + "%"
        lower_version = searchstring.lower()
        traits = self.bot.dbm.db.select("LangTrait", where="langId=$langid and (traitId like $search_lower or traitShort like $search_lower or traitName like $search_string)", vars=dict(search_lower=lower_version, search_string = searchstring, langid=ctx.getLID()))
        
        if not len(traits):
            await self.bot.atSendLang(ctx, "string_msg_no_match")
            return

        response = self.bot.getStringForUser(ctx, "string_msg_found_traits") +":\n"
        for trait in traits:
            response += f"\n {trait['traitShort']} ({trait['traitId']}): {trait['traitName']}"
        await self.bot.atSend(ctx, response)

    @commands.command(name = 'call', brief = "Richiama l'attenzione dello storyteller", description = "Richiama l'attenzione dello storyteller della cronaca attiva nel canale in cui viene invocato")
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def call(self, ctx: commands.Context):
        character = self.bot.dbm.getActiveChar(ctx)
        sts = self.bot.dbm.getChannelStoryTellers(ctx.channel.id)
        response = f"{character['fullname']} ({ctx.message.author}) richiede la tua attenzione!"
        for st in sts:
            stuser = await self.bot.fetch_user(st['storyteller'])
            response += f' {stuser.mention}'
        await self.bot.atSend(ctx, response)

    @commands.command(name = 'start', brief = "Tira 1d100 per l'inizio giocata", description = "Tira 1d100 per l'inizio giocata")
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def start(self, ctx: commands.Context):
        await self.bot.atSend(ctx, f'{random.randint(1, 100)}')

    @commands.command(name = 'strat', aliases = strat_list, brief = "Tira 1d100 per l'inizio giocata", description = "Tira 1d100 per l'inizio giocata anche se l'invocatore è ubriaco")
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def strat(self, ctx: commands.Context):
        await self.bot.atSend(ctx, f'{random.randint(1, 100)}, però la prossima volta scrivilo giusto <3')