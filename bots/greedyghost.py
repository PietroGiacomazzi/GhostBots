#!/usr/bin/env python3

from discord.ext import commands
import random, sys, configparser, web, traceback, MySQLdb
import support.vtm_res as vtm_res

if len(sys.argv) == 1:
    print("Specifica un file di configurazione!")
    sys.exit()

config = configparser.ConfigParser()
config.read(sys.argv[1])

TOKEN = config['Discord']['token']


SOMMA_CMD = ["somma", "s", "lapse"]
DIFF_CMD = ["diff", "d"]
MULTI_CMD = ["multi", "m"]
DANNI_CMD = ["danni", "dmg"]
PROGRESSI_CMD = ["progressi", "p"]
SPLIT_CMD = ["split"]
INIZIATIVA_CMD = ["iniziativa", "iniz"]

NORMALE = 0
SOMMA = 1
DANNI = 2
PROGRESSI = 3

max_dice = 100
max_faces = 100


die_emoji = {
    2: ":two:",
    3: ":three:",
    4: ":four:",
    5: ":five:",
    6: ":six:",
    7: ":seven:",
    8: ":eight:",
    9: ":nine:",
    10: ":keycap_ten:"
    }

def prettyRoll(roll, diff, cancel):
    for i in range(0, len(roll)-cancel):
        die = roll[i]
        if die == 1:
            roll[i] = '**1**'
        elif die >= diff:
            roll[i] = die_emoji[die]
        else:
            roll[i] = str(die)
    for i in range(len(roll)-cancel, len(roll)):
        roll[i] = f"**~~{roll[i]}~~**"
    random.shuffle(roll)
    return "["+", ".join(roll)+"]"

def rollStatusDMG(n):
    if n == 1:
        return f':green_square: **{1} Danno**'
    elif n > 1:
        return f':green_square: **{n} Danni**'
    else:
        return f':red_square: **Nessun danno**'

def rollStatusProgress(n):
    if n == 1:
        return f':green_square: **{1} Ora**'
    elif n > 1:
        return f':green_square: **{n} Ore**'
    else:
        return f':red_square: **Il soffitto è estremamente interessante**'

def rollStatusNormal(n):
    if n == 1:
        return f':green_square: **{1} Successo**'
    elif n > 1:
        return f':green_square: **{n} Successi**'
    elif n == 0:
        return f':yellow_square: **Fallimento**'
    elif n == -2:
        return f':orange_square: **Fallimento drammatico**'
    else:
        return f':sos: **Fallimento critico**'

def rollAndFormatVTM(ndice, nfaces, diff, statusFunc = rollStatusNormal, extra_succ = 0, cancel = True, spec = False):
    successi, tiro, cancel = vtm_res.roller(ndice, nfaces, diff, cancel, spec)
    pretty = prettyRoll(tiro, diff, cancel)
    successi += extra_succ
    status = statusFunc(successi)
    response = status + f' (diff {diff}): {pretty}'
    if extra_succ:
        response += f' **+{extra_succ}**'
    return response

def atSend(ctx, msg):
    return ctx.send(f'{ctx.message.author.mention} {msg}')

def findSplit(idx, splits):
    for si in range(len(splits)):
        if idx == splits[si][0]:
            return splits[si][1:]
    return []

class DBManager:
    def __init__(self, config):
        self.cfg = config
        self.reconnect()
    def reconnect(self):
        self.db = web.database(dbn=self.cfg['type'], user=self.cfg['user'], pw=self.cfg['pw'], db=self.cfg['database']) # wait_timeout = 3153600# seconds

class BotException(Exception): # use this for 'known' error situations
    def __init__(self, msg):
        super(BotException, self).__init__(msg)
    
dbm = DBManager(config['Database'])

botcmd_prefixes = ['.']
bot = commands.Bot(botcmd_prefixes)

#executed once on bot boot
@bot.event
async def on_ready():
    for guild in bot.guilds:
        print(
            f'{bot.user} is connected to the following guild:\n'
            f'{guild.name} (id: {guild.id})'
        )
    #members = '\n - '.join([member.name for member in guild.members])
    #print(f'Guild Members:\n - {members}')
    #await bot.get_channel(int(config['DISCORD_DEBUG_CHANNEL'])).send("bot is online")

def isValidCharacter(charid):
    characters = dbm.db.select('PlayerCharacter', where='id=$id', vars=dict(id=charid))
    return bool(len(characters)), (characters[0] if (len(characters)) else None)

# dato un canale e un utente, trova il pg interpretato
def getActiveChar(ctx):
    playercharacters = dbm.db.query("""
SELECT pc.*
FROM GameSession gs
join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
join PlayerCharacter pc on (pc.id = cc.playerchar)
where gs.channel = $channel and pc.player = $player
""", vars=dict(channel=ctx.channel.id, player=ctx.message.author.id))
    if len(playercharacters) == 0:
        raise BotException("Non stai interpretando nessun personaggio!")
    if len(playercharacters) > 1:
        raise BotException("Stai interplretando più di un personaggio in questa cronaca, non so a chi ti riferisci!")
    return playercharacters[0]

def getTrait(pc_id, trait_id):
    traits = dbm.db.query("""
SELECT
    ct.*,
    t.*,
    tt.textbased as textbased
FROM CharacterTrait ct
join Trait t on (t.id = ct.trait)
join TraitType tt on (t.traittype = tt.id)
where ct.trait = $trait and ct.playerchar = $pc
""", vars=dict(trait=trait_id, pc=pc_id))
    if len(traits) == 0:
        raise BotException(f'{pc_id} non ha il tratto {trait_id}')
    return traits[0]

# todo has_trait?

def isBotAdmin(userid):
    admins = dbm.db.select('BotAdmin',  where='userid = $userid', vars=dict(userid=userid))
    return bool(len(admins)), (admins[0] if (len(admins)) else None)

def isStoryteller(userid):
    storytellers = dbm.db.select('Storyteller',  where='userid = $userid', vars=dict(userid=userid))
    return bool(len(storytellers)), (storytellers[0] if (len(storytellers)) else None)

def isCharacterOwner(userid, character):
    characters = dbm.db.select('PlayerCharacter',  where='owner = $owner and id=$character', vars=dict(userid=userid, character=character))
    return bool(len(characters)), (characters[0] if (len(characters)) else None)

