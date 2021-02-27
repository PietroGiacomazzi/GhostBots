#!/usr/bin/env python3

from discord.ext import commands
import random, sys, configparser, web
import support.vtm_res as vtm_res

if len(sys.argv) == 1:
    print("Specifica un file di configurazione!")
    sys.exit()

config = configparser.ConfigParser()
config.read(sys.argv[1])

TOKEN = config['Discord']['token']


SOMMA_CMD = ["somma", "s"]
DIFF_CMD = ["diff", "d"]
MULTI_CMD = ["multi", "m"]
DANNI_CMD = ["danni", "dmg"]
PROGRESSI_CMD = ["progressi", "p"]
SPLIT_CMD = ["split"]

NORMALE = 0
SOMMA = 1
DANNI = 2
PROGRESSI = 3

max_dice = 100
max_faces = 100


die_emoji = {
    2: ":two:",
    3: ":three",
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
        self.db = web.database(dbn=config['type'], user=config['user'], pw=config['pw'], db=config['database'])


dbm = DBManager(config['Database'])

bot = commands.Bot(['gg', '.'])

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

ignored_errors = [commands.errors.CommandNotFound]

@bot.event
async def on_command_error(ctx, error):
    #logging.warning(traceback.format_exc()) #logs the error
    if not type(error) in ignored_errors:
        await atSend(ctx, f'Congratulazioni! hai trovato un modo per rompere il comando!')
        #print("debug user:", int(config['Discord']['debuguser']))
        debug_user = await bot.fetch_user(int(config['Discord']['debuguser']))
        await debug_user.send(f'Il messaggio:\n\n{ctx.message.content}\n\n ha causato l\'errore di tipo {type(error)}:\n\n{error}')
    else:
        print(error)
        

@bot.command(name='coin', help = 'Testa o Croce.')
async def coin(ctx):
    moneta=['Testa' , 'Croce']
    await atSend(ctx, f'{random.choice(moneta)}')

@bot.command(name='roll', help = 'Soon™')
async def roll(ctx, *args):
    #print("roll args:", repr(args))
    try:
        if len(args) == 0:
            raise ValueError("roll cosa diomadonna")
        split = args[0].split("d")
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
                        raise ValueError(f'eeh deciditi')
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
                        raise ValueError(f'eeh deciditi')
                    if len(args) == i+1:
                        raise ValueError(f'multi cosa')
                    if not args[i+1].isdigit():
                        raise ValueError(f'"{args[i+1]}" non è un numero di mosse valido')
                    multi = int(args[i+1])
                    if multi < 2:
                        raise ValueError(f'una multipla deve avere almeno 2 tiri!')
                    if n-multi-(multi-1) <= 0:
                        raise ValueError(f'non hai abbastanza dadi per questo numero di mosse!')
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
                        if sum(filter(lambda x: x[0] == roll_index, split)): # cerco se ho giò splittato questo tiro
                            raise ValueError(f'eeh deciditi')
                        i += 1
                    else: # not an elif because reasons
                        if len(args) < i+3:
                            raise ValueError(f'split prende almeno 2 parametri!')
                    temp = args[i+1:i+3]
                    if not temp[0].isdigit() or temp[0] == "0":
                        raise ValueError(f'"{split[0]}" non è un intero positivo')
                    if not temp[1].isdigit() or temp[1] == "0":
                        raise ValueError(f'"{split[1]}" non è un intero positivo')
                    split.append( [roll_index] + list(map(int, temp)))
                    i += 2
                elif args[i].startswith("+"):
                    raw = args[i][1:]
                    if not raw.isdigit() or raw == "0":
                        raise ValueError(f'"{raw}" non è un intero positivo')
                    add = int(raw)
                else:
                    raise ValueError(f'coes')
                i += 1
            # decido cosa fare
            if multi:
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
                raw_roll = list(map(lambda x: random.randint(1, faces), range(n)))
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
                        response = rollAndFormatVTM(n, faces, diff)
                    elif rolltype == SOMMA:
                        somma = sum(raw_roll)
                        response = f'somma: **{somma}**, tiro: {raw_roll}'
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

@bot.command(brief='sapere il ping del Bot')
async def ping(ctx):
    await atSend(ctx, f' Ping: {round(bot.latency * 1000)}ms')

@bot.command(aliases=['divinazione' , 'div'] , brief='Avere risposte.')
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
    await atSend(ctx, f'Domanda: {question}\nRisposta:{random.choice(responses)}')

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

session_start_aliases = ['start', 's']
session_end_aliases = ['end', 'e', 'edn'] # ehehehehe
@bot.command(brief='Controlla le sessioni di gioco')
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

@bot.command(brief='Permette ai giocatori di interagire col proprio personaggio durante le sessioni')
async def me(ctx, *args):
    # steps: session -> chronicle -> characters
    sessions = dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
    if len(sessions):
        players = dbm.db.query("""
SELECT pc.id, pc.fullname
FROM ChronicleCharacterRel cc
join PlayerCharacter pc on (pc.id = cc.playerchar)
where cc.chronicle = $chronicle and pc.player = $player
""", vars=dict(chronicle=sessions[0]['chronicle'], player=ctx.message.author.id))
        if len(players) == 1:
            if len(args) == 0:
                response = f"Stai interpretando {players[0]['fullname']}"
            else:
                trait_id = args[0].lower()
                traits = dbm.db.select('CharacterTrait',  where='trait = $trait', vars=dict(trait=trait_id))
                if len(traits):
                    trait = traits[0]
                    if len(args) == 1:
                        response = f"{trait_id}: {trait['cur_value']}/{trait['max_value']}"
                    elif len(args) == 2:
                        response = 'not yet'
                    else:
                        response = 'coes'
                else:
                    response = f'Non hai il tratto {trait_id}'
        elif len(players) > 1:
            response = f'Stai interpretando più di un personaggio in questa cronaca, non so a chi ti riferisci!{players}'
        else:
            response = 'Non stai interpretando un personaggio in questa cronaca!'
    else:
        response = 'Nessuna sessione attiva in questo canale!'
    await atSend(ctx, response)

bot.run(TOKEN)
