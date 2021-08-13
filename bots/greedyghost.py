#!/usr/bin/env python3

import os, urllib
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

from discord.ext import commands
import random, sys, configparser, web, traceback, MySQLdb, discord
import support.vtm_res as vtm_res
import support.ghostDB as ghostDB
import support.utils as utils
import lang.lang as lng

if len(sys.argv) == 1:
    print("Specify a configuration file!")
    sys.exit()

print(f"Working directory: {dname}")
if not os.path.exists(sys.argv[1]):
    print(f"The configuration file {sys.argv[1]}does not exist!")
    sys.exit()

config = configparser.ConfigParser()
config.read(sys.argv[1])

TOKEN = config['Discord']['token']


SOMMA_CMD = ["somma", "s", "lapse", "sum"]
DIFF_CMD = ["diff", "diff.", "difficoltà", "difficolta", "d", "difficulty"]
MULTI_CMD = ["multi", "m"]
DANNI_CMD = ["danni", "dmg", "damage"]
PROGRESSI_CMD = ["progressi", "progress"]
SPLIT_CMD = ["split"]
PENALITA_CMD = ["penalita", "penalità", "p", "penalty"]
DADI_CMD = ["dadi", "dice"]

PERMANENTE_CMD = ["permanente", "perm", "permanent"]
SOAK_CMD = ["soak", "assorbi"]
INIZIATIVA_CMD = ["iniziativa", "iniz", "initiative"]
RIFLESSI_CMD = ["riflessi", "r", "reflexes"]
STATISTICS_CMD = ["statistica", "stats", "stat"]

RollCat = utils.enum("DICE", "INITIATIVE", "REFLEXES", "SOAK") # macro categoria che divide le azioni di tiro
RollArg = utils.enum("DIFF", "MULTI", "SPLIT", "ADD", "ROLLTYPE", "PENALITA", "DADI", "PERMANENTE", "STATS") # argomenti del tiro
RollType = utils.enum("NORMALE", "SOMMA", "DANNI", "PROGRESSI") # sottotipo dell'argomento RollType

reset_aliases = ["reset"]

INFINITY = float("inf")

max_dice = int(config['BotOptions']['max_dice'])
max_faces = int(config['BotOptions']['max_faces'])
statistics_samples = int(config['BotOptions']['stat_samples'])

default_language = config['BotOptions']['default_language']
lp = lng.LanguageStringProvider("lang")

def getLanguage(userid, dbm):
    try:
        return dbm.getUserLanguage(userid)
    except ghostDB.DBException:
        return default_language



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

def rollStatusDMG(lid, n):
    if n == 1:
        return lp.get(lid, 'roll_status_dmg_1dmg')
    elif n > 1:
        return lp.get(lid, "roll_status_dmg_ndmg", n) 
    else:
        return lp.get(lid, 'roll_status_dmg_0dmg')

def rollStatusProgress(lid, n):
    if n == 1:
        return lp.get(lid, 'roll_status_prg_1hr')
    elif n > 1:
        return lp.get(lid, 'roll_status_prg_nhr', n) 
    else:
        return lp.get(lid, 'roll_status_prg_0hr')

def rollStatusNormal(lid, n):
    if n == 1:
        return lp.get(lid, 'roll_status_normal_1succ')
    elif n > 1:
        return lp.get(lid, 'roll_status_normal_nsucc', n)
    elif n == 0:
        return lp.get(lid, 'roll_status_normal_fail')
    elif n == -2:
        return lp.get(lid, 'roll_status_normal_dramafail')
    else:
        return lp.get(lid, 'roll_status_normal_critfail')

def rollStatusReflexes(lid, n):
    if n >= 1:
        return lp.get(lid, 'roll_status_hitormiss_success') 
    else:
        return lp.get(lid, 'roll_status_hitormiss_fail')

def rollStatusSoak(lid, n):
    if n == 1:
        return lp.get(lid, 'roll_status_soak_1dmg') 
    elif n > 1:
        return lp.get(lid, 'roll_status_soak_ndmg', n) 
    else:
        return lp.get(lid, 'roll_status_soak_0dmg') 

def rollAndFormatVTM(lid, ndice, nfaces, diff, statusFunc = rollStatusNormal, extra_succ = 0, canceling = True, spec = False, statistics = False):
    if statistics:
        total_successes = 0
        passes = 0
        fails = 0
        critfails = 0
        for i in range(statistics_samples):
            successi, _, _ = vtm_res.roller(ndice, nfaces, diff, canceling, spec)
            if successi > 0:
                passes += 1
                total_successes += (successi + extra_succ)
            elif successi == 0 or successi == -2:
                fails += 1
            else:
                critfails += 1
        response =  lp.get(lid,
            'roll_status_statistics_info',
            statistics_samples,
            ndice,
            nfaces,
            diff,
            extra_succ,
            lp.get(lid, 'roll_status_with') if canceling else lp.get(lid, 'roll_status_without'),
            lp.get(lid, 'roll_status_with') if spec else lp.get(lid, 'roll_status_without'),
            round(100*passes/statistics_samples, 2),
            round(100*(fails+critfails)/statistics_samples, 2),
            round(100*fails/statistics_samples, 2),
            round(100*critfails/statistics_samples, 2),
            round(total_successes/statistics_samples, 2)
        )
        return response
    else:        
        successi, tiro, cancels = vtm_res.roller(ndice, nfaces, diff, canceling, spec)
        pretty = prettyRoll(tiro, diff, cancels)
        successi += extra_succ # posso fare sta roba solo perchè i successi extra vengono usati solo in casi in cui il canceling è spento
        status = statusFunc(lid, successi)
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

def validateTraitName(traitid):
    forbidden_chars = [" ", "+"]
    return sum(map(lambda x: traitid.count(x), forbidden_chars)) == 0

class BotException(Exception): # use this for 'known' error situations
    def __init__(self, msg):
        super(BotException, self).__init__(msg)
    
dbm = ghostDB.DBManager(config['Database'])

botcmd_prefixes = ['.']
bot = commands.Bot(botcmd_prefixes)

#executed once on bot boot
@bot.event
async def on_ready():
    for guild in bot.guilds:
        print(
            f'{bot.user} is connected to the following guilds:\n'
            f'{guild.name} (id: {guild.id})'
        )
    debug_user = await bot.fetch_user(int(config['Discord']['debuguser']))
    await debug_user.send(f'Online!')
    #members = '\n - '.join([member.name for member in guild.members])
    #print(f'Guild Members:\n - {members}')
    #await bot.get_channel(int(config['DISCORD_DEBUG_CHANNEL'])).send("bot is online")

@bot.event
async def on_command_error(ctx, error):
    issuer = ctx.message.author.id
    lid = getLanguage(issuer, dbm)
    ftb = traceback.format_exception(*sys.exc_info()) # broken, because the exception has already been handled
    #print(ftb)
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
            ic, character = dbm.isValidCharacter(charid)
            if ic:
                await pgmanage(ctx, *msgsplit)
            else:
                await atSend(ctx, f'coes')
            return
        except Exception as e:
            error = e
    if isinstance(error, BotException):
        await atSend(ctx, f'{error}')
    elif isinstance(error, ghostDB.DBException):
        await atSend(ctx, lp.formatException(lid, error))
    elif isinstance(error, lng.LangException):
        await atSend(ctx, f'{error}')
    else:
        if isinstance(error, MySQLdb.OperationalError):
            if error.args[0] == 2006:
                await atSend(ctx, f'Il database non ha risposto, riprova per favore')
                dbm.reconnect()
            else:
                await atSend(ctx, f'Errore di database :(')
        elif isinstance(error, MySQLdb.IntegrityError):
            await atSend(ctx, f"L'operazione viola dei vincoli sui dati, non posso farlo")
        else:
            await atSend(ctx, f'Congratulazioni! Hai trovato un modo per rompere il comando!')
        #print("debug user:", int(config['Discord']['debuguser']))
        debug_user = await bot.fetch_user(int(config['Discord']['debuguser']))
        await debug_user.send(f'Il messaggio:\n\n{ctx.message.content}\n\n ha causato l\'errore di tipo {type(error)}:\n\n{error}\n\n{ftb}')