def isChronicleStoryteller(userid, chronicle):
    storytellers = dbm.db.select('StoryTellerChronicleRel', where='storyteller = $userid and chronicle=$chronicle' , vars=dict(userid=userid, chronicle = chronicle))
    return bool(len(storytellers)), (storytellers[0] if (len(storytellers)) else None)

def isValidTrait(traitid):
    traits = dbm.db.select('Trait', where='id=$id', vars=dict(id=traitid))
    return bool(len(traits)), (traits[0] if (len(traits)) else None)

def isValidTraitType(traittypeid):
    traittypes = dbm.db.select('TraitType', where='id=$id', vars=dict(id=traittypeid))
    return bool(len(traittypes)), (traittypes[0] if (len(traittypes)) else None)

@bot.event
async def on_command_error(ctx, error):
    ftb = traceback.format_exc()
    #logging.warning(traceback.format_exc()) #logs the error
    #ignored = (commands.CommandNotFound, )
    error = getattr(error, 'original', error)
    #if isinstance(error, ignored):
    #    print(error)
    if isinstance(error, commands.CommandNotFound):
        try:
            msgsplit = ctx.message.content.split(" ")
            msgsplit[0] = msgsplit[0][1:] # toglie prefisso
            charid = msgsplit[0]
            ic, character = isValidCharacter(charid)
            if ic:
                await pgmanage(ctx, *msgsplit)
        except MySQLdb.OperationalError as e:
            if e.args[0] == 2006:
                dbm.reconnect()
                await atSend(ctx, f'Ho dovuto ripristinare al connessione Database, per favore riprova')
            else:
                await atSend(ctx, f'Congratulazioni! hai trovato un modo per rompere il comando!')
                debug_user = await bot.fetch_user(int(config['Discord']['debuguser']))
                await debug_user.send(f'Il messaggio:\n\n{ctx.message.content}\n\n ha causato l\'errore di tipo {type(error)}:\n\n{error}\n\n{ftb}')
        except BotException as e:
            await atSend(ctx, f'{e}')   
    elif isinstance(error, BotException):
        await atSend(ctx, f'{error}')     
    else:
        if isinstance(error, MySQLdb.OperationalError) and error.args[0] == 2006:
            dbm.reconnect()
            await atSend(ctx, f'Ho dovuto ripristinare al connessione Database, per favore riprova')
        else:
            await atSend(ctx, f'Congratulazioni! hai trovato un modo per rompere il comando!')
        #print("debug user:", int(config['Discord']['debuguser']))
        debug_user = await bot.fetch_user(int(config['Discord']['debuguser']))
        await debug_user.send(f'Il messaggio:\n\n{ctx.message.content}\n\n ha causato l\'errore di tipo {type(error)}:\n\n{error}\n\n{ftb}')


@bot.command(name='coin', help = 'Testa o Croce.')
async def coin(ctx):
    moneta=['Testa' , 'Croce']
    await atSend(ctx, f'{random.choice(moneta)}')

roll_longdescription = """
.roll 10d10 - tiro senza difficoltà
.roll 10d10 somma - somma il numero dei tiri
.roll 10d10 diff 6 - tiro con difficoltà specifica
.roll 10d10 danni - tiro danni
.roll 10d10 +5 danni - tiro danni con modificatore
.roll 10d10 progressi - tiro per i progressi del giocatore
.roll 10d10 lapse - tiro per i progressi in timelapse del giocatore
.roll 10d10 multi 3 diff 6 - tiro multiplo
.roll 10d10 split 6 7 - split a difficoltà separate [6, 7]
.roll 10d10 diff 6 multi 3 split 2 6 7  - multipla [3] con split [al 2° tiro] a difficoltà separate [6,7]
.roll 10d10 multi 3 split 2 6 7 split 3 4 5 - multipla [3] con split al 2° e 3° tiro
"""

# todo: usare delle funzioni di validazione e usare BotException per gli errori
@bot.command(name='roll', aliases=['r', 'tira', 'lancia'], brief = 'Tira dadi', description = roll_longdescription)
async def roll(ctx, *args):
    #print("roll args:", repr(args))
    iniziativa = False
    try:
        n = -1
        faces = -1
        if len(args) == 0:
            raise ValueError("roll cosa diomadonna")
        what = args[0].lower()
        if what in INIZIATIVA_CMD:
            n = 1
            faces = 10
            iniziativa = True
        else:            
            singletrait, _ = isValidTrait(what)
            if what.count("+") or singletrait:
                character = getActiveChar(ctx)
                split = what.split("+")
                faces = 10
                n = 0
                for trait in split:
                    n += getTrait(character['id'], trait)['cur_value']
            else:
                split = what.split("d")
                if len(split) > 2:
                    raise ValueError("Troppe 'd' b0ss")
                if len(split) == 1:
                    raise ValueError(f'"{split[0]}" cosa')
                if split[0] == "":
                    split[0] = "1"
                if not split[0].isdigit():
                    raise ValueError(f'"{split[0]}" non è un numero intero positivo')
                if split[1] == "":
                    split[1] = "10"
                if not split[1].isdigit():
                    raise ValueError(f'"{split[1]}" non è un numero intero positivo')
                n = int(split[0])
                faces = int(split[1])
        if n == 0:
            raise ValueError(f'{n} non è > 0')
        if  faces == 0:
            raise ValueError(f'{faces} non è > 0')
        if n > max_dice:
            raise ValueError(f'{n} dadi sono troppi b0ss')
        if faces > max_faces:
            raise ValueError(f'{faces} facce sono un po\' tante')
        if len(args) == 1: #simple roll
            raw_roll = list(map(lambda x: random.randint(1, faces), range(n)))
            response = repr(raw_roll)
        else:
            diff = None
            multi = None
            split = [] # lista di liste [indice, diff1, diff2]
            rolltype = 0 # somma, progressi...
            add = 0 # extra successi
            # leggo gli argomenti
            i = 1
            while i < len(args):
                if args[i] in SOMMA_CMD:
                    rolltype = SOMMA
                elif args[i] in DIFF_CMD:
                    if diff:
                        raise ValueError(f'mi hai già dato una difficoltà')
                    if len(args) == i+1:
                        raise ValueError(f'diff cosa')
                    if not args[i+1].isdigit():
                        raise ValueError(f'"{args[i+1]}" non è una difficoltà valida')
                    diff = int(args[i+1])
                    if diff > 10 or diff < 2:
                        raise ValueError(f'{args[i+1]} non è una difficoltà valida')
                    i += 1 
                elif args[i] in MULTI_CMD:
                    if len(split):
                        raise ValueError(f'multi va specificato prima di split')
                    if multi:
                        raise ValueError(f'Stai tentando di innestare 2 multiple?')
                    if len(args) == i+1:
                        raise ValueError(f'multi cosa')
                    if not args[i+1].isdigit():
                        raise ValueError(f'"{args[i+1]}" non è un numero di mosse valido')
                    multi = int(args[i+1])
                    if multi < 2:
                        raise ValueError(f'una multipla deve avere almeno 2 tiri!')
                    if n-multi-(multi-1) <= 0:
                        raise ValueError(f'Hai lo 0.0001% di riuscita, prova a ridurre i movimenti') # non hai abbastanza dadi per questo numero di mosse!
                    i += 1
                elif args[i] in DANNI_CMD:
                    rolltype = DANNI
                elif args[i] in PROGRESSI_CMD:
                    rolltype = PROGRESSI
                elif args[i] in SPLIT_CMD:
                    roll_index = 0
                    if multi:
                        if len(args) < i+4:
                            raise ValueError(f'split prende almeno 3 parametri con multi!')
                        if not args[i+1].isdigit() or args[i+1] == "0":
                            raise ValueError(f'"{args[i+1]}" non è un intero positivo')
                        roll_index = int(args[i+1])-1
                        if roll_index >= multi:
                            raise ValueError(f'"Non puoi splittare il tiro {args[i+1]} con multi {multi}')
                        if sum(filter(lambda x: x[0] == roll_index, split)): # cerco se ho giò splittato questo tiro
                            raise ValueError(f'Stai già splittando il tiro {roll_index+1}')
                        i += 1
                    else: # not an elif because reasons
                        if len(args) < i+3:
                            raise ValueError(f'split prende almeno 2 parametri!')
                    temp = args[i+1:i+3]
                    if (not temp[0].isdigit()) or temp[0] == "0":
                        raise ValueError(f'"{temp[0]}" non è un intero positivo')
                    if (not temp[1].isdigit()) or temp[1] == "0":
                        raise ValueError(f'"{temp[1]}" non è un intero positivo')
                    split.append( [roll_index] + list(map(int, temp)))
                    i += 2
                elif args[i].startswith("+"):
                    raw = args[i][1:]
                    if raw == "":
                        if len(args) == i+1:
                            raise ValueError(f'+ cosa')
                        raw = args[i+1]
                        i += 1
                    if not raw.isdigit() or raw == "0":
                        raise ValueError(f'"{raw}" non è un intero positivo')
                    add = int(raw)
                else:
                    width = 3
                    ht = " ".join(list(args[max(0, i-width):i]) + ['**'+args[i]+'**'] + list(args[min(len(args), i+1):min(len(args), i+width)]))
                    raise ValueError(f"L'argomento '{args[i]}' in '{ht}' non mi è particolarmente chiaro")
                i += 1
            # decido cosa fare
            if iniziativa:
                raw_roll = random.randint(1, faces)
                final_val = raw_roll+add
                if multi or len(split) or (not rolltype in [NORMALE, SOMMA]) or diff:
                    raise BotException("Combinazione di parametri non valida!")
                response = f'Iniziativa: **{final_val}**, tiro: [{raw_roll}]' + (f'+{add}' if add else '')
            elif multi:
                if rolltype == NORMALE:
                    response = ""
                    if not diff:
                        raise ValueError(f'Si ma mi devi dare una difficoltà')
                    for i in range(multi):
                        parziale = ''
                        ndadi = n-i-multi
                        split_diffs = findSplit(i, split)
                        if len(split_diffs):
                            pools = [(ndadi-ndadi//2), ndadi//2]
                            for j in range(len(pools)):
                                parziale += f'\nTiro {j+1}: '+ rollAndFormatVTM(pools[j], faces, split_diffs[j])
                        else:
                            parziale = rollAndFormatVTM(ndadi, faces, diff)
                        response += f'\nAzione {i+1}: '+parziale # line break all'inizio tanto c'è il @mention
                else:
                    raise ValueError(f'Combinazione di parametri non supportata')
            else: # 1 tiro solo 
                if len(split):
                    if rolltype == NORMALE:
                        pools = [(n-n//2), n//2]
                        response = ''
                        for i in range(len(pools)):
                            parziale = rollAndFormatVTM(pools[i], faces, split[0][i+1])
                            response += f'\nTiro {i+1}: '+parziale
                    else:
                        raise ValueError(f'Combinazione di parametri non supportata')
                else:
                    if rolltype == NORMALE: # tiro normale
                        if not diff:
                            raise ValueError(f'Si ma mi devi dare una difficoltà')
                        #successi, tiro = vtm_res.decider(sorted(raw_roll), diff)
                        response = rollAndFormatVTM(n, faces, diff, rollStatusNormal, add)
                    elif rolltype == SOMMA:
                        raw_roll = list(map(lambda x: random.randint(1, faces), range(n)))
                        somma = sum(raw_roll)+add
                        response = f'somma: **{somma}**, tiro: {raw_roll}' + (f'+{add}' if add else '')
                    elif rolltype == DANNI:
                        if not diff:
                            diff = 6
                        response = rollAndFormatVTM(n, faces, diff, rollStatusDMG, add, False)
                    elif rolltype == PROGRESSI:
                        if not diff:
                            diff = 6
                        response = rollAndFormatVTM(n, faces, diff, rollStatusProgress, add, False, True)
                    else:
                        raise ValueError(f'Tipo di tiro sconosciuto: {rolltype}')
            
    except ValueError as e:
        response = str(e)
    await atSend(ctx, response)

@bot.command(brief='Lascia che il Greedy Ghost ti saluti.')
async def salut(ctx):
    await atSend(ctx, 'Shalom!')

@bot.command(brief='Pay respect.')
async def respect(ctx):
	await atSend(ctx, ':regional_indicator_f:')

@bot.command(brief='Fa sapere il ping del Bot')
async def ping(ctx):
    await atSend(ctx, f' Ping: {round(bot.latency * 1000)}ms')

@bot.command(aliases=['divinazione' , 'div'] , brief='Presagire il futuro con una domanda' , help = 'Inserire comando + domanda')
async def divina(ctx, *, question):
    responses=['Certamente.',
	 	'Sicuramente.' ,
 		'Probabilmente si.' ,
	 	'Forse.' ,
	  	'Mi sa di no.' ,
		'Probabilmente no.' ,
	 	'Sicuramente no.',
		'Per come la vedo io, si.',
		'Non è scontato.',
		'Meglio chiedere a Rossellini.',
		'Le prospettive sono buone.',
		'Ci puoi contare.',
		'Nebuloso il futuro è.',
		'Sarebbe meglio non risponderti adesso.',
		'Sarebbe uno spoiler troppo grosso.',
		'Non ci contare.',
		'I miei contatti mi dicono di no.'
		]
    await atSend(ctx, f'Domanda: {question}\nRisposta: {random.choice(responses)}')

@bot.command(brief='Testa il database rispondendo con la lista degli amministratori')
async def dbtest(ctx):
    admins = []    
    response = ''
    try:
        admins = dbm.db.select('BotAdmin')
        response = "Database test, listing bot admins..."
        for admin in admins:
            user = await bot.fetch_user(admin['userid'])
            response += f'\n{user}'
    except Exception as e:
        response = f'C\'è stato un problema: {e}'
    await atSend(ctx, response)


@bot.command(brief = "Tira 1d100 per l'inizio giocata", description = "Tira 1d100 per l'inizio giocata")
async def start(ctx, *args):
    await atSend(ctx, f'{random.randint(1, 100)}')

session_start_aliases = ['start', 's']
session_end_aliases = ['end', 'e', 'edn'] # ehehehehe
@bot.command(brief='Controlla le sessioni di gioco', description = ".session: informazioni sulla sessione\n.session start <nomecronaca>: inizia una sessione (richiede essere admin o storyteller della cronaca da iniziare)\n.session end: termina la sessione (richiede essere admin o storyteller della cronaca da terminare)\n\n Le sessioni sono basate sui canali: un canale può ospitare una sessione alla volta, ma la stessa cronaca può avere sessioni attive in più canali.")
async def session(ctx, *args):
    response = ''
    # find chronicle first? yes cause i want info about it
    sessions = dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
    if len(args) == 0:
        if len(sessions):
            chronicle = dbm.db.select('Chronicle', where='id=$chronicle', vars=dict(chronicle=sessions[0]['chronicle']))
            cn = chronicle[0]['name']
            response = f"Sessione attiva: {cn}"
        else:
            response = "Nessuna sessione attiva in questo canale!"
    else:
        action = args[0].lower()       
        if action in session_start_aliases and len(args) == 2:
            chronicle = args[1].lower()
            can_do = len(dbm.db.select('BotAdmin',  where='userid = $userid', vars=dict(userid=ctx.message.author.id))) + len(dbm.db.select('StoryTellerChronicleRel', where='storyteller = $userid and chronicle=$chronicle' , vars=dict(userid=ctx.message.author.id, chronicle = chronicle)))
            if len(sessions):
                response = "C'è già una sessione in corso in questo canale"
            elif can_do:
                dbm.db.insert('GameSession', chronicle=chronicle, channel=ctx.channel.id)
                response = f'Sessione iniziata per la cronaca {chronicle}'
                # todo lista dei pg?
            else:
                response = "Non hai il ruolo di Storyteller per la questa cronaca"
        elif action in session_end_aliases and len(args) == 1:
            if len(sessions):
                isAdmin = len(dbm.db.select('BotAdmin',  where='userid = $userid', vars=dict(userid=ctx.message.author.id)))
                st = dbm.db.query('select sc.chronicle from StoryTellerChronicleRel sc join GameSession gs on (sc.chronicle = gs.chronicle) where gs.channel=$channel and sc.storyteller = $st', vars=dict(channel=ctx.channel.id, st=ctx.message.author.id))
                can_do = isAdmin + len(st)
                if can_do:
                    n = dbm.db.delete('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
                    if n:
                        response = f'sessione terminata'
                    else: # non dovrebbe mai accadere
                        response = f'la cronaca non ha una sessione aperta in questo canale'
                else:
                    response = "Non hai il ruolo di Storyteller per la questa cronaca"
            else:
                response = "Nessuna sessione attiva in questo canale!"       
        else:
            response = "Stai usando il comando in modo improprio"
    await atSend(ctx, response)

damage_types = ["a", "l", "c"]

def defaultTraitFormatter(trait):
    return f"Oh no! devo usare il formatter di default!\n{trait['name']}: {trait['cur_value']}/{trait['max_value']}/{trait['pimp_max']}, text: {trait['text_value']}"

def prettyDotTrait(trait):
    pretty = f"{trait['name']}: {trait['cur_value']}/{trait['max_value']}\n"
    pretty += ":red_circle:"*min(trait['cur_value'], trait['max_value'])
    if trait['cur_value']<trait['max_value']:
        pretty += ":orange_circle:"*(trait['max_value']-trait['cur_value'])
    if trait['cur_value']>trait['max_value']:
        pretty += ":green_circle:"*(trait['cur_value']-trait['max_value'])
    max_dots = max(trait['pimp_max'], 5)
    if trait['cur_value'] < max_dots:
        pretty += ":white_circle:"*(max_dots-max(trait['max_value'], trait['cur_value']))
    return pretty

healthToEmoji = {
    'c': '<:hl_bashing:815338465368604682>',
    'l': '<:hl_lethal:815338465176715325>',
    'a': '<:hl_aggravated:815338465365458994>',
    #
    ' ': '<:hl_free:815338465348026388>',
    'B': '<:hl_blocked:815338465260077077>'
    }


hurt_levels = [
    "Illeso",
    "Contuso",
    "Graffiato (-1)",
    "Leso (-1)",
    "Ferito (-2)",
    "Straziato (-2)",
    "Menomato (-5)",
    "Incapacitato"
]

def prettyHealth(trait, levels = 7):
    if trait['max_value'] <= 0:
        return 'Non hai ancora inizializzato la tua salute!'
    hs = trait['text_value']
    hs = hs + (" "*(trait['max_value']-len(hs)))
    columns = len(hs) // levels 
    extra = len(hs) % levels
    width = columns + (extra > 0)
    prettytext = 'Salute:'
    cursor = 0
    hurt_level = 0
    for i in range(levels):
        if hs[cursor] != " ":
            hurt_level = i+1
        if i < extra:
            prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], hs[cursor:cursor+width])))
            cursor += width
        else:
            prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], hs[cursor:cursor+columns]+"B"*(extra > 0))))
            cursor += columns
    return hurt_levels[hurt_level] +"\n"+ prettytext