@bot.command(name='coin', help = 'Testa o Croce.')
async def coin(ctx):
    moneta=['Testa' , 'Croce']
    await atSend(ctx, f'{random.choice(moneta)}')

roll_longdescription = """
Comando base
.roll <cosa> <argomento1> <argomento2>...

.roll 10d10                                 -> Tiro senza difficoltà
.roll 10d10 somma                           -> Somma il numero dei tiri
.roll 10d10 diff 6                          -> Tiro con difficoltà specifica
.roll 10d10 danni                           -> Tiro danni
.roll 10d10 +5 danni                        -> Tiro danni con modificatore
.roll 10d10 progressi                       -> Tiro per i progressi del giocatore
.roll 10d10 lapse                           -> Tiro per i progressi in timelapse del giocatore
.roll 10d10 multi 3 diff 6                  -> Tiro multiplo
.roll 10d10 split 6 7                       -> Split a difficoltà separate [6, 7]
.roll 10d10 diff 6 multi 3 split 2 6 7      -> Multipla [3] con split [al 2° tiro] a difficoltà separate [6,7]
.roll 10d10 multi 3 split 2 6 7 split 3 4 5 -> Multipla [3] con split al 2° e 3° tiro

A sessione attiva:

.roll tratto1+tratto2   -> Si può sostituire XdY con una combinazione di tratti (forza, destrezza+schivare...) e verranno prese le statistiche del pg rilevante
.roll iniziativa        -> equivale a .roll 1d10 +(destrezza+prontezza+velocità)
.roll riflessi          -> equivale a .roll volontà diff (10-prontezza)
.roll assorbi           -> equivale a .roll costituzione+robustezza diff 6 danni
.roll <cose> penalita   -> applica la penalità corrente derivata dalla salute
.roll <cose> dadi N     -> modifica il numero di dadi del tiro (N può essere positivo o negativo), utile per modificare un tiro basato sui tratti
.roll <cose> permanente -> usa i valori di scheda e non quelli potenziati/spesi (esempio: ".roll volontà permanente diff 7")

Note sugli spazi in ".roll <cosa> <argomento1> <argomento2>..."

In <cosa> non ci vanno mai spazi (XdY, o tratto1+tratto2)
In <come> bisogna spaziare tutto (multi 6, diff 4).
    Il bot è in grado di leggere anche 2 argomenti attaccati (diff8, multi3) se è una coppia argomento-parametro
"""

def parseDiceExpression_Dice(what):
    split = what.split("d")
    if len(split) > 2:
        raise BotException("Troppe 'd' b0ss")
    if len(split) == 1:
        raise BotException(f'"{split[0]}" non è un\'espressione XdY')
    if split[0] == "":
        split[0] = "1"
    if not split[0].isdigit():
        raise BotException(f'"{split[0]}" non è un numero intero positivo')
    if split[1] == "":
        split[1] = "10"
    if not split[1].isdigit():
        raise BotException(f'"{split[1]}" non è un numero intero positivo')
    n = int(split[0])
    faces = int(split[1])
    if n == 0:
        raise BotException(f'{n} non è > 0')
    if  faces == 0:
        raise BotException(f'{faces} non è > 0')
    if n > max_dice:
        raise BotException(f'{n} dadi sono troppi b0ss')
    if faces > max_faces:
        raise BotException(f'{faces} facce sono un po\' tante')
    return RollCat.DICE, n, n, faces, None

def parseDiceExpression_Traits(ctx, lid, what):
    character = dbm.getActiveChar(ctx) # can raise
    split = what.split("+")
    faces = 10
    n = 0
    n_perm = 0
    for trait in split:
        temp = dbm.getTrait_LangSafe(character['id'], trait, lid) 
        n += temp['cur_value']
        n_perm += temp['max_value']
    return RollCat.DICE, n, n_perm, faces, character

# input: l'espressione <what> in .roll <what> [<args>]
# output: tipo di tiro, numero di dadi, numero di dadi (permanente), numero di facce, personaggio
def parseRollWhat(ctx, lid, what):
    n = -1
    faces = -1
    character = None

    # tiri custom 
    if what in INIZIATIVA_CMD:
        return RollCat.INITIATIVE, 1, 1, 10, character
    if what in RIFLESSI_CMD:
        return RollCat.REFLEXES, 1, 1, 10, character
    if what in SOAK_CMD:
        return RollCat.SOAK, 1, 1, 10, character

    try:
        return parseDiceExpression_Dice(what)    
    except BotException as e:
        try:
            return parseDiceExpression_Traits(ctx, lid, what)
        except ghostDB.DBException as edb:
            raise BotException("\n".join(["Non ho capito cosa devo tirare:", f'{e}', f'{lp.formatException(lid, edb)}']) )
        
def validateInteger(args, i, err_msg = 'un intero'):
    try:
        return i, int(args[i])
    except ValueError:
        raise ValueError(f'"{args[i]}" non è {err_msg}')

def validateBoundedInteger(args, i, min_val, max_val, err_msg = "non è nell'intervallo specificato"):
    j, val = validateInteger(args, i)
    if val < min_val or val > max_val:
        raise ValueError(f'{args[i]} {err_msg}')
    return j, val

def validateNumber(args, i, err_msg = 'un intero positivo'):
    if not args[i].isdigit():
        raise ValueError(f'"{args[i]}" non è {err_msg}')
    return i, int(args[i])

def validateBoundedNumber(args, i, min_bound, max_bound = INFINITY, err_msg = "un numero nell'intervallo accettato"):
    _, num = validateNumber(args, i)
    if num > max_bound or num < min_bound:
        raise ValueError(f'{num} non è {err_msg}')
    return i, num

def validateIntegerGreatZero(args, i):
    return validateBoundedNumber(args, i, 1, err_msg = "un intero maggiore di zero")

def validateDifficulty(args, i):
    return validateBoundedNumber(args, i, 2, 10, "una difficoltà valida")