def prettyFDV(trait):
    return defaultTraitFormatter(trait)

blood_emojis = [":drop_of_blood:", ":droplet:"]
will_emojis = [":white_square_button:", ":white_large_square:"]

def prettyMaxPointTracker(trait, emojis, separator = ""):
    pretty = f"{trait['name']}: {trait['cur_value']}/{trait['max_value']}\n"
    pretty += separator.join([emojis[0]]*trait['cur_value'])
    pretty += separator
    pretty += separator.join([emojis[1]]*(trait['max_value']-trait['cur_value']))
    return pretty

def prettyPointAccumulator(trait):
    return f"{trait['name']}: {trait['cur_value']}"

def prettyTextTrait(trait):
    return f"{trait['name']}: {trait['text_value']}"

def prettyGeneration(trait):
    return f"{13 - trait['cur_value']}a generazione\n{prettyDotTrait(trait)}"

def trackerFormatter(trait):
    # formattatori specifici
    if trait['id'] == 'generazione':
        return prettyGeneration
    # formattatori generici
    if trait['textbased']:
        return prettyTextTrait
    elif trait['trackertype']==0:
        return prettyDotTrait
    elif trait['trackertype']==1:
        if trait['id'] == 'sangue':
            return lambda x: prettyMaxPointTracker(x, blood_emojis)
        else:
            return lambda x: prettyMaxPointTracker(x, will_emojis, " ")
    elif trait['trackertype']==2:
        return prettyHealth
    elif trait['trackertype']==3:
        return prettyPointAccumulator
    else:
        return defaultTraitFormatter