# input: sequenza di argomenti per .roll
# output: dizionario popolato con gli argomenti validati
def parseRollArgs(args_raw):
    parsed = {
        RollArg.ROLLTYPE: RollType.NORMALE # default
        }
    args = list(args_raw)
    # leggo gli argomenti scorrendo args
    i = 0
    while i < len(args):
        if args[i] in SOMMA_CMD:
            parsed[RollArg.ROLLTYPE] = RollType.SOMMA
        elif args[i] in DIFF_CMD:
            if RollArg.DIFF in parsed:
                raise ValueError(f'mi hai già dato una difficoltà')
            if len(args) == i+1:
                raise ValueError(f'diff cosa')
            i, diff = validateDifficulty(args, i+1)
            parsed[RollArg.DIFF] = diff
        elif args[i] in MULTI_CMD:
            if RollArg.SPLIT in parsed:
                raise ValueError(f'multi va specificato prima di split')
            if RollArg.MULTI in parsed:
                raise ValueError(f'Stai tentando di innestare 2 multiple?')
            if len(args) == i+1:
                raise ValueError(f'multi cosa')
            i, multi = validateBoundedNumber(args, i+1, 2, INFINITY, f"multi prende come paramento un numero >= 2")# controlliamo il numero di mosse sotto, dopo aver applicato bonus o penalità al numero di dadi
            parsed[RollArg.MULTI] = multi            
        elif args[i] in DANNI_CMD:
            parsed[RollArg.ROLLTYPE] = RollType.DANNI
        elif args[i] in PROGRESSI_CMD:
            parsed[RollArg.ROLLTYPE] = RollType.PROGRESSI
        elif args[i] in SPLIT_CMD:
            roll_index = 0
            split = []
            if RollArg.SPLIT in parsed: # fetch previous splits
                split = parsed[RollArg.SPLIT]
            if RollArg.MULTI in parsed:
                if len(args) < i+4:
                    raise ValueError(f'split prende almeno 3 parametri con multi!')
                i, temp = validateIntegerGreatZero(args, i+1)
                roll_index = temp-1
                if roll_index >= parsed[RollArg.MULTI]:
                    raise ValueError(f'"Non puoi splittare il tiro {args[i+1]} con multi {multi}')
                if sum(filter(lambda x: x[0] == roll_index, split)): # cerco se ho giò splittato questo tiro
                    raise ValueError(f'Stai già splittando il tiro {roll_index+1}')
            else: # not an elif because reasons
                if len(args) < i+3:
                    raise ValueError(f'split prende almeno 2 parametri!')
            i, d1 = validateIntegerGreatZero(args, i+1)
            i, d2 = validateIntegerGreatZero(args, i+1)
            split.append( [roll_index] + list(map(int, [d1, d2])))
            parsed[RollArg.SPLIT] = split # save the new split
        elif args[i].startswith("+"):
            raw = args[i][1:]
            if raw == "":
                if len(args) == i+1:
                    raise ValueError(f'+ cosa')
                raw = args[i+1] # support for space
                i += 1
            if not raw.isdigit() or raw == "0":
                raise ValueError(f'"{raw}" non è un intero positivo')
            add = int(raw)
            parsed[RollArg.ADD] = add
        elif args[i] in PENALITA_CMD:
            parsed[RollArg.PENALITA] = True
        elif args[i] in DADI_CMD:
            if len(args) == i+1:
                raise ValueError(f'dadi cosa')
            i, val = validateBoundedInteger(args, i+1, -100, +100) # lel 
            parsed[RollArg.DADI] = val
        elif args[i] in PERMANENTE_CMD:
            parsed[RollArg.PERMANENTE] = True
        elif args[i] in STATISTICS_CMD:
            parsed[RollArg.STATS] = True
        else:
            # provo a staccare parametri attaccati
            did_split = False
            idx = 0
            tests = DIFF_CMD+MULTI_CMD+DADI_CMD
            while not did_split and idx < len(tests):
                cmd = tests[idx]
                if args[i].startswith(cmd):
                    try:
                        _ = int(args[i][len(cmd):])
                        args = args[:i] + [cmd, args[i][len(cmd):]] + args[i+1:]
                        did_split = True
                    except ValueError:
                        pass
                idx += 1
            if not did_split: # F
                width = 3
                ht = " ".join(list(args[max(0, i-width):i]) + ['**'+args[i]+'**'] + list(args[min(len(args), i+1):min(len(args), i+width)]))
                raise ValueError(f"L'argomento '{args[i]}' in '{ht}' non mi è particolarmente chiaro")
            else:
                i -= 1 # forzo rilettura
        i += 1
    return parsed

@bot.command(name='roll', aliases=['r', 'tira', 'lancia'], brief = 'Tira dadi', description = roll_longdescription) 
async def roll(ctx, *args):
    issuer = ctx.message.author.id
    lid = getLanguage(issuer, dbm)
    if len(args) == 0:
        raise BotException("roll cosa diomadonna")
    # capisco quanti dadi tirare
    what = args[0].lower()
    action, ndice, ndice_perm, nfaces, character = parseRollWhat(ctx, lid, what)
    
    # leggo e imposto le varie opzioni
    parsed = None
    try:
        parsed = parseRollArgs(args[1:])
    except ValueError as e:
        await atSend(ctx, str(e))
        return
    
    # modifico il numero di dadi
    if RollArg.PERMANENTE in parsed:
        ndice = ndice_perm
    
    if RollArg.PENALITA in parsed:
        if not character:
            character = dbm.getActiveChar(ctx)
        health = dbm.getTrait_LangSafe(character['id'], 'salute', lid)
        penalty, _ = parseHealth(health)
        ndice += penalty[0]

    if RollArg.DADI in parsed:
        ndice += parsed[RollArg.DADI]

    if ndice > max_dice:
        raise BotException("Non puoi tirare più di {max_dice} dadi!")
    if ndice <= 0:
        raise BotException("Devi avere almeno un dado nel tuo pool (pool richiesto: {ndice} dadi)")

    # check n° di mosse per le multiple
    if RollArg.MULTI in parsed:
        multi = parsed[RollArg.MULTI]
        max_moves = int( ((ndice+1)/2) -0.1) # (ndice+1)/2 è il numero di mosse in cui si rompe, non il massimo. togliendo 0.1 e arrotondando per difetto copro sia il caso intero che il caso con .5
        if max_moves == 1:
            raise BotException("Non hai abbastanza dadi per una multipla!")
        elif multi > max_moves:
            raise BotException(f"Non hai abbastanza dadi, puoi arrivare al massimo a {max_moves} azioni con {ndice} dadi!")

    # decido cosa fare
    if len(args) == 1 and action == RollCat.DICE : #simple roll
        raw_roll = list(map(lambda x: random.randint(1, nfaces), range(ndice)))
        await atSend(ctx, repr(raw_roll))
        return

    stats = RollArg.STATS in parsed

    response = ''
    if parsed[RollArg.ROLLTYPE] == RollType.NORMALE and not RollArg.DIFF in parsed and RollArg.ADD in parsed: #se non c'è difficoltà tramuta un tiro in un tiro somma instile dnd
        parsed[RollArg.ROLLTYPE] = RollType.SOMMA
    add = parsed[RollArg.ADD] if RollArg.ADD in parsed else 0
    if action == RollCat.INITIATIVE:
        if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE or RollArg.DIFF in parsed:
            raise BotException("Combinazione di parametri non valida!")
        raw_roll = random.randint(1, nfaces)
        bonuses_log = []
        bonus = add
        if add:
            bonuses_log.append( f'bonus: {add}' )
        try:
            character = dbm.getActiveChar(ctx)
            for traitid in ['prontezza', 'destrezza', 'velocità']:
                try:
                    val = dbm.getTrait_LangSafe(character['id'], traitid, lid)['cur_value']
                    bonus += val
                    bonuses_log.append( f'{traitid}: {val}' )
                except ghostDB.DBException:
                    pass
        except ghostDB.DBException:
            response += 'Nessun personaggio !\n'
        if len(bonuses_log):
            response += (", ".join(bonuses_log)) + "\n"
        final_val = raw_roll+bonus
        response += f'Iniziativa: **{final_val}**, tiro: [{raw_roll}]' + (f'+{bonus}' if bonus else '')
    elif action == RollCat.REFLEXES:
        if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE or RollArg.DIFF in parsed:
            raise BotException("Combinazione di parametri non valida!")
        character = dbm.getActiveChar(ctx)
        volonta = dbm.getTrait_LangSafe(character['id'], 'volonta', lid)['cur_value']
        prontezza = dbm.getTrait_LangSafe(character['id'], 'prontezza', lid)['cur_value']
        diff = 10 - prontezza
        response = f'Volontà corrente: {volonta}, Prontezza: {prontezza} -> {volonta}d{nfaces} diff ({diff} = {nfaces}-{prontezza})\n'
        response += rollAndFormatVTM(lid, volonta, nfaces, diff, rollStatusReflexes, add, statistics = stats)
    elif action == RollCat.SOAK:
        if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or RollArg.ADD in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE:
            raise BotException("Combinazione di parametri non valida!")
        diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
        character = dbm.getActiveChar(ctx)
        pool = dbm.getTrait_LangSafe(character['id'], 'costituzione', lid)['cur_value']
        try:
            pool += dbm.getTrait_LangSafe(character['id'], 'robustezza', lid)['cur_value']
        except ghostDB.DBException:
            pass
        response = rollAndFormatVTM(lid, pool, nfaces, diff, rollStatusSoak, 0, False, statistics = stats)
    elif RollArg.MULTI in parsed:
        multi = parsed[RollArg.MULTI]
        split = []
        if RollArg.SPLIT in parsed:
            split = parsed[RollArg.SPLIT]
        if parsed[RollArg.ROLLTYPE] == RollType.NORMALE:
            response = ""
            if not RollArg.DIFF in parsed:
                raise BotException(f'Si ma mi devi dare una difficoltà')
            for i in range(multi):
                parziale = ''
                ndadi = ndice-i-multi
                split_diffs = findSplit(i, split)
                if len(split_diffs):
                    pools = [(ndadi-ndadi//2), ndadi//2]
                    for j in range(len(pools)):
                        parziale += f'\nTiro {j+1}: '+ rollAndFormatVTM(lid, pools[j], nfaces, split_diffs[j], statistics = stats)
                else:
                    parziale = rollAndFormatVTM(lid, ndadi, nfaces, parsed[RollArg.DIFF], statistics = stats)
                response += f'\nAzione {i+1}: '+parziale # line break all'inizio tanto c'è il @mention
        else:
            raise BotException(f'Combinazione di parametri non supportata')
    else: # 1 tiro solo 
        if RollArg.SPLIT in parsed:
            split = parsed[RollArg.SPLIT]
            if parsed[RollArg.ROLLTYPE] == RollType.NORMALE:
                pools = [(ndice-ndice//2), ndice//2]
                response = ''
                for i in range(len(pools)):
                    parziale = rollAndFormatVTM(lid, pools[i], nfaces, split[0][i+1], statistics = stats)
                    response += f'\nTiro {i+1}: '+parziale
            else:
                raise BotException(f'Combinazione di parametri non supportata')
        else:
            if parsed[RollArg.ROLLTYPE] == RollType.NORMALE: # tiro normale
                if not RollArg.DIFF in parsed:
                    raise BotException(f'Si ma mi devi dare una difficoltà')
                response = rollAndFormatVTM(lid, ndice, nfaces, parsed[RollArg.DIFF], rollStatusNormal, add, statistics = stats)
            elif parsed[RollArg.ROLLTYPE] == RollType.SOMMA:
                raw_roll = list(map(lambda x: random.randint(1, nfaces), range(ndice)))
                somma = sum(raw_roll)+add
                response = f'somma: **{somma}**, tiro: {raw_roll}' + (f'+{add}' if add else '')
            elif parsed[RollArg.ROLLTYPE] == RollType.DANNI:
                diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
                response = rollAndFormatVTM(lid, ndice, nfaces, diff, rollStatusDMG, add, False, statistics = stats)
            elif parsed[RollArg.ROLLTYPE] == RollType.PROGRESSI:
                diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
                response = rollAndFormatVTM(lid, ndice, nfaces, diff, rollStatusProgress, add, False, True, statistics = stats)
            else:
                raise BotException(f'Tipo di tiro sconosciuto: {RollArg.ROLLTYPE}')
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
		'Difficile dare una risposta.',
		'Sarebbe meglio non risponderti adesso.',
		'Sarebbe uno spoiler troppo grosso.',
		'Non ci contare.',
		'I miei contatti mi dicono di no.'
		]
    await atSend(ctx, f'Domanda: {question}\nRisposta: {random.choice(responses)}')


@bot.command(name = 'search', brief = "Cerca un tratto", description = "Cerca un tratto:\n\n .search <termine di ricerca> -> elenco dei risultati")
async def search_trait(ctx, *args):
    response = ''
    if len(args) == 0:
        response = "Specifica un termine di ricerca!"
    else:
        searchstring = "%" + (" ".join(args)) + "%"
        lower_version = searchstring.lower()
        traits = dbm.db.select("Trait", where="id like $search_lower or name like $search_string", vars=dict(search_lower=lower_version, search_string = searchstring))
        if not len(traits):
            response =  'Nessun match!'
        else:
            response = 'Tratti trovati:\n'
            for trait in traits:
                response += f"\n{trait['id']}: {trait['name']}"
    await atSend(ctx, response)

@bot.command(brief = "Richiama l'attenzione dello storyteller", description = "Richiama l'attenzione dello storyteller della cronaca attiva nel canale in cui viene invocato")
async def call(ctx, *args):
    character = dbm.getActiveChar(ctx)
    sts = dbm.getChannelStoryTellers(ctx.channel.id)
    response = f"{character['fullname']} ({ctx.message.author}) richiede la tua attenzione!"
    for st in sts:
        stuser = await bot.fetch_user(st['storyteller'])
        response += f' {stuser.mention}'
    await atSend(ctx, response)


@bot.command(brief = "Tira 1d100 per l'inizio giocata", description = "Tira 1d100 per l'inizio giocata")
async def start(ctx, *args):
    await atSend(ctx, f'{random.randint(1, 100)}')

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
              'star'
              ]
@bot.command(aliases = strat_list, brief = "Tira 1d100 per l'inizio giocata", description = "Tira 1d100 per l'inizio giocata anche se l'invocatore è ubriaco")
async def strat(ctx, *args):
    await atSend(ctx, f'{random.randint(1, 100)}, però la prossima volta scrivilo giusto <3')


@bot.command(brief='Impostazioni di lingua', description = "Permette di cambiare impostazioni di lingua del bot")
async def lang(ctx, *args):
    issuer = ctx.message.author.id
    lid = getLanguage(issuer, dbm)
    if len(args) == 0:
        await atSend(ctx, lp.get(lid, "string_your_lang_is", lid))
    elif len(args) == 1:
        try:
            person = dbm.getUser(issuer)
            dbm.db.update("People", where='userid  = $userid', vars=dict(userid =issuer), langId = args[0])
            lid = args[0]
            await atSend(ctx, lp.get(lid, "string_lang_updated_to", lid))
        except ghostDB.DBException:
            user = await bot.fetch_user(issuer)
            dbm.db.insert('People', userid=issuer, name=user.name, langId = args[0])
            lid = args[0]
            await atSend(ctx, lp.get(lid, "string_lang_updated_to", lid))
    else:
        raise BotException(lp.get(lid, "string_invalid_number_of_parameters"))

@bot.group(brief='Controlla le sessioni di gioco', description = "Le sessioni sono basate sui canali: un canale può ospitare una sessione alla volta, ma la stessa cronaca può avere sessioni attive in più canali.")
async def session(ctx):
    if ctx.invoked_subcommand is None:
        sessions = dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
        if len(sessions):
            chronicle = dbm.db.select('Chronicle', where='id=$chronicle', vars=dict(chronicle=sessions[0]['chronicle']))
            cn = chronicle[0]['name']
            await atSend(ctx, f"Sessione attiva: {cn}")
        else:
            await atSend(ctx, "Nessuna sessione attiva in questo canale!")
        

@session.command(brief = 'Inizia una sessione', description = '.session start <nomecronaca>: inizia una sessione per <nomecronaca> (richiede essere admin o storyteller della cronaca da iniziare) (richiede essere admin o storyteller della cronaca da iniziare)')
async def start(ctx, *args):
    issuer = str(ctx.message.author.id)
    sessions = dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
    chronicleid = args[0].lower()
    st, _ = dbm.isChronicleStoryteller(issuer, chronicleid)
    ba, _ = dbm.isBotAdmin(issuer)
    can_do = st or ba
    #can_do = len(dbm.db.select('BotAdmin',  where='userid = $userid', vars=dict(userid=ctx.message.author.id))) + len(dbm.db.select('StoryTellerChronicleRel', where='storyteller = $userid and chronicle=$chronicle' , vars=dict(userid=ctx.message.author.id, chronicle = chronicle)))
    if len(sessions):
        response = "C'è già una sessione in corso in questo canale"
    elif can_do:
        dbm.db.insert('GameSession', chronicle=chronicleid, channel=ctx.channel.id)
        chronicle = dbm.db.select('Chronicle', where='id=$chronicleid', vars=dict(chronicleid=chronicleid))[0]
        response = f"Sessione iniziata per la cronaca {chronicle['name']}"
        # todo lista dei pg?
    else:
        response = "Non hai il ruolo di Storyteller per la questa cronaca"
    await atSend(ctx, response)

@session.command(name = 'list', brief = 'Elenca le sessioni aperte', description = 'Elenca le sessioni aperte. richiede di essere admin o storyteller')
async def session_list(ctx):
    issuer = ctx.message.author.id
    st, _ = dbm.isStoryteller(issuer) # todo: elenca solo le sue
    ba, _ = dbm.isBotAdmin(issuer)
    if not (st or ba):
        raise BotException("no.")
    
    sessions = dbm.db.select('GameSession').list()
    channels = []
    for s in sessions:
        ch = await bot.fetch_channel(int(s['channel']))
        channels.append(ch)
    lines = []
    #pvt = 0
    for session, channel in zip(sessions, channels):
        if isinstance(channel, discord.abc.GuildChannel):
            lines.append(f"**{session['chronicle']}** in: {channel.category}/{channel.name}")
        #elif isinstance(channel, discord.abc.PrivateChannel):
        #    pvt += 1
    if not len(lines):
        lines.append("Nessuna!")
    response = "Sessioni attive:\n" + ("\n".join(lines))
    await atSend(ctx, response)
    

@session.command(brief = 'Termina la sessione corrente', description = 'Termina la sessione corrente. Richiede di essere admin o storyteller della sessione in corso.')
async def end(ctx):
    response = ''
    issuer = str(ctx.message.author.id)
    sessions = dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
    if len(sessions):
        ba, _ = dbm.isBotAdmin(issuer)
        st = dbm.db.query('select sc.chronicle from StoryTellerChronicleRel sc join GameSession gs on (sc.chronicle = gs.chronicle) where gs.channel=$channel and sc.storyteller = $st', vars=dict(channel=ctx.channel.id, st=ctx.message.author.id))
        can_do = ba or bool(len(st))
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
    await atSend(ctx, response)

damage_types = ["a", "l", "c"]

def defaultTraitFormatter(trait):
    return f"Oh no! devo usare il formatter di default!\n{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}/{trait['pimp_max']}, text: {trait['text_value']}"

def prettyDotTrait(trait):
    pretty = f"{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}\n"
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

hurt_levels_vampire = [
    (0, "Illeso"),
    (0, "Contuso"),
    (-1, "Graffiato"),
    (-1, "Leso"),
    (-2, "Ferito"),
    (-2, "Straziato"),
    (-5, "Menomato"),
    (-INFINITY, "Incapacitato"),
]


def parseHealth(trait, levels_list = hurt_levels_vampire):
    if trait['max_value'] <= 0:
        return 'Non hai ancora inizializzato la tua salute!'
    hs = trait['text_value']
    hs = hs + (" "*(trait['max_value']-len(hs)))
    levels = len(levels_list) - 1 
    columns = len(hs) // levels 
    extra = len(hs) % levels
    width = columns + (extra > 0)
    cursor = 0
    hurt_level = 0
    health_lines = []
    for i in range(levels):
        if hs[cursor] != " ":
            hurt_level = i+1
        if i < extra:
            health_lines.append(hs[cursor:cursor+width])#prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], hs[cursor:cursor+width])))
            cursor += width
        else:
            health_lines.append(hs[cursor:cursor+columns]+"B"*(extra > 0)) #prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], hs[cursor:cursor+columns]+"B"*(extra > 0))))
            cursor += columns
    #return hurt_levels[hurt_level] +"\n"+ prettytext
    return hurt_levels_vampire[hurt_level], health_lines

def prettyHealth(trait, levels_list = hurt_levels_vampire):
    penalty, parsed = parseHealth(trait, levels_list)
    prettytext = f'{trait["traitName"]}:'
    for line in parsed:
        prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], line)))
    return f'{penalty[1]} ({penalty[0]})' +"\n"+ prettytext