async def pc_interact(pc, can_edit, *args):
    response = ''
    if len(args) == 0:
        return f"Stai interpretando {pc['fullname']}"

    trait_id = args[0].lower()
    if len(args) == 1:
        if trait_id.count("+"):
            count = 0
            for tid in trait_id.split("+"):
                count += getTrait(pc['id'], tid)['cur_value']
            return f"{args[0]}: {count}"
        else:
            trait = getTrait(pc['id'], trait_id)
            prettyFormatter = trackerFormatter(trait)
            return prettyFormatter(trait)

    # qui siamo sicuri che c'è un'operazione (o spazzatura)
    if not can_edit:
        return f'A sessione spenta puoi solo consultare le tue statistiche'

    param = "".join(args[1:]) # squish
    operazione = param[0]
    if not operazione in ["+", "-", "="]:
        return "Stai usando il comando in modo improprio"
 
    trait = getTrait(pc['id'], trait_id)
    prettyFormatter = trackerFormatter(trait)
    if trait['pimp_max']==0 and trait['trackertype']==0:
        raise BotException(f"Non puoi modificare il valore corrente di {trait['name']}")
    if trait['trackertype'] != 2:
        n = param[1:]
        if not (n.isdigit() and n != "0"):
            return f'"{n}" non è un intero positivo'
        
        if operazione == "=":
            n = int(param[1:]) - trait['cur_value'] # tricks
        else:
            n = int(param)
        new_val = trait['cur_value'] + n
        max_val = max(trait['max_value'], trait['pimp_max']) 
        if new_val<0:
            raise BotException(f'Non hai abbastanza {trait_id}!')
        elif new_val > max_val and trait['trackertype'] != 3:
            raise BotException(f"Non puoi avere {new_val} {trait['name'].lower()}. Valore massimo: {max_val}")
        #
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=pc['id']), cur_value = trait['cur_value'] + n)
        if u == 1:
            trait = getTrait(pc['id'], trait_id)
            return prettyFormatter(trait)
        else:
            return f'Qualcosa è andato storto, righe aggiornate: {u}'

    # salute
    response = ''
    n = param[1:-1]
    if n == '':
        n = 1
    elif n.isdigit():
        n = int(n)
    elif operazione == "=":
        pass
    else:
        raise BotException(f'"{n}" non è un parametro valido!')
    dmgtype = param[-1].lower()
    new_health = trait['text_value']
    if not dmgtype in damage_types:
        raise BotException(f'"{dmgtype}" non è un tipo di danno valido')
    if operazione == "+":
        rip = False
        for i in range(n): # applico i danni uno alla volta perchè sono un nabbo
            if dmgtype == "c" and new_health.endswith("c"): # non rischio di cambiare la lunghezza
                new_health = new_health[:-1]+"l"
            else:
                if len(new_health) < trait['max_value']: # non ho già raggiunto il massimo
                    if dmgtype == "c":                                        
                        new_health += "c"
                    elif dmgtype == "a":
                        new_health = "a"+new_health
                    else:
                        la = new_health.rfind("a")+1
                        new_health = new_health[:la] + "l" + new_health[la:]
                else:  # oh no
                    convert = False
                    if dmgtype == "c":
                        if trait['cur_value'] > 0: # trick per salvarsi mezzo aggravato
                            trait['cur_value'] = 0
                        else:
                            convert = True
                            trait['cur_value'] = 1
                    elif dmgtype == 'l':
                        convert = True
                    else:
                        rip = True

                    if convert:
                        fl = new_health.find('l')
                        if fl >= 0:
                            new_health = new_health[:fl] + 'a' + new_health[fl+1:]
                        else:
                            rip = True
                    if rip:
                        break
        if new_health.count("a") == trait['max_value']:
            rip = True
        
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=pc['id']), text_value = new_health, cur_value = trait['cur_value'])
        if u != 1 and not rip:
            raise BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
        trait = getTrait(pc['id'], trait_id)
        response = prettyFormatter(trait)
        if rip:
            response += "\n\n RIP"
    elif operazione == "-":
        if dmgtype == "a":
            if new_health.count(dmgtype) < n:
                raise BotException("Non hai tutti quei danni aggravati")
            else:
                new_health = new_health[n:]
        elif dmgtype == "l":
            if new_health.count(dmgtype) < n:
                raise BotException("Non hai tutti quei danni letali")
            else:
                fl = new_health.find(dmgtype)
                new_health = new_health[:fl]+new_health[fl+n:]
        else: # dio can
            for i in range(n):
                if trait['cur_value'] == 0:
                    trait['cur_value'] = 1 # togli il mezzo aggravato
                else:
                    if new_health[-1] == 'c':
                        new_health = new_health[:-1]
                    elif new_health[-1] == 'l':
                        new_health = new_health[:-1]+'c'
                    else:
                        raise BotException("Non hai tutti quei danni contundenti")
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=pc['id']), text_value = new_health, cur_value = trait['cur_value'])
        if u != 1:
            raise BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
        trait = getTrait(pc['id'], trait_id)
        response = prettyFormatter(trait)
    else: # =
        full = param[1:]
        counts = list(map(lambda x: full.count(x), damage_types))
        if sum(counts) !=  len(full):
            raise BotException(f'"{full}" non è un parametro valido!')
        new_health = "".join(list(map(lambda x: x[0]*x[1], zip(damage_types, counts)))) # siamo generosi e riordiniamo l'input
        
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=pc['id']), text_value = new_health, cur_value = 1)
        if u != 1:
            raise BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
        trait = getTrait(pc['id'], trait_id)
        response = prettyFormatter(trait)

    return response