def prettyFDV(trait):
    return defaultTraitFormatter(trait)

blood_emojis = [":drop_of_blood:", ":droplet:"]
will_emojis = [":white_square_button:", ":white_large_square:"]

def prettyMaxPointTracker(trait, emojis, separator = ""):
    pretty = f"{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}\n"
    pretty += separator.join([emojis[0]]*trait['cur_value'])
    pretty += separator
    pretty += separator.join([emojis[1]]*(trait['max_value']-trait['cur_value']))
    return pretty

def prettyPointAccumulator(trait):
    return f"{trait['traitName']}: {trait['cur_value']}"

def prettyTextTrait(trait):
    return f"{trait['traitName']}: {trait['text_value']}"

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

async def pc_interact(ctx, pc, can_edit, *args):
    issuer = ctx.message.author.id
    lid = getLanguage(issuer, dbm)
    response = ''
    if len(args) == 0:
        parsed = list(urllib.parse.urlparse(config['Website']['website_url'])) # load website url
        parsed[4] = urllib.parse.urlencode({'character': pc['id']}) # fill query
        unparsed = urllib.parse.urlunparse(tuple(parsed)) # recreate url
        return f"Personaggio: {pc['fullname']}\nScheda: {unparsed}"

    trait_id = args[0].lower()
    if len(args) == 1:
        if trait_id.count("+"):
            _, count, _, _, _ = parseDiceExpression_Traits(ctx, lid, trait_id)
            #count = 0
            #for tid in trait_id.split("+"):
            #    count += dbm.getTrait(pc['id'], tid)['cur_value']
            return f"{args[0]}: {count}"
        else:
            trait = dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
            prettyFormatter = trackerFormatter(trait)
            return prettyFormatter(trait)

    # qui siamo sicuri che c'è un'operazione (o spazzatura)
    if not can_edit:
        return f'A sessione spenta puoi solo consultare le tue statistiche'

    param = "".join(args[1:]) # squish
    operazione = None
    if param in reset_aliases:
        operazione = "r"
    else:
        operazione = param[0]
        if not operazione in ["+", "-", "="]:
            return f'Operazione "{operazione}" non supportata'

    trait = dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
    #trait = dbm.getTrait(pc['id'], trait_id)
    prettyFormatter = trackerFormatter(trait)
    if trait['pimp_max']==0 and trait['trackertype']==0:
        raise BotException(f"Non puoi modificare il valore corrente di {trait['traitName']}")
    if trait['trackertype'] != 2:
        n = None
        if operazione != "r":
            n = param[1:]
            if not (n.isdigit()):
                return f'"{n}" non è un intero >= 0'
            
        if operazione == "r":
            if trait['trackertype'] == 1 or trait['trackertype'] == 0:
                n = trait['max_value'] - trait['cur_value']
            elif trait['trackertype'] == 3:
                n = - trait['cur_value']
            else:
                raise BotException(f"Tracker {trait['trackertype']} non supportato")
        elif operazione == "=":
            n = int(param[1:]) - trait['cur_value'] # tricks
        else:
            n = int(param)
        new_val = trait['cur_value'] + n
        max_val = max(trait['max_value'], trait['pimp_max']) 
        if new_val<0:
            raise BotException(f'Non hai abbastanza {trait["traitName"].lower()}!')
        elif new_val > max_val and trait['trackertype'] != 3:
            raise BotException(f"Non puoi avere {new_val} {trait['traitName'].lower()}. Valore massimo: {max_val}")
        #
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=pc['id']), cur_value = new_val)
        dbm.log(ctx.message.author.id, pc['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_val, trait['cur_value'], ctx.message.content)
        if u == 1:
            trait = dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
            return prettyFormatter(trait)
        elif u == 0:
            trait = dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
            return prettyFormatter(trait)+'\n(nessuna modifica effettuata)'
        else:
            return f'Qualcosa è andato storto, righe aggiornate:  {u}'

    # salute
    response = ''
    n = param[1:-1]
    if n == '':
        n = 1
    elif n.isdigit():
        n = int(n)
    elif operazione == "=" or operazione == "r":
        pass
    else:
        raise BotException(f'"{n}" non è un parametro valido!')
    dmgtype = param[-1].lower()
    new_health = trait['text_value']
    if (not dmgtype in damage_types) and operazione != "r":
        raise BotException(f'"{dmgtype}" non è un tipo di danno valido')
    if operazione == "r":
        new_health = ""
        
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=pc['id']), text_value = new_health, cur_value = trait['cur_value'])
        dbm.log(ctx.message.author.id, pc['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_health, trait['text_value'], ctx.message.content)
        if u != 1:
            raise BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
        trait = dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
        response = prettyFormatter(trait)        
    elif operazione == "+":
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
        
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=pc['id']), text_value = new_health, cur_value = trait['cur_value'])
        dbm.log(ctx.message.author.id, pc['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_health, trait['text_value'], ctx.message.content)
        if u != 1 and not rip:
            raise BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
        trait = dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
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
            if (int(trait['cur_value']) == 0 + new_health.count(dmgtype)+new_health.count("l")*2) < n:
                raise BotException("Non hai tutti quei danni contundenti")
            for i in range(n):
                if trait['cur_value'] == 0:
                    trait['cur_value'] = 1 # togli il mezzo aggravato
                else:
                    if new_health[-1] == 'c':
                        new_health = new_health[:-1]
                    elif new_health[-1] == 'l':
                        new_health = new_health[:-1]+'c'
                    else:
                        raise BotException("Non hai tutti quei danni contundenti")# non dovrebbe mai succedere
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=pc['id']), text_value = new_health, cur_value = trait['cur_value'])
        dbm.log(ctx.message.author.id, pc['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_health, trait['text_value'], ctx.message.content)
        if u != 1:
            raise BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
        trait = dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
        response = prettyFormatter(trait)
    else: # =
        full = param[1:]
        counts = list(map(lambda x: full.count(x), damage_types))
        if sum(counts) !=  len(full):
            raise BotException(f'"{full}" non è un parametro valido!')
        new_health = "".join(list(map(lambda x: x[0]*x[1], zip(damage_types, counts)))) # siamo generosi e riordiniamo l'input
        
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=pc['id']), text_value = new_health, cur_value = 1)
        dbm.log(ctx.message.author.id, pc['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_health, trait['text_value'], ctx.message.content)
        if u != 1:
            raise BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
        trait = dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
        response = prettyFormatter(trait)

    return response

me_description = """.me <NomeTratto> [<Operazione>]

<Nometratto>: Nome del tratto (o somma di tratti)
<Operazione>: +n / -n / =n / reset
    (se <Operazione> è assente viene invece visualizzato il valore corrente)

- Richiede sessione attiva nel canale per capire di che personaggio si sta parlando
- Basato sul valore corrente del tratto (potenziamenti temporanei, risorse spendibili...)
- Per modificare il valore "vero" di un tratto, vedi .pgmod
"""

@bot.command(brief='Permette ai giocatori di interagire col proprio personaggio durante le sessioni' , help = me_description)
async def me(ctx, *args):
    pc = dbm.getActiveChar(ctx)
    response = await pc_interact(ctx, pc, True, *args)
    await atSend(ctx, response)

pgmanage_description = """.pgmanage <nomepg> <NomeTratto> [<Operazione>]

<nomepg>: Nome breve del pg
<Nometratto>: Nome del tratto (o somma di tratti)
<Operazione>: +n / -n / =n / reset
    (se <Operazione> è assente viene invece visualizzato il valore corrente)

- Funziona esattamente come '.me', ma funziona anche fuori sessione (solo per consultare i valori).
- Si può usare in 2 modi:
    1) .<nomepg> [argomenti di .me]
    2) .pgmanage <nomepg> [argomenti di .me]
"""

@bot.command(brief='Permette ai giocatori di interagire col proprio personaggio durante le sessioni' , help = pgmanage_description)
async def pgmanage(ctx, *args):
    if len(args)==0:
        raise BotException('Specifica un pg!')

    charid = args[0].lower()
    isChar, character = dbm.isValidCharacter(charid)
    if not isChar:
        raise BotException(f"Il personaggio {charid} non esiste!")

    # permission checks
    issuer = str(ctx.message.author.id)
    playerid = character['player']
    co = playerid == issuer
    
    st, _ = dbm.isStoryteller(issuer) # della cronaca?
    ba, _ = dbm.isBotAdmin(issuer)    
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

    response = await pc_interact(ctx, character, ce, *args[1:])
    await atSend(ctx, response)

@bot.command(brief='a bad idea.', help = "no.", hidden=True)
async def sql(ctx, *args):
    issuer = str(ctx.message.author.id)
    ba, _ = dbm.isBotAdmin(issuer)
    if not ba:
        raise BotException(f"Devi essere un Bot Admin per poter eseguire questo comando.")

    query = " ".join(args)
    try:
        query_result_raw = dbm.db.query(query)
        # check for integer -> delete statements return an int (and update statements aswell?)
        if isinstance(query_result_raw, int):
            await atSend(ctx, f"righe interessate: {query_result_raw}")
            return
        
        query_result = query_result_raw.list()
        if len(query_result) == 0:
            await atSend(ctx, "nessun risultato")
            return
        
        column_names = list(query_result[0].keys())
        col_widths = list(map(len, column_names))
        for r in query_result:
            for i in range(len(column_names)):
                length = len(str(r[column_names[i]]))
                if col_widths[i] < length:
                    col_widths[i] = length
        table_delim = '+' + '+'.join(map(lambda x: '-'*(x+2), col_widths)) + '+'
        out = table_delim+"\n|"
        for i in range(len(column_names)):
            out += " "+column_names[i]+" "*(col_widths[i]-len(column_names[i]))+" |"
        out += "\n"+table_delim+"\n"
        for r in query_result:
            out += "|"
            for i in range(len(column_names)):
                data = str(r[column_names[i]])
                out += " "+data+" "*(col_widths[i]-len(data))+" |"
            out += "\n"
        out += table_delim
        await atSend(ctx, "```\n"+out+"```")        
    except MySQLdb.OperationalError as e:
        await atSend(ctx, f"```Errore {e.args[0]}\n{e.args[1]}```")
    except MySQLdb.ProgrammingError as e:
        await atSend(ctx, f"```Errore {e.args[0]}\n{e.args[1]}```")

    

async def pgmod_create(ctx, args):
    helptext = "Argomenti: nome breve (senza spazi), @menzione al proprietario, nome completo del personaggio (spazi ammessi)"
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
            st, _ = dbm.isStoryteller(issuer)
            ba, _ = dbm.isBotAdmin(issuer)
            if not (st or ba):
                raise BotException("Per creare un pg ad un altra persona è necessario essere Admin o Storyteller")
        
        t = dbm.db.transaction()
        try:
            if not len(dbm.db.select('People', where='userid=$userid', vars=dict(userid=owner))):
                user = await bot.fetch_user(owner)
                dbm.db.insert('People', userid=owner, name=user.name, langId = default_language)
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
        isChar, character = dbm.isValidCharacter(charid)
        if not isChar:
            raise BotException(f"Il personaggio {charid} non esiste!")
        chronid = args[1].lower()
        chronicles = dbm.db.select('Chronicle', where='id=$id', vars=dict(id=chronid))
        if not len(chronicles):
            raise BotException(f"La cronaca {chronid} non esiste!")
        chronicle = chronicles[0]

        # permission checks
        issuer = str(ctx.message.author.id)
        st, _ = dbm.isChronicleStoryteller(issuer, chronicle['id'])
        ba, _ = dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise BotException("Per associare un pg ad una cronaca necessario essere Admin o Storyteller di quella cronaca")
        
        # todo check link esistente
        dbm.db.insert("ChronicleCharacterRel", chronicle=chronid, playerchar=charid)
        return f"{character['fullname']} ora gioca a {chronicle['name']}"

def pgmodPermissionCheck(issuer_id, character, channel_id):
    owner_id = character['owner']
    char_id = character['id']
    
    st, _ =  dbm.isStorytellerForCharacter(issuer_id, char_id)
    ba, _ = dbm.isBotAdmin(issuer_id)
    co = False
    if owner_id == issuer_id and not (st or ba):
        #1: unlinked
        cl, _ = dbm.isCharacterLinked(char_id)
        #2 active session
        sa, _ = dbm.isSessionActiveForCharacter(char_id, channel_id)
        co = co or (not cl) or sa            

    return (st or ba or co)
    
def pgmodPermissionCheck_Exc(issuer_id, character, channel_id):
    pc = pgmodPermissionCheck(issuer_id, character, channel_id)
    if not pc:
        raise BotException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Admin o Storyteller")
    else:
        return pc

async def pgmod_traitAdd(ctx, args):
    helptext = "Argomenti: nome breve del pg, nome breve del tratto, valore"
    if len(args) < 3:
        return helptext
    else:
        charid = args[0].lower()
        traitid = args[1].lower()
        isChar, character = dbm.isValidCharacter(charid)
        if not isChar:
            raise BotException(f"Il personaggio {charid} non esiste!")

        # permission checks
        issuer = str(ctx.message.author.id)

        pgmodPermissionCheck_Exc(issuer, character, ctx.channel.id)

        istrait, trait = dbm.isValidTrait(traitid)
        if not istrait:
            raise BotException(f"Il tratto {traitid} non esiste!")
        
        ptraits = dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id'])).list()
        if len(ptraits):
            raise BotException(f"{character['fullname']} ha già il tratto {trait['name']} ")
        
        ttype = dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        if ttype['textbased']:
            textval = " ".join(args[2:])
            dbm.db.insert("CharacterTrait", trait=traitid, playerchar=charid, cur_value = 0, max_value = 0, text_value = textval, pimp_max = 0)
            dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.TEXT_VALUE, textval, '', ctx.message.content)
            return f"{character['fullname']} ora ha {trait['name']} {textval}"
        else:
            pimp = 6 if trait['traittype'] in ['fisico', 'sociale', 'mentale'] else 0
            dbm.db.insert("CharacterTrait", trait=traitid, playerchar=charid, cur_value = args[2], max_value = args[2], text_value = "", pimp_max = pimp)
            dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.MAX_VALUE, args[2], '', ctx.message.content)
            return f"{character['fullname']} ora ha {trait['name']} {args[2]}"