me_description = """.me <NomeTratto> [<Operazione>]

<Nometratto>: Nome del tratto (o somma di tratti)
<Operazione>: +/-/= n (se assente viene invece visualizzato il valore corrente)

-Richiede sessione attiva
-Basato sul valore corrente del Tratto'
"""

@bot.command(brief='Permette ai giocatori di interagire col proprio personaggio durante le sessioni' , help = me_description)
async def me(ctx, *args):
    pc = getActiveChar(ctx)
    response = await pc_interact(pc, True, *args)
    await atSend(ctx, response)

@bot.command(brief='Permette ai giocatori di interagire col proprio personaggio durante le sessioni' , help = "come '.me', ma si può usare in 2 modi:\n\n1) .<nomepg> [argomenti di .me]\n2) .pgmanage <nomepg> [argomenti di .me]")
async def pgmanage(ctx, *args):
    if len(args)==0:
        raise BotException('Specifica un pg!')

    charid = args[0].lower()
    isChar, character = isValidCharacter(charid)
    if not isChar:
        raise BotException(f"Il personaggio {charid} non esiste!")

    # permission checks
    issuer = str(ctx.message.author.id)
    playerid = character['player']
    co = playerid == issuer
    
    st, _ = isStoryteller(issuer) # della cronaca?
    ba, _ = isBotAdmin(issuer)    
    ce = st or ba # can edit
    if co and (not ce):
        #1: unlinked
        ce = ce or not len(dbm.db.select('ChronicleCharacterRel', where='playerchar=$id', vars=dict(id=charid)))
        #2 active session
        ce = ce or len(dbm.db.query("""
SELECT cc.playerchar
FROM GameSession gs
join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
where gs.channel = $channel and cc.playerchar = $charid
""", vars=dict(channel=ctx.channel.id, charid=charid)))
    if not (st or ba or co):
        return # non vogliamo che .rossellini faccia cose
        #raise BotException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Admin o Storyteller")
    
    response = await pc_interact(character, ce, *args[1:])
    await atSend(ctx, response)

async def pgmod_create(ctx, args):
    helptext = "Argomenti: nome breve (senza spazi), menzione al proprietario, nome completo del personaggio"
    if len(args) < 3:
        return helptext
    else:
        chid = args[0].lower()
        owner = args[1]
        if not (owner.startswith("<@!") and owner.endswith(">")):
            raise BotException("Menziona il proprietario del personaggio con @nome")
        owner = owner[3:-1]
        fullname = " ".join(list(args[2:]))

        # permission checks
        issuer = str(ctx.message.author.id)
        if issuer != owner: # chiunque può crearsi un pg, ma per crearlo a qualcun'altro serve essere ST/admin
            st, _ = isStoryteller(issuer)
            ba, _ = isBotAdmin(issuer)
            if not (st or ba):
                raise BotException("Per creare un pg ad un altra persona è necessario essere Admin o Storyteller")
        
        t = dbm.db.transaction()
        try:
            if not len(dbm.db.select('People', where='userid=$userid', vars=dict(userid=owner))):
                user = await bot.fetch_user(owner)
                dbm.db.insert('People', userid=owner, name=user.name)
            dbm.db.insert('PlayerCharacter', id=chid, owner=owner, player=owner, fullname=fullname)
            dbm.db.query("""
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
    and pc.id = $pcid;
""", vars = dict(pcid=chid))
        except:
            t.rollback()
            raise
        else:
            t.commit()
            return f'Il personaggio {fullname} è stato inserito!'

async def pgmod_chronicleAdd(ctx, args):
    helptext = "Argomenti: nome breve del pg, nome breve della cronaca"
    if len(args) != 2:
        return helptext
    else:
        charid = args[0].lower()
        isChar, character = isValidCharacter(charid)
        if not isChar:
            raise BotException(f"Il personaggio {charid} non esiste!")
        chronid = args[1].lower()
        chronicles = dbm.db.select('Chronicle', where='id=$id', vars=dict(id=chronid))
        if not len(chronicles):
            raise BotException(f"La cronaca {chronid} non esiste!")
        chronicle = chronicles[0]

        # permission checks
        issuer = str(ctx.message.author.id)
        st, _ = isChronicleStoryteller(issuer, chronicle['id'])
        ba, _ = isBotAdmin(issuer)
        if not (st or ba):
            raise BotException("Per associare un pg ad una cronaca necessario essere Admin o Storyteller di quella cronaca")
        
        # todo check link esistente
        dbm.db.insert("ChronicleCharacterRel", chronicle=chronid, playerchar=charid)
        return f"{character['fullname']} ora gioca a {chronicle['name']}"


async def pgmod_traitAdd(ctx, args):
    helptext = "Argomenti: nome breve del pg, nome breve del tratto, valore"
    if len(args) < 3:
        return helptext
    else:
        charid = args[0].lower()
        traitid = args[1].lower()
        isChar, character = isValidCharacter(charid)
        if not isChar:
            raise BotException(f"Il personaggio {charid} non esiste!")

        # permission checks
        issuer = str(ctx.message.author.id)
        ownerid = character['owner']
        
        st, _ = isStoryteller(issuer) # della cronaca?
        ba, _ = isBotAdmin(issuer)
        co = False
        if ownerid == issuer and not (st or ba):
            #1: unlinked
            co = co or not len(dbm.db.select('ChronicleCharacterRel', where='playerchar=$id', vars=dict(id=charid)))
            #2 active session
            co = co or len(dbm.db.query("""
SELECT cc.playerchar
FROM GameSession gs
join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
where gs.channel = $channel and cc.playerchar = $charid
""", vars=dict(channel=ctx.channel.id, charid=charid)))
        if not (st or ba or co):
            raise BotException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Admin o Storyteller")

        istrait, trait = isValidTrait(traitid)
        if not istrait:
            raise BotException(f"Il tratto {traitid} non esiste!")
        
        ptraits = dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']))
        if len(ptraits):
            raise BotException(f"{character['fullname']} ha già il tratto {trait['name']} ")
        
        ttype = dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        if ttype['textbased']:
            textval = " ".join(args[2:])
            dbm.db.insert("CharacterTrait", trait=traitid, playerchar=charid, cur_value = 0, max_value = 0, text_value = textval, pimp_max = 0)
            return f"{character['fullname']} ora ha {trait['name']} {textval}"
        else:
            pimp = 6 if trait['traittype'] in ['fisico', 'sociale', 'mentale'] else 0
            dbm.db.insert("CharacterTrait", trait=traitid, playerchar=charid, cur_value = args[2], max_value = args[2], text_value = "", pimp_max = pimp)
            return f"{character['fullname']} ora ha {trait['name']} {args[2]}"

async def pgmod_traitMod(ctx, args):
    helptext = "Argomenti: nome breve del pg, nome breve del tratto, nuovo valore"
    if len(args) < 3:
        return helptext
    else:
        charid = args[0].lower()
        isChar, character = isValidCharacter(charid)
        if not isChar:
            raise BotException(f"Il personaggio {charid} non esiste!")

        # permission checks
        issuer = str(ctx.message.author.id)
        ownerid = character['owner']
        
        st, _ = isStoryteller(issuer) # della cronaca?
        ba, _ = isBotAdmin(issuer)
        co = False
        if ownerid == issuer and not (st or ba):
            #1: unlinked
            co = co or not len(dbm.db.select('ChronicleCharacterRel', where='playerchar=$id', vars=dict(id=charid)))
            #2 active session
            co = co or len(dbm.db.query("""
SELECT cc.playerchar
FROM GameSession gs
join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
where gs.channel = $channel and cc.playerchar = $charid
""", vars=dict(channel=ctx.channel.id, charid=charid)))
        if not (st or ba or co):
            raise BotException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Admin o Storyteller")

        traitid = args[1].lower()
        istrait, trait = isValidTrait(traitid)
        if not istrait:
            raise BotException(f"Il tratto {traitid} non esiste!")
        
        ptraits = dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']))
        if not len(ptraits):
            raise BotException(f"{character['fullname']} non ha il tratto {trait['name']} ")
        ttype = dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        if ttype['textbased']:
            textval = " ".join(args[2:])
            dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']), text_value = textval)
            return f"{character['fullname']} ora ha {trait['name']} {textval}"
        else:
            dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']), cur_value = args[2], max_value = args[2])
            return f"{character['fullname']} ora ha {trait['name']} {args[2]}"

pgmod_subcommands = {
    "create": [pgmod_create, "Crea un personaggio"],
    "link": [pgmod_chronicleAdd, "Aggiunge un personaggio ad una cronaca"],
    "addt": [pgmod_traitAdd, "Aggiunge tratto ad un personaggio"],
    "modt": [pgmod_traitMod, "Modifica un tratto di un personaggio"]
    }
pgmod_longdescription = "\n".join(list(map(lambda x: botcmd_prefixes[0]+"pgmod "+x+" [arg1, ...]: "+pgmod_subcommands[x][1], pgmod_subcommands.keys()))) + "\n\nInvoca un sottocomando senza argomenti per avere ulteriori informazioni sugli argomenti"

@bot.command(brief='Crea e modifica personaggi', description = pgmod_longdescription)
async def pgmod(ctx, *args):
    response = 'Azioni disponibili (invoca una azione senza argomenti per conoscere il funzionamento):\n'
    if len(args) == 0:
        response += pgmod_longdescription
    else:
        subcmd = args[0]
        if subcmd in pgmod_subcommands:
            response = await pgmod_subcommands[subcmd][0](ctx, args[1:])
        else:
            response = f'"{subcmd}" non è un sotttocomando valido!\n'+pgmod_longdescription

    await atSend(ctx, response)

##

async def gmadm_listChronicles(ctx, args):
    # voglio anche gli ST collegati
    return "non implementato"


async def gmadm_newChronicle(ctx, args):
    helptext = "Argomenti: <id> <nome completo> \n\nId non ammette spazi."
    if len(args) < 2:
        return helptext
    else:
        shortname = args[0].lower()
        fullname = " ".join(list(args[1:])) # squish

        # permission checks
        issuer = str(ctx.message.author.id)
        st, _ = isStoryteller(issuer) # della cronaca?
        # no botadmin perchè non è necessariente anche uno storyteller e dovrei faren check in più e non ho voglia
        if not (st):
            raise BotException("Per creare una cronaca è necessario essere Storyteller")

        # todo existence
        t = dbm.db.transaction()
        try:
            dbm.db.insert("Chronicle", id=shortname, name = fullname)
            dbm.db.insert("StoryTellerChronicleRel", storyteller=issuer, chronicle=shortname)
        except:
            t.rollback()
            raise
        else:
            t.commit()
            issuer_user = await bot.fetch_user(issuer)
            return f"Cronaca {fullname} inserita ed associata a {issuer_user}"

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