async def pgmod_traitMod(ctx, args):
    helptext = "Argomenti: nome breve del pg, nome breve del tratto, nuovo valore"
    if len(args) < 3:
        return helptext
    else:
        charid = args[0].lower()
        traitid = args[1].lower()
        isChar, character = dbm.isValidCharacter(charid)
        if not isChar:
            raise BotException(f"Il personaggio {charid} non esiste!")

        # permission checks
        issuer = str(ctx.message.author.id)
        
        pgmodPermissionCheck_Exc(issuer, character, ctx.channel.id)

        istrait, trait = dbm.isValidTrait(traitid)
        if not istrait:
            raise BotException(f"Il tratto {traitid} non esiste!")
        
        ptraits = dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id'])).list()
        if not len(ptraits):
            raise BotException(f"{character['fullname']} non ha il tratto {trait['name']} ")
        
        ttype = dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        if ttype['textbased']:
            textval = " ".join(args[2:])
            dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']), text_value = textval)
            dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.TEXT_VALUE, textval, ptraits[0]['text_value'], ctx.message.content)
            return f"{character['fullname']} ora ha {trait['name']} {textval}"
        else:
            dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']), cur_value = args[2], max_value = args[2])
            dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.MAX_VALUE, args[2], ptraits[0]['max_value'], ctx.message.content)
            dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.CUR_VALUE, args[2], ptraits[0]['cur_value'], ctx.message.content)
            return f"{character['fullname']} ora ha {trait['name']} {args[2]}"