async def gmadm_newTrait(ctx, args):
    if len(args) < 5:
        helptext = "Argomenti: <id> <tipo> <tracker> <standard> <nome completo>\n\n"
        helptext += "Gli id non ammettono spazi.\n\n"
        helptext += "<standard> ammette [y, s, 1] per Sì e [n, 0] per No\n\n"
        ttypes = dbm.db.select('TraitType', what = "id, name")
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
        return helptext
    else:
        # permission checks
        issuer = ctx.message.author.id
        st, _ = isStoryteller(issuer)
        ba, _ = isBotAdmin(issuer)
        if not (st or ba):
            raise BotException("Per creare un tratto è necessario essere Admin o Storyteller")
        
        traitid = args[0].lower()
        istrait, trait = isValidTrait(traitid)
        if istrait:
            raise BotException(f"Il tratto {traitid} esiste già!")

        traittypeid = args[1].lower()
        istraittype, traittype = isValidTraitType(traittypeid)
        if not istraittype:
            raise BotException(f"Il tipo di tratto {traittypeid} non esiste!")

        if not args[2].isdigit():
            raise BotException(f"{args[2]} non è un intero >= 0!")
        tracktype = int(args[2])
        if not tracktype in [0, 1, 2, 3]: # todo dehardcode
            raise BotException(f"{tracktype} non è tracker valido!")

        stdarg = args[3].lower()
        std = stdarg in ['y', 's', '1']
        if not std and not stdarg in ['n', '0']:
            raise BotException(f"{stdarg} non è un'opzione valida")
        
        traitname = " ".join(args[4:])
        dbm.db.insert("Trait", id = traitid, name = traitname, traittype = traittypeid, trackertype = tracktype, standard = std, ordering = 1.0)

        response = f'Il tratto {traitname} è stato inserito'
        # todo: se std, aggiungilo a tutti i pg
        if std:
            t = dbm.db.transaction()
            try:
                dbm.db.query(query_addTraitToPCs, vars = dict(traitid=traitid))
            except:
                t.rollback()
                raise
            else:
                t.commit()
                response +=  f'\nIl nuovo talento standard {traitname} è stato assegnato ai personaggi!'

        return response

async def gmadm_updateTrait(ctx, args):
    if len(args) < 6:
        helptext = "Argomenti: <vecchio_id> <nuovo_id> <tipo> <tracker> <standard> <nome completo>\n\n"
        helptext += "Gli id non ammettono spazi.\n\n"
        helptext += "<standard> ammette [y, s, 1] per Sì e [n, 0] per No\n\n"
        ttypes = dbm.db.select('TraitType', what = "id, name")
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
        return helptext
    else:
        # permission checks
        issuer = ctx.message.author.id
        st, _ = isStoryteller(issuer)
        ba, _ = isBotAdmin(issuer)
        if not (st or ba):
            raise BotException("Per creare un tratto è necessario essere Admin o Storyteller")

        old_traitid = args[0].lower()
        istrait, old_trait = isValidTrait(old_traitid)
        if not istrait:
            raise BotException(f"Il tratto {old_traitid} non esiste!")
        
        new_traitid = args[1].lower()
        istrait, new_trait = isValidTrait(new_traitid)
        if istrait and (old_traitid!=new_traitid):
            raise BotException(f"Il tratto {new_traitid} esiste già!")

        traittypeid = args[2].lower()
        istraittype, traittype = isValidTraitType(traittypeid)
        if not istraittype:
            raise BotException(f"Il tipo di tratto {traittypeid} non esiste!")

        if not args[3].isdigit():
            raise BotException(f"{args[2]} non è un intero >= 0!")
        tracktype = int(args[3])
        if not tracktype in [0, 1, 2, 3]: # todo dehardcode
            raise BotException(f"{tracktype} non è tracker valido!")

        stdarg = args[4].lower()
        std = stdarg in ['y', 's', '1']
        if not std and not stdarg in ['n', '0']:
            raise BotException(f"{stdarg} non è un'opzione valida")

        traitname = " ".join(args[5:])
        dbm.db.update("Trait", where= 'id = $oldid' , vars=dict(oldid = old_traitid), id = new_traitid, name = traitname, traittype = traittypeid, trackertype = tracktype, standard = std, ordering = 1.0)

        response = f'Il tratto {traitname} è stato inserito'
        # todo: se std, aggiungilo a tutti i pg
        if std and not old_trait['standard']:
            t = dbm.db.transaction()
            try:
                dbm.db.query(query_addTraitToPCs_safe, vars = dict(traitid=new_traitid))
            except:
                t.rollback()
                raise
            else:
                t.commit()
                response +=  f'\nIl nuovo talento standard {traitname} è stato assegnato ai personaggi!'
        elif not std and old_trait['standard']:
            t = dbm.db.transaction()
            try:
                dbm.db.query("""
    delete from CharacterTrait
    where trait = $traitid and max_value = 0 and cur_value = 0 and text_value = '';
    """, vars = dict(traitid=new_traitid))
            except:
                t.rollback()
                raise
            else:
                t.commit()
                response +=  f'\nIl talento {traitname} è stato rimosso dai personaggi che non avevano pallini'

        return response

async def gmadm_deleteTrait(ctx, args):
    return "non implementato"

async def gmadm_searchTrait(ctx, args):
    if len(args) == 0:
        helptext = "Argomenti: parte del nome breve o nome completo del tratto"
        return helptext
    else:
        searchstring = "%" + (" ".join(args)) + "%"
        lower_version = searchstring.lower()
        traits = dbm.db.select("Trait", where="id like $search_lower or name like $search_string", vars=dict(search_lower=lower_version, search_string = searchstring))
        if not len(traits):
            return 'Nessun match!'
        response = 'Tratti trovati:\n'
        for trait in traits:
            response += f"\n{trait['id']}: {trait['name']}"
        return response


gameAdmin_subcommands = {
    "listChronicles": [gmadm_listChronicles, "Elenca le cronache"],
    "newChronicle": [gmadm_newChronicle, "Crea una nuova cronaca associata allo ST che invoca il comando"],
    "newTrait": [gmadm_newTrait, "Crea nuovo tratto"],
    "updt": [gmadm_updateTrait, "Modifica un tratto"],
    "delet": [gmadm_deleteTrait, "Cancella un tratto"],
    "searcht": [gmadm_searchTrait, "Cerca un tratto"]
    # todo: nomina storyteller, associa storyteller a cronaca
    # todo: dissociazioni varie
    }
gameAdmin_longdescription = "\n".join(list(map(lambda x: botcmd_prefixes[0]+"gmadm "+x+" [arg1, ...]: "+gameAdmin_subcommands[x][1], gameAdmin_subcommands.keys())))  + "\n\nInvoca un sottocomando senza argomenti per avere ulteriori informazioni sugli argomenti"

@bot.command(brief="Gestione dell'ambiente di gioco", description = gameAdmin_longdescription)
async def gmadm(ctx, *args):
    response = 'Azioni disponibili (invoca una azione senza argomenti per conoscere il funzionamento):\n'
    if len(args) == 0:
        response += gameAdmin_longdescription
    else:
        subcmd = args[0]
        if subcmd in gameAdmin_subcommands:
            response = await gameAdmin_subcommands[subcmd][0](ctx, args[1:])
        else:
            response = f'"{subcmd}" non è un sotttocomando valido!\n'+gameAdmin_longdescription
        
    await atSend(ctx, response)

bot.run(TOKEN)