async def pgmod_traitRM(ctx, args):
    helptext = "Argomenti: nome breve del pg, nome breve del tratto"
    if len(args) < 2:
        return helptext
    else:
        charid = args[0].lower()
        traitid = args[1].lower()
        isChar, character = dbm.isValidCharacter(charid)
        if not isChar:
            raise BotException(f"Il personaggio {charid} non esiste!")

        # permission checks
        issuer = str(ctx.message.author.id)
        
        pgmodPermissionCheck_Exc(issuer, character, ctx.channel.id)

        istrait, trait = dbm.isValidTrait(traitid)
        if not istrait:
            raise BotException(f"Il tratto {traitid} non esiste!")
        
        ptraits = dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id'])).list()
        if not len(ptraits):
            raise BotException(f"{character['fullname']} non ha il tratto {trait['name']} ")
        ttype = dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        
        updated_rows = dbm.db.delete("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']))
        if ttype['textbased']:
            dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.DELETE, "", ptraits[0]['text_value'], ctx.message.content)
        else:
            dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.DELETE, "", f"{ptraits[0]['cur_value']}/{ptraits[0]['max_value']}", ctx.message.content)
            
        if updated_rows > 0:
            return f"Rimosso {trait['name']} da {character['fullname']} ({updated_rows})"
        else:
            return f"Nessun tratto rimosso"

pgmod_subcommands = {
    "create": [pgmod_create, "Crea un personaggio"],
    "link": [pgmod_chronicleAdd, "Aggiunge un personaggio ad una cronaca"],
    "addt": [pgmod_traitAdd, "Aggiunge tratto ad un personaggio"],
    "modt": [pgmod_traitMod, "Modifica un tratto di un personaggio"],
    "rmt": [pgmod_traitRM, "Rimuovi un tratto ad un personaggio"]
    }

async def gmadm_listChronicles(ctx, args):
    helptext = "Nessun argomento richiesto"
    if len(args) != 0:
        return helptext
    else:
        # permission checks
        issuer = str(ctx.message.author.id)
        #st, _ = dbm.isStoryteller(issuer)
        #ba, _ = dbm.isBotAdmin(issuer)
        #if not (st or ba):
        #    raise BotException("Per creare una cronaca è necessario essere Storyteller")

        query = """
    SELECT cr.id as cid, cr.name as cname, p.name as pname
    FROM Chronicle cr
    JOIN StoryTellerChronicleRel stcr on (cr.id = stcr.chronicle)
    JOIN People p on (stcr.storyteller = p.userid)
"""
        results = dbm.db.query(query)
        if len(results) == 0:
            return "Nessuna cronaca trovata!"

        chronicles = {}
        crst = {}
        for c in results:
            chronicles[c['cid']] = c['cname']
            if not c['cid'] in crst:
                crst[c['cid']] = []
            crst[c['cid']].append(c['pname'])

        return "Cronache:\n" + "\n".join(list(map(lambda x: f"**{chronicles[x]}** ({x}) (storyteller: {', '.join(crst[x])})", chronicles)))


async def gmadm_newChronicle(ctx, args):
    helptext = "Argomenti: <id> <nome completo> \n\nId non ammette spazi."
    if len(args) < 2:
        return helptext
    else:
        shortname = args[0].lower()
        fullname = " ".join(list(args[1:])) # squish

        # permission checks
        issuer = str(ctx.message.author.id)
        st, _ = dbm.isStoryteller(issuer)
        # no botadmin perchè non è necessariente anche uno storyteller e dovrei fare n check in più e non ho voglia
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

query_addTraitLangs = """
    insert into LangTrait select l.langId as langId, t.id as traitId, $traitid as traitShort, $traitname as traitName from Trait t join Languages l where t.id = $traitid;
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
        st, _ = dbm.isStoryteller(issuer)
        ba, _ = dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise BotException("Per creare un tratto è necessario essere Admin o Storyteller")
        
        traitid = args[0].lower()
        istrait, trait = dbm.isValidTrait(traitid)
        if istrait:
            raise BotException(f"Il tratto {traitid} esiste già!")

        if not validateTraitName(traitid):
            raise BotException(f"'{traitid}' non è un id valido!")

        traittypeid = args[1].lower()
        istraittype, traittype = dbm.isValidTraitType(traittypeid)
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

        response = ""
        t = dbm.db.transaction()
        try:
            dbm.db.insert("Trait", id = traitid, name = traitname, traittype = traittypeid, trackertype = tracktype, standard = std, ordering = 1.0)
            # we insert it in all available languages and we assume that it will be translated later:
            # better have it in the wrong language than not having it at all
            dbm.db.query(query_addTraitLangs, vars = dict(traitid=traitid, traitname=traitname))
            response = f'Il tratto {traitname} è stato inserito'
            if std:
                dbm.db.query(query_addTraitToPCs, vars = dict(traitid=traitid))
                response +=  f'\nIl nuovo talento standard {traitname} è stato assegnato ai personaggi!'
        except:
            t.rollback()
            raise
        else:
            t.commit()

        return response

async def gmadm_updateTrait(ctx, args):    
    issuer = ctx.message.author.id
    lid = getLanguage(issuer, dbm)
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
        st, _ = dbm.isStoryteller(issuer)
        ba, _ = dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise BotException("Per modificare un tratto è necessario essere Admin o Storyteller")

        old_traitid = args[0].lower()
        istrait, old_trait = dbm.isValidTrait(old_traitid)
        if not istrait:
            raise BotException(f"Il tratto {old_traitid} non esiste!")
        
        new_traitid = args[1].lower()
        istrait, new_trait = dbm.isValidTrait(new_traitid)
        if istrait and (old_traitid!=new_traitid):
            raise BotException(f"Il tratto {new_traitid} esiste già!")

        if not validateTraitName(new_traitid):
            raise BotException(f"'{new_traitid}' non è un id valido!")

        traittypeid = args[2].lower()
        istraittype, traittype = dbm.isValidTraitType(traittypeid)
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
        

        response = f'Il tratto {traitname} è stato aggiornato'
        t = dbm.db.transaction()
        try:
            dbm.db.update("Trait", where= 'id = $oldid' , vars=dict(oldid = old_traitid), id = new_traitid, name = traitname, traittype = traittypeid, trackertype = tracktype, standard = std, ordering = 1.0)
            # now we update the language description, but only of the current language
            dbm.db.update("LangTrait", where= 'traitId = $traitid and langId = $lid' , vars=dict(traitid=new_traitid, lid = lid), traitName = traitname)
            if std and not old_trait['standard']:
                dbm.db.query(query_addTraitToPCs_safe, vars = dict(traitid=new_traitid))
                response +=  f'\nIl nuovo talento standard {traitname} è stato assegnato ai personaggi!'
            elif not std and old_trait['standard']:
                dbm.db.query("""
    delete from CharacterTrait
    where trait = $traitid and max_value = 0 and cur_value = 0 and text_value = '';
    """, vars = dict(traitid=new_traitid))
                response += f'\nIl talento {traitname} è stato rimosso dai personaggi che non avevano pallini'
        except:
            t.rollback()
            raise
        else:
            t.commit()


        return response

async def gmadm_deleteTrait(ctx, args):
    return "non implementato"

gameAdmin_subcommands = {
    "listChronicles": [gmadm_listChronicles, "Elenca le cronache"],
    "newChronicle": [gmadm_newChronicle, "Crea una nuova cronaca associata allo ST che invoca il comando"],
    "newTrait": [gmadm_newTrait, "Crea nuovo tratto"],
    "updt": [gmadm_updateTrait, "Modifica un tratto"],
    "delet": [gmadm_deleteTrait, "Cancella un tratto"] #non implemmentato
    # todo: nomina storyteller, associa storyteller a cronaca
    # todo: dissociazioni varie
    }

def generateNestedCmd(cmd_name, cmd_brief, cmd_dict):
    longdescription = "\n".join(list(map(lambda x: botcmd_prefixes[0]+cmd_name+" "+x+" [arg1, ...]: "+cmd_dict[x][1], cmd_dict.keys())))  + "\n\nInvoca un sottocomando senza argomenti per avere ulteriori informazioni sugli argomenti"

    @bot.command(name=cmd_name, brief=cmd_brief, description = longdescription)
    async def generatedCommand(ctx, *args):
        response = 'Azioni disponibili (invoca una azione senza argomenti per conoscere il funzionamento):\n'
        if len(args) == 0:
            response += longdescription
        else:
            subcmd = args[0]
            if subcmd in cmd_dict:
                response = await cmd_dict[subcmd][0](ctx, args[1:])
            else:
                response = f'"{subcmd}" non è un sottocomando valido!\n'+longdescription
        await atSend(ctx, response)
    return generatedCommand

gmadm = generateNestedCmd('gmadm', "Gestione dell'ambiente di gioco", gameAdmin_subcommands)
pgmod = generateNestedCmd('pgmod', "Gestione personaggi", pgmod_subcommands)


bot.run(TOKEN)
