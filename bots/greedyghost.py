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
    print(f"The configuration file {sys.argv[1]} does not exist!")
    sys.exit()

config = configparser.ConfigParser()
config.read(sys.argv[1])

TOKEN = config['Discord']['token']

SOMMA_CMD = ["somma", "s", "lapse", "sum"]
DIFF_CMD = ["diff", "diff.", "difficoltà", "difficolta", "d", "difficulty"]
MULTI_CMD = ["multi", "m"]
DANNI_CMD = ["danni", "danno", "dmg", "damage"]
PROGRESSI_CMD = ["progressi", "progress"]
SPLIT_CMD = ["split"]
PENALITA_CMD = ["penalita", "penalità", "p", "penalty"]
DADI_CMD = ["dadi", "dice"]
ADD_CMD = "+"
SUB_CMD = "-"

PERMANENTE_CMD = ["permanente", "perm", "permanent"]
SOAK_CMD = ["soak", "assorbi"]
INIZIATIVA_CMD = ["iniziativa", "iniz", "initiative"]
RIFLESSI_CMD = ["riflessi", "r", "reflexes"]
STATISTICS_CMD = ["statistica", "stats", "stat"]

RollCat = utils.enum("DICE", "INITIATIVE", "REFLEXES", "SOAK") # macro categoria che divide le azioni di tiro
RollArg = utils.enum("DIFF", "MULTI", "SPLIT", "ADD", "ROLLTYPE", "PENALITA", "DADI", "DADI_PERMANENTI",  "PERMANENTE", "STATS", "CHARACTER", "NFACES") # argomenti del tiro
RollType = utils.enum("NORMALE", "SOMMA", "DANNI", "PROGRESSI") # valori dell'argomento RollType

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

def validateDiscordMention(mention : str):
    if not (mention.startswith("<@!") and mention.endswith(">")): 
        return False, ""
    return  True, mention[3:-1]

async def validateDiscordMentionOrID(inp: str): #, bot : commands.Bot):
    vm, userid = validateDiscordMention(inp)
    if vm:
        return vm, userid
    
    uid = int(inp)
    try:
        user = await bot.fetch_user(uid)
        return True, inp
    except:
        return False, ""

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
        # TODO: define how extra successes (bopth positive and negative) invfluende critfail situations
        if (extra_succ > 0): 
            if successi < 0: # adding auto successes means we ignore critfail situations, the roll is always a success.
                successi = 0
            successi += extra_succ
        if (extra_succ < 0): 
            if successi > 0: # the idea here is that we only act if there are successes to remove in the first place, and at max we shift to a fail (?)
                successi = max(0, successi + extra_succ)
        status = statusFunc(lid, successi)
        response = status + f' (diff {diff}): {pretty}'
        if extra_succ > 0:
            response += f' **+{extra_succ}**'
        if extra_succ < 0:
            response += f' **{extra_succ}**'
        return response

def d10check(lid, faces):
    if faces != 10:
        raise BotException(lp.get(lid, 'string_error_not_d10') )

def atSend(ctx, msg):
    return ctx.send(f'{ctx.message.author.mention} {msg}')

def atSendLang(ctx, msg, *args):
    issuer = ctx.message.author.id
    lid = getLanguage(issuer, dbm)
    translated = lp.get(lid, msg, *args)
    return ctx.send(f'{ctx.message.author.mention} {translated}')

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
                await atSend(ctx, lp.get(lid, "string_error_wat"))
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
                await atSend(ctx, lp.get(lid, "string_error_database_noanswer") )
                dbm.reconnect()
            else:
                await atSend(ctx, lp.get(lid, "string_error_database_generic") )
        elif isinstance(error, MySQLdb.IntegrityError):
            await atSend(ctx, lp.get(lid, "string_error_database_dataviolation") )
        else:
            await atSend(ctx, lp.get(lid, "string_error_unhandled_exception") )
        #print("debug user:", int(config['Discord']['debuguser']))
        debug_user = await bot.fetch_user(int(config['Discord']['debuguser']))
        await debug_user.send( lp.get(lid, "string_error_details", ctx.message.content, type(error), error, ftb) )


@bot.command(name='coin', help = 'Testa o Croce.')
async def coin(ctx):
    issuer = ctx.message.author.id
    lid = getLanguage(issuer, dbm)

    moneta=[ "string_heads", "string_tails" ]
    await atSend(ctx, lp.get(lid, random.choice(moneta)))

roll_longdescription = """.roll <cosa> <argomento1> (<parametro1> <parametro2>...) <argomento2> ...
  <cosa> è il numero di dadi in forma XdY (es. ".roll 1d20")
  <argomento> indicazioni aggiuntive che pilotano il tiro con eventuali <parametri>

Argomenti diponibili:

.roll 7d10 somma                       -> Somma i risultati in un unico valore
.roll 7d10 diff 6                      -> Tiro a difficoltà 6
.roll 7d10 danni                       -> Tiro danni
.roll 7d10 + 5                         -> Aggiunge 5 successi
.roll 7d10 progressi                   -> Tiro per i progressi
.roll 7d10 lapse                       -> Tiro per i progressi in timelapse
.roll 7d10 multi 3 diff 6              -> Azione multipla con 3 mosse
.roll 7d10 split 6 7                   -> Azione splittata a diff. separate (6 e 7)
.roll 7d10 diff 6 multi 3 split 2 6 7  -> Multipla [3] con split [al 2° tiro] a diff. separate [6,7]

A sessione attiva:

.roll tratto1+tratto2  -> al posto di XdY per usare le statistiche del proprio pg (es. ".roll destrezza+schivare")
.roll iniziativa       -> .roll 1d10 +(destrezza+prontezza+velocità)
.roll riflessi         -> .roll volontà diff (10-prontezza)
.roll assorbi          -> .roll costituzione+robustezza diff 6 danni
.roll <...> penalita   -> Applica la penalità derivata dalla salute
.roll <...> dadi N     -> Modifica il numero di dadi del tiro (N può essere positivo o negativo)
.roll <...> +/- XdY    -> Vedi sopra
.roll <...> permanente -> Usa i valori base e non quelli potenziati/spesi (es.: ".roll volontà permanente diff 7")

Note sugli spazi:

Si può spaziare o meno tra i tratti, basta non mischiare dadi e successi automatici se non si spazia:
  ".roll forza + rissa" ok
  ".roll 2d10+ rissa" ok
  ".roll forza +rissa" ok
  ".roll forza+2d10" ok
  ".roll forza+2" no

Si può omettere lo spazio tra argomento e il 1° parametro:
  ".roll 3d10 diff6" ok
  ".roll 3d10 split6 7" ok
  ".roll 3d10 split67" no"""

def parseDiceExpression_Dice(lid, what, forced10 = False):
    split = what.split("d")
    if len(split) > 2:
        raise BotException(lp.get(lid, "string_error_toomany_d"))
    if len(split) == 1:
        raise BotException(lp.get(lid, "string_error_not_XdY", split[0] ) )
    if split[0] == "":
        split[0] = "1"
    if not split[0].isdigit():
        raise BotException(lp.get(lid, "string_error_not_positive_integer", split[0]))
    if split[1] == "":
        split[1] = "10"
    if not split[1].isdigit():
        raise BotException( lp.get(lid, "string_error_not_positive_integer", split[1]))
    n = int(split[0])
    faces = int(split[1])
    if forced10 and faces != 10:
        raise BotException( lp.get(lid, "string_error_not_d10", split[1]))
    if n == 0:
        raise BotException(lp.get(lid, "string_error_not_gt0", n) )
    if  faces == 0:
        raise BotException(lp.get(lid, "string_error_not_gt0", faces))
    if n > max_dice:
        raise BotException(lp.get(lid, "string_error_toomany_dice", n) )
    if faces > max_faces:
        raise BotException(lp.get(lid, "string_error_toomany_faces", faces))
    return n, n, faces, None

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
    return n, n_perm, faces, character

def parseDiceExpression_Mixed(ctx, lid, what, firstNegative = False, forced10 = True, character = None):
    #character = None

    saw_trait = False
    saw_notd10 = False

    faces = 0
    n = 0
    n_perm = 0

    split_add_list = what.split(ADD_CMD) # split on "+", so each of the results STARTS with something to add
    for i in range(0, len(split_add_list)):
        split_add = split_add_list[i]
        split_sub_list = split_add.split(SUB_CMD) # split on "-", so the first element will be an addition (unless firstNegative is true and i == 0), and everything else is a subtraction

        for j in range(0, len(split_sub_list)):
            term = split_sub_list[j]
            n_term = 0
            n_term_perm = 0
            try: # either a xdy expr
                n_term, n_term_perm, nf, _ =  parseDiceExpression_Dice(lid, term, forced10)    
                saw_notd10 = saw_notd10 or (nf != 10)
                if faces and (faces != nf): # we do not support mixing different face numbers for now
                    raise BotException( lp.get(lid, "string_error_face_mixing"))
                faces = nf
            except BotException as e: # or a trait
                try:
                    if not character:
                        character = dbm.getActiveChar(ctx) # can raise
                    temp = dbm.getTrait_LangSafe(character['id'], term, lid) 
                    n_term = temp['cur_value']
                    n_term_perm = temp['max_value']
                    saw_trait = True
                    faces = 10
                except ghostDB.DBException as edb:
                    raise BotException("\n".join([ lp.get(lid, "string_error_notsure_whatroll"), f'{e}', f'{lp.formatException(lid, edb)}']) )
            
            if j > 0 or (i == 0 and firstNegative):
                n -= n_term
                n_perm -= n_term_perm
            else:
                n += n_term
                n_perm += n_term_perm

    if saw_trait and saw_notd10: # forced10 = false only lets through non d10 expressions that DO NOT use traits
        raise BotException( lp.get(lid, "string_error_not_d10"))

    return n, n_perm, faces, character


# input: l'espressione <what> in .roll <what> [<args>]
# output: tipo di tiro
def parseRollWhat(ctx, lid, what):
    if what in INIZIATIVA_CMD:
        return RollCat.INITIATIVE
    if what in RIFLESSI_CMD:
        return RollCat.REFLEXES
    if what in SOAK_CMD:
        return RollCat.SOAK
    else:
        return RollCat.DICE
        
def validateInteger(lid, args, i, err_msg = None):
    if err_msg == None:
        err_msg = lp.get(lid, "string_errorpiece_integer") 
    try:
        return i, int(args[i])
    except ValueError:
        raise ValueError(lp.get(lid, "string_error_x_isnot_y", args[i], err_msg))

def validateBoundedInteger(lid, args, i, min_val, max_val, err_msg = None):
    if err_msg == None:
        err_msg = lp.get(lid, "string_errorpiece_number_in_range", min_val, max_val) 
    j, val = validateInteger(lid, args, i)
    if val < min_val or val > max_val:
        raise ValueError(lp.get(lid, "string_error_x_isnot_y", args[i], err_msg))
    return j, val

def validateNumber(lid, args, i, err_msg = None):
    if err_msg == None:
        err_msg = lp.get(lid, "string_errorpiece_positive_integer") 
    if not args[i].isdigit():
        raise ValueError(lp.get(lid, "string_error_x_isnot_y", args[i], err_msg))
    return i, int(args[i])

def validateBoundedNumber(lid, args, i, min_bound, max_bound, err_msg = None):
    if err_msg == None:
        err_msg = lp.get(lid, "string_errorpiece_number_in_range", min_bound, max_bound) 
    _, num = validateNumber(lid, args, i)
    if num > max_bound or num < min_bound:
        raise ValueError(lp.get(lid, "string_error_x_isnot_y", num, err_msg) )
    return i, num

def validateIntegerGreatZero(lid, args, i):
    return validateBoundedNumber(lid, args, i, 1, INFINITY, lp.get(lid, "string_errorpiece_integer_gt0") )

def validateDifficulty(lid, args, i):
    return validateBoundedNumber(lid, args, i, 2, 10, lp.get(lid, "string_errorpiece_valid_diff") )


def prettyHighlightError(args, i, width = 3):
    return " ".join(list(args[max(0, i-width):i]) + ['**'+args[i]+'**'] + list(args[min(len(args), i+1):min(len(args), i+width)]))

# input: sequenza di argomenti per .roll
# output: dizionario popolato con gli argomenti validati
def parseRollArgs(ctx, lid, args_raw):
    parsed = {
        RollArg.ROLLTYPE: RollType.NORMALE, # default
        RollArg.CHARACTER: None
        }
    args = list(args_raw)
    # leggo gli argomenti scorrendo args

    i = 0
    last_i = -1
    repeats = 0
    while i < len(args):
        # bit of safety code due to the fact that we decrement i sometimes
        if i == last_i:
            repeats += 1
        else:
            repeats = 0
        if repeats >= 2:
            raise ValueError(lp.get(lid, "string_arg_X_in_Y_notclear", args[i], prettyHighlightError(args, i)) )
        last_i = i
        
        # detaching + or - from the end of an expression needs to be done immediately
        if args[i].endswith(ADD_CMD) and args[i] != ADD_CMD: 
            args = args[:i] + [args[i][:-1], ADD_CMD] + args[i+1:]
        if args[i].endswith(SUB_CMD) and args[i] != SUB_CMD: 
            args = args[:i] + [args[i][:-1], SUB_CMD] + args[i+1:]

        if args[i] in SOMMA_CMD:
            parsed[RollArg.ROLLTYPE] = RollType.SOMMA
        elif args[i] in DIFF_CMD:
            if RollArg.DIFF in parsed:
                raise ValueError(lp.get(lid, "string_error_multiple_diff"))
            if len(args) == i+1:
                raise ValueError(lp.get(lid, "string_error_x_what", args[i]))
            i, diff = validateDifficulty(lid, args, i+1)
            parsed[RollArg.DIFF] = diff
        elif args[i] in MULTI_CMD:
            if RollArg.SPLIT in parsed:
                raise ValueError(lp.get(lid, "string_error_split_before_multi"))
            if RollArg.MULTI in parsed:
                raise ValueError(lp.get(lid, "string_error_multiple_multi"))
            if len(args) == i+1:
                raise ValueError(lp.get(lid, "string_error_x_what", args[i]))
            i, multi = validateBoundedNumber(lid, args, i+1, 2, INFINITY, lp.get(lid, "string_errorpiece_validarg_multi", args[i]) )# controlliamo il numero di mosse sotto, dopo aver applicato bonus o penalità al numero di dadi
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
                    raise ValueError(lp.get(lid, "string_error_X_takes_atleast_Y_params", args[i], 3) +" "+ lp.get(lid, "string_errorpiece_with_multi") )
                i, temp = validateIntegerGreatZero(lid, args, i+1)
                roll_index = temp-1
                if roll_index >= parsed[RollArg.MULTI]:
                    raise ValueError(lp.get(lid, "string_error_split_X_higherthan_multi_Y", args[i+1], multi) )
                if sum(filter(lambda x: x[0] == roll_index, split)): # cerco se ho giò splittato questo tiro
                    raise ValueError(lp.get(lid, "string_error_already_splitting_X", roll_index+1) )
            else: # not an elif because reasons
                if len(args) < i+3:
                    raise ValueError(lp.get(lid, "string_error_X_takes_atleast_Y_params", args[i], 2))
            i, d1 = validateIntegerGreatZero(lid, args, i+1)
            i, d2 = validateIntegerGreatZero(lid, args, i+1)
            split.append( [roll_index] + list(map(int, [d1, d2])))
            parsed[RollArg.SPLIT] = split # save the new split
        elif args[i] in [ADD_CMD, SUB_CMD]:
            if len(args) == i+1:
                raise ValueError(lp.get(lid, "string_error_x_what", args[i]))
            # 3 options here: XdY (and variants), trait(s), integers.
            try:
                sign = ( 1 - 2 * ( args[i] == SUB_CMD)) # 1 or -1 depenging on args[i]
                i, add = validateIntegerGreatZero(lid, args, i+1) # simple positive integer -> add as successes
                if RollArg.ADD in parsed:
                    parsed[RollArg.ADD] += add * sign
                else:
                    parsed[RollArg.ADD] = add * sign
            except ValueError as e_add: # not an integer -> try to parse it as a dice expression
                n_dice, n_dice_perm, nfaces, character = parseDiceExpression_Mixed(ctx, lid, args[i+1], firstNegative = args[i] == SUB_CMD, forced10 = (i != 0), character = parsed[RollArg.CHARACTER]) # TODO: we're locked into d10s by this point, non-vtm dice rolls are limited to the first argument for .roll
                if RollArg.DADI in parsed:
                    parsed[RollArg.DADI] += n_dice
                    parsed[RollArg.DADI_PERMANENTI] += n_dice_perm 
                else:
                    parsed[RollArg.DADI] = n_dice
                    parsed[RollArg.DADI_PERMANENTI] = n_dice_perm
                if character != None:
                    parsed[RollArg.CHARACTER] = character
                parsed[RollArg.NFACES] = nfaces
                i += 1
        elif args[i] in PENALITA_CMD:
            parsed[RollArg.PENALITA] = True
        elif args[i] in DADI_CMD:
            if len(args) == i+1:
                raise ValueError(lp.get(lid, "string_error_x_what", args[i]))
            i, val = validateBoundedInteger(lid, args, i+1, -100, +100) # this is also checked later on the final number
            if RollArg.DADI in parsed:
                parsed[RollArg.DADI] += val
                parsed[RollArg.DADI_PERMANENTI] += val 
            else:
                parsed[RollArg.DADI] = val
                parsed[RollArg.DADI_PERMANENTI] = val 
        elif args[i] in PERMANENTE_CMD:
            parsed[RollArg.PERMANENTE] = True
        elif args[i] in STATISTICS_CMD:
            parsed[RollArg.STATS] = True
        else:
            #try parsing a dice expr
            try:
                n_dice, n_dice_perm, nfaces, character = parseDiceExpression_Mixed(ctx, lid, args[i], firstNegative = False, forced10 = (i != 0), character = parsed[RollArg.CHARACTER])
                if RollArg.DADI in parsed:
                    parsed[RollArg.DADI] += n_dice
                    parsed[RollArg.DADI_PERMANENTI] += n_dice_perm 
                else:
                    parsed[RollArg.DADI] = n_dice
                    parsed[RollArg.DADI_PERMANENTI] = n_dice_perm
                if character != None:
                    parsed[RollArg.CHARACTER] = character
                parsed[RollArg.NFACES] = nfaces
            except:
                # provo a staccare parametri attaccati
                did_split = False
                idx = 0
                tests = DIFF_CMD+MULTI_CMD+DADI_CMD+[ADD_CMD, SUB_CMD]
                while not did_split and idx < len(tests):
                    cmd = tests[idx]
                    if args[i].startswith(cmd):
                        try:
                            #_ = int(args[i][len(cmd):]) # pass only if the rest of the argument is a valid integer. We don't enforce this anymore now that we can also parse traits.
                            args = args[:i] + [cmd, args[i][len(cmd):]] + args[i+1:]
                            did_split = True
                        except ValueError:
                            pass
                    idx += 1

                if not did_split: # F
                    raise ValueError(lp.get(lid, "string_arg_X_in_Y_notclear", args[i], prettyHighlightError(args, i)) )
                else:
                    i -= 1 # forzo rilettura
        i += 1
    return parsed

async def roll_initiative(ctx, lid, parsed):
    if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE or RollArg.DIFF in parsed:
        raise BotException(lp.get(lid, "string_error_roll_invalid_param_combination") )
    add = parsed[RollArg.ADD] if RollArg.ADD in parsed else 0
    raw_roll = random.randint(1, 10)
    bonuses_log = []
    bonus = add
    if add:
        bonuses_log.append(lp.get(lid, "string_bonus_X", add))
    try:
        character = dbm.getActiveChar(ctx)
        for traitid in ['prontezza', 'destrezza', 'velocità']:
            try:
                val = dbm.getTrait_LangSafe(character['id'], traitid, lid)
                bonus += val["cur_value"]
                bonuses_log.append( f'{val["traitName"]}: {val["cur_value"]}' )
            except ghostDB.DBException:
                pass
    except ghostDB.DBException:
        bonuses_log.append(lp.get(lid, "string_comment_no_pc"))
    details = ""
    if len(bonuses_log):
        details = ", ".join(bonuses_log)
    final_val = raw_roll+bonus
    return f'{lp.get(lid, "string_initiative")}: **{final_val}**\n{lp.get(lid, "string_roll")}: [{raw_roll}] + {bonus if bonus else 0} ({details})'

async def roll_reflexes(ctx, lid, parsed):
    if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE or RollArg.DIFF in parsed:    
        raise BotException(lp.get(lid, "string_error_roll_invalid_param_combination"))
    add = parsed[RollArg.ADD] if RollArg.ADD in parsed else 0
    character = dbm.getActiveChar(ctx)
    volonta = dbm.getTrait_LangSafe(character['id'], 'volonta', lid)#['cur_value']
    prontezza = dbm.getTrait_LangSafe(character['id'], 'prontezza', lid)#['cur_value']
    diff = 10 - prontezza['cur_value']
    response = f'{volonta["traitName"]}: {volonta["cur_value"]}, {prontezza["traitName"]}: {prontezza["cur_value"]} -> {volonta["cur_value"]}d{10} {lp.get(lid, "string_diff")} ({diff} = {10}-{prontezza["cur_value"]})\n'
    response += rollAndFormatVTM(lid, volonta['cur_value'], 10, diff, rollStatusReflexes, add, statistics = RollArg.STATS in parsed)
    return response

async def roll_soak(ctx, lid, parsed):
    if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or RollArg.ADD in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE:
        raise BotException(lp.get(lid, "string_error_roll_invalid_param_combination"))
    diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
    character = dbm.getActiveChar(ctx)
    pool = dbm.getTrait_LangSafe(character['id'], 'costituzione', lid)['cur_value']
    try:
        pool += dbm.getTrait_LangSafe(character['id'], 'robustezza', lid)['cur_value']
    except ghostDB.DBException:
        pass
    return rollAndFormatVTM(lid, pool, 10, diff, rollStatusSoak, 0, False, statistics = RollArg.STATS in parsed)

async def roll_dice(ctx, lid, parsed):
    ndice = 0
    if RollArg.PERMANENTE in parsed:
        ndice = parsed[RollArg.DADI_PERMANENTI]
    else:
        ndice = parsed[RollArg.DADI]

    nfaces = parsed[RollArg.NFACES]

    character = parsed[RollArg.CHARACTER] # might be None

    # modifico il numero di dadi
    
    if RollArg.PENALITA in parsed:
        if not character:
            character = dbm.getActiveChar(ctx)
        health = dbm.getTrait_LangSafe(character['id'], 'salute', lid)
        penalty, _ = parseHealth(health)
        ndice += penalty[0]

    if ndice > max_dice:
        raise BotException(lp.get(lid, "string_error_toomany_dice", max_dice))
    if ndice <= 0:
        raise BotException(lp.get(lid, "string_error_toofew_dice", ndice) )

    # check n° di mosse per le multiple
    if RollArg.MULTI in parsed:
        multi = parsed[RollArg.MULTI]
        max_moves = int( ((ndice+1)/2) -0.1) # (ndice+1)/2 è il numero di mosse in cui si rompe, non il massimo. togliendo 0.1 e arrotondando per difetto copro sia il caso intero che il caso con .5
        if max_moves == 1:
            raise BotException(lp.get(lid, "string_error_not_enough_dice_multi") )
        elif multi > max_moves:
            raise BotException(lp.get(lid, "string_error_not_enough_dice_multi_MAX_REQUESTED", max_moves, ndice) )

    # decido cosa fare

    add = parsed[RollArg.ADD] if RollArg.ADD in parsed else 0

    # simple roll
    if not (RollArg.MULTI in parsed) and not (RollArg.DIFF in parsed) and not (RollArg.SPLIT in parsed) and (parsed[RollArg.ROLLTYPE] == RollType.NORMALE or parsed[RollArg.ROLLTYPE] == RollType.SOMMA):
        raw_roll = list(map(lambda x: random.randint(1, nfaces), range(ndice)))
        if add != 0 or parsed[RollArg.ROLLTYPE] == RollType.SOMMA:
            roll_sum = sum(raw_roll) + add
            await atSend(ctx, f'{repr(raw_roll)} {"+" if add > 0 else "" }{add} = **{roll_sum}**')
        else:
            await atSend(ctx, repr(raw_roll))
        return

    d10check(lid, nfaces) # past this point, we are in d10 territory
    
    stats = RollArg.STATS in parsed
    response = ''
    
    if RollArg.MULTI in parsed:
        multi = parsed[RollArg.MULTI]
        split = []
        if RollArg.SPLIT in parsed:
            split = parsed[RollArg.SPLIT]
        if parsed[RollArg.ROLLTYPE] == RollType.NORMALE:
            response = ""
            if not RollArg.DIFF in parsed:
                raise BotException(lp.get(lid, "string_error_missing_diff"))
            for i in range(multi):
                parziale = ''
                ndadi = ndice-i-multi
                split_diffs = findSplit(i, split)
                if len(split_diffs):
                    pools = [(ndadi-ndadi//2), ndadi//2]
                    for j in range(len(pools)):
                        parziale += f'\n{lp.get(lid, "string_roll")} {j+1}: '+ rollAndFormatVTM(lid, pools[j], nfaces, split_diffs[j], statistics = stats)
                else:
                    parziale = rollAndFormatVTM(lid, ndadi, nfaces, parsed[RollArg.DIFF], statistics = stats)
                response += f'\n{lp.get(lid, "string_action")} {i+1}: '+parziale # line break all'inizio tanto c'è il @mention
        else:
            raise BotException(lp.get(lid, "string_error_roll_invalid_param_combination"))
    else: # 1 tiro solo 
        if RollArg.SPLIT in parsed:
            split = parsed[RollArg.SPLIT]
            if parsed[RollArg.ROLLTYPE] == RollType.NORMALE:
                pools = [(ndice-ndice//2), ndice//2]
                response = ''
                for i in range(len(pools)):
                    parziale = rollAndFormatVTM(lid, pools[i], nfaces, split[0][i+1], statistics = stats)
                    response += f'\n{lp.get(lid, "string_roll")} {i+1}: '+parziale
            else:
                raise BotException(lp.get(lid, "string_error_roll_invalid_param_combination"))
        else:
            if parsed[RollArg.ROLLTYPE] == RollType.NORMALE: # tiro normale
                if not RollArg.DIFF in parsed:
                    raise BotException(lp.get(lid, "string_error_missing_diff"))
                response = rollAndFormatVTM(lid, ndice, nfaces, parsed[RollArg.DIFF], rollStatusNormal, add, statistics = stats)
            elif parsed[RollArg.ROLLTYPE] == RollType.DANNI:
                diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
                response = rollAndFormatVTM(lid, ndice, nfaces, diff, rollStatusDMG, add, False, statistics = stats)
            elif parsed[RollArg.ROLLTYPE] == RollType.PROGRESSI:
                diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
                response = rollAndFormatVTM(lid, ndice, nfaces, diff, rollStatusProgress, add, False, True, statistics = stats)
            else:
                raise BotException(lp.get(lid, "string_error_unknown_rolltype", RollArg.ROLLTYPE))
    await atSend(ctx, response)


@bot.command(name='roll', aliases=['r', 'tira', 'lancia', 'rolla'], brief = 'Tira dadi', description = roll_longdescription) 
async def roll(ctx, *args):
    issuer = ctx.message.author.id
    lid = getLanguage(issuer, dbm)
    if len(args) == 0:
        raise BotException(lp.get(lid, "string_error_x_what", "roll")+" diomadonna") #xd
    args_list = list(args)
    
    # capisco che tipo di tiro ho di fronte
    what = args_list[0].lower()

    action = parseRollWhat(ctx, lid, what)
    
    # leggo e imposto le varie opzioni
    parsed = None
    start_arg = 0 if action == RollCat.DADI else 1
    try:
        parsed = parseRollArgs(ctx, lid, args_list[start_arg:])
    except ValueError as e:
        await atSend(ctx, str(e))
        return

    # gestisco i tiri specifici
    if action == RollCat.INITIATIVE:
        response = await roll_initiative(ctx, lid, parsed)
    elif action == RollCat.REFLEXES:
        response = await roll_reflexes(ctx, lid, parsed)
    elif action == RollCat.SOAK:
        response = await roll_soak(ctx, lid, parsed)
    else:
        response = await roll_dice(ctx, lid, parsed)
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
    issuer = ctx.message.author.id
    lid = getLanguage(issuer, dbm)
    response = ''
    if len(args) == 0:
        response = lp.get(lid, "string_error_no_searchterm") 
    else:
        searchstring = "%" + (" ".join(args)) + "%"
        lower_version = searchstring.lower()
        traits = dbm.db.select("LangTrait", where="langId=$langid and (traitId like $search_lower or traitShort like $search_lower or traitName like $search_string)", vars=dict(search_lower=lower_version, search_string = searchstring, langid=lid))
        if not len(traits):
            response =  lp.get(lid, "string_msg_no_match") 
        else:
            response = lp.get(lid, "string_msg_found_traits") +":\n"
            for trait in traits:
                response += f"\n {trait['traitShort']} ({trait['traitId']}): {trait['traitName']}"
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
            dbm.registerUser(issuer, user.name, args[0])
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
    #lid = getLanguage(issuer, dbm)
    if len(args) != 1:
        await atSendLang(ctx, "string_error_wrong_number_arguments")
        return
    chronicleid = args[0].lower()
    vc, _ = dbm.isValidChronicle(chronicleid)
    if not vc:
        await atSend(ctx, "Id cronaca non valido")
        return
        
    st, _ = dbm.isChronicleStoryteller(issuer, chronicleid)
    ba, _ = dbm.isBotAdmin(issuer)
    can_do = st or ba

    sessions = dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
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
    st, _ = dbm.isStoryteller(issuer) # todo: elenca solo le sue?
    ba, _ = dbm.isBotAdmin(issuer)
    if not (st or ba):
        raise BotException("no.")
    
    sessions = dbm.db.select('GameSession').list()
    channels = []
    lines = []
    for s in sessions:
        try:
            ch = await bot.fetch_channel(int(s['channel']))
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
    await atSend(ctx, response)
    

@session.command(brief = 'Termina la sessione corrente', description = 'Termina la sessione corrente. Richiede di essere admin o storyteller della sessione in corso.')
async def end(ctx):
    response = ''
    issuer = str(ctx.message.author.id)
    sessions = dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
    if len(sessions):
        ba, _ = dbm.isBotAdmin(issuer)
        st, _ = dbm.isChronicleStoryteller(issuer, sessions[0]['chronicle'])
        can_do = ba or st
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


@bot.command(name = 'translate', brief='Permette di aggiornare la traduzione di un tratto in una lingua' , help = "")
async def translate(ctx, *args):
    issuer = ctx.message.author.id
    lid = getLanguage(issuer, dbm)
    language = None
    if len(args):
        vl, language = dbm.isValidLanguage(args[0]) 
        if not vl:
            raise BotException(lp.get(lid, "string_error_invalid_language_X", args[0]))
    if len(args)>=2:
        vt, _ = dbm.isValidTrait(args[1]) 
        if not vt:
            raise BotException(lp.get(lid, "string_error_invalid_trait_X", args[1]))

    if len(args) == 2: # consulto
        traits = dbm.db.select("LangTrait", where = 'traitId = $traitId and langId = $langId', vars = dict(traitId=args[1], langId = args[0]))
        if len(traits):
            trait = traits[0]
            await atSendLang(ctx, "string_msg_trait_X_in_Y_has_translation_Z1_Z2", args[1], language['langName'], trait['traitName'], trait['traitShort'])
        else:
            await atSendLang(ctx, "string_msg_trait_X_not_translated_Y", args[1], language['langName'])
    elif len(args) >= 4: # update/inserimento
        traits = dbm.db.select("LangTrait", where = 'traitId = $traitId and langId = $langId', vars = dict(traitId=args[1], langId = args[0]))
        if len(traits): # update
            trait = traits[0]
            u = dbm.db.update("LangTrait", where = 'traitId = $traitId and langId = $langId', vars = dict(traitId=args[1], langId = args[0]), traitShort = args[2], traitName = args[3])
            if u == 1:
                await atSendLang(ctx, "string_msg_trait_X_in_Y_has_translation_Z1_Z2", args[1], language['langName'], args[3], args[2])
            else:
                await atSendLang(ctx, "string_error_update_wrong_X_rows_affected", u)
        else:
            dbm.db.insert("LangTrait", langId = args[0], traitId=args[1], traitShort = args[2], traitName = args[3])
            await atSendLang(ctx, "string_msg_trait_X_in_Y_has_translation_Z1_Z2", args[1], language['langName'], args[3], args[2])
    else:
        await atSendLang(ctx, "string_help_translate")

damage_types = ["a", "l", "c"]

def defaultTraitFormatter(trait, lid):
    return f"Oh no! devo usare il formatter di default!\n{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}/{trait['pimp_max']}, text: {trait['text_value']}"

def prettyDotTrait(trait, lid):
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
    (0, "hurt_levels_vampire_unharmed"),
    (0, "hurt_levels_vampire_bruised"),
    (-1, "hurt_levels_vampire_hurt"),
    (-1, "hurt_levels_vampire_injured"),
    (-2, "hurt_levels_vampire_wounded"),
    (-2, "hurt_levels_vampire_mauled"),
    (-5, "hurt_levels_vampire_crippled"),
    (-INFINITY, "hurt_levels_vampire_incapacitated"),
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
    return levels_list[hurt_level], health_lines

def prettyHealth(trait, lid, levels_list = hurt_levels_vampire):
    penalty, parsed = parseHealth(trait, levels_list)
    prettytext = f'{trait["traitName"]}:'
    for line in parsed:
        prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], line)))
    return lp.get(lid, penalty[1]) +"\n"+ prettytext

def prettyFDV(trait, lid):
    return defaultTraitFormatter(trait, lid)

blood_emojis = [":drop_of_blood:", ":droplet:"]
will_emojis = [":white_square_button:", ":white_large_square:"]

def prettyMaxPointTracker(trait, lid, emojis = [":black_circle:", ":white_circle:"], separator = ""):
    pretty = f"{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}\n"
    pretty += separator.join([emojis[0]]*trait['cur_value'])
    pretty += separator
    pretty += separator.join([emojis[1]]*(trait['max_value']-trait['cur_value']))
    return pretty

def prettyPointAccumulator(trait, lid):
    return f"{trait['traitName']}: {trait['cur_value']}"

def prettyTextTrait(trait, lid):
    return f"{trait['traitName']}: {trait['text_value']}"

def prettyGeneration(trait, lid):
    return f"{13 - trait['cur_value']}a generazione\n{prettyDotTrait(trait)}"

def getTraitFormatter(trait):
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
            return lambda x, y: prettyMaxPointTracker(x, y, blood_emojis)
        else:
            return lambda x, y: prettyMaxPointTracker(x, y, will_emojis, " ")
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
            prettyFormatter = getTraitFormatter(trait)
            return prettyFormatter(trait, lid)

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
    prettyFormatter = getTraitFormatter(trait)
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
            return prettyFormatter(trait, lid)
        elif u == 0:
            trait = dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
            return prettyFormatter(trait, lid)+'\n(nessuna modifica effettuata)'
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
        response = prettyFormatter(trait, lid)        
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
        response = prettyFormatter(trait, lid)
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
        response = prettyFormatter(trait, lid)
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
        response = prettyFormatter(trait, lid)

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
    helptext = "Argomenti: nome breve (senza spazi), @menzione al proprietario (oppure Discord ID), nome completo del personaggio (spazi ammessi)"
    if len(args) < 3:
        return helptext
    else:
        chid = args[0].lower()
        v, owner = await validateDiscordMentionOrID(args[1])
        if not v:
            raise BotException("Menziona il proprietario del personaggio con @nome on con il suo discord ID")

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
            iu, _ = dbm.isUser(owner)
            if not iu:
                user = await bot.fetch_user(owner)
                dbm.registerUser(owner, user.name, default_language)
            dbm.newCharacter(chid, fullname, owner)
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
    
    # validation
    charid = args[0].lower()
    isChar, character = dbm.isValidCharacter(charid)
    if not isChar:
        raise BotException(f"Il personaggio {charid} non esiste!")
    
    chronid = args[1].lower()
    vc, chronicle = dbm.isValidChronicle(chronid)
    if not vc:
        raise BotException(f"La cronaca {chronid} non esiste!") 

    # permission checks
    issuer = str(ctx.message.author.id)
    st, _ = dbm.isChronicleStoryteller(issuer, chronicle['id'])
    ba, _ = dbm.isBotAdmin(issuer)
    if not (st or ba):
        raise BotException("Per associare un pg ad una cronaca necessario essere Admin o Storyteller di quella cronaca")
    
    is_linked, _ = dbm.isCharacterLinkedToChronicle(charid, chronid)
    if is_linked:
        return f"C'è già un associazione tra {character['fullname']} e {chronicle['name']}"
    else:
        dbm.db.insert("ChronicleCharacterRel", chronicle=chronid, playerchar=charid)
        return f"{character['fullname']} ora gioca a {chronicle['name']}"

async def pgmod_chronicleRemove(ctx, args):
    helptext = "Argomenti: nome breve del pg, nome breve della cronaca"
    if len(args) != 2:
        return helptext
    
    # validation
    charid = args[0].lower()
    isChar, character = dbm.isValidCharacter(charid)
    if not isChar:
        raise BotException(f"Il personaggio {charid} non esiste!")

    chronid = args[1].lower()
    vc, chronicle = dbm.isValidChronicle(chronid)
    if not vc:
        raise BotException(f"La cronaca {chronid} non esiste!")

    # permission checks
    issuer = str(ctx.message.author.id)
    st, _ = dbm.isChronicleStoryteller(issuer, chronicle['id'])
    ba, _ = dbm.isBotAdmin(issuer)
    if not (st or ba):
        raise BotException("Per rimuovere un pg da una cronaca necessario essere Admin o Storyteller di quella cronaca")
    
    is_linked, _ = dbm.isCharacterLinkedToChronicle(charid, chronid)
    if is_linked:
        dbm.db.delete("ChronicleCharacterRel", where = 'playerchar=$playerchar and chronicle=$chronicleid', vars=dict(chronicleid=chronid, playerchar=charid))
        return f"{character['fullname']} ora non gioca più a  {chronicle['name']}"
    else:
        return f"Non c\'è un\'associazione tra {character['fullname']} e {chronicle['name']}"


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
    "addt": [pgmod_traitAdd, "Aggiunge tratto ad un personaggio"],
    "modt": [pgmod_traitMod, "Modifica un tratto di un personaggio"],
    "rmt": [pgmod_traitRM, "Rimuovi un tratto ad un personaggio"],
    "link": [pgmod_chronicleAdd, "Aggiunge un personaggio ad una cronaca"],
    "unlink": [pgmod_chronicleRemove, "Disassocia un personaggio da una cronaca"]
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
    if len(args) != 2:
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

async def gmadm_stlink(ctx, args):
    issuer = str(ctx.message.author.id)
    lid = getLanguage(issuer, dbm)
    helptext = lp.get(lid, "help_gmadm_stlink")

    if len(args) == 0 or len(args) > 2:
        return helptext
    
    # validation
    chronid = args[0].lower()
    vc, _ = dbm.isValidChronicle(chronid)
    if not vc:
        raise BotException(f"La cronaca {chronid} non esiste!")

    # permission checks
    st, _ = dbm.isChronicleStoryteller(issuer, chronid)
    ba, _ = dbm.isBotAdmin(issuer)
    if not (st or ba):
        raise BotException("Per collegare Storyteller e cronaca è necessario essere Admin o Storyteller di quella cronaca")

    
    target_st = None
    if len(args) == 1:
        target_st = issuer
    else:
        vt, target_st = await validateDiscordMentionOrID(args[1])
        if not vt:
            raise BotException(f"Menziona lo storyteller con @ o inserisci il suo Discord ID") 
    
    t_st, _ = dbm.isStoryteller(target_st)
    if not t_st:
        raise BotException(f"L'utente selezionato non è uno storyteller") 
    t_stc, _ = dbm.isChronicleStoryteller(target_st, chronid)
    if t_stc:
        raise BotException(f"L'utente selezionato è già Storyteller per {chronid}")  

    # link
    dbm.db.insert("StoryTellerChronicleRel", storyteller=target_st, chronicle=chronid)
    return f"Cronaca associata"

async def gmadm_stunlink(ctx, args):
    issuer = str(ctx.message.author.id)
    lid = getLanguage(issuer, dbm)
    helptext = lp.get(lid, "help_gmadm_stunlink")

    if len(args) == 0 or len(args) > 2:
        return helptext
    
    # validation
    chronid = args[0].lower()
    vc, _ = dbm.isValidChronicle(chronid)
    if not vc:
        raise BotException(f"La cronaca {chronid} non esiste!")

    target_st = None
    if len(args) == 1:
        target_st = issuer
    else:
        vt, target_st = validateDiscordMention(args[1])
        if not vt:
            raise BotException(f"Menziona lo storyteller con @") 

    # permission checks
    ba, _ = dbm.isBotAdmin(issuer)
    #st, _ = dbm.isChronicleStoryteller(issuer, chronid)
    st = issuer == target_st
    if not (st or ba):
        raise BotException("Gli storyteller possono solo sganciarsi dalle proprie cronache, altrimenti è necessario essere admin")

    t_st, _ = dbm.isStoryteller(target_st)
    if not t_st:
        raise BotException(f"L'utente selezionato non è uno storyteller") 
    
    t_stc, _ = dbm.isChronicleStoryteller(target_st, chronid)
    if not t_stc:
        raise BotException(f"L'utente selezionato non è Storyteller per {chronid}")  

    # link
    n = dbm.db.delete('StoryTellerChronicleRel', where='storyteller=$storyteller and chronicle=$chronicle', vars=dict(storyteller=target_st, chronicle=chronid))
    if n:
        return f"Cronaca disassociata"
    else:
        return f"Nessuna cronaca da disassociare"

async def gmadm_stname(ctx, args):
    issuer = str(ctx.message.author.id)
    lid = getLanguage(issuer, dbm)
    helptext = lp.get(lid, "help_gmadm_stname")

    if len(args) > 1:
        return helptext
    
    target_st = None
    if len(args) == 0:
        target_st = issuer
    else:
        vt, target_st = await validateDiscordMentionOrID(args[0])
        if not vt:
            raise BotException(f"Menziona l'utente con @ o inserisci il suo Discord ID") 

    # permission checks
    ba, _ = dbm.isBotAdmin(issuer)

    if not ba:
        raise BotException("Solo gli admin possono nominare gli storyteller")

    t_st, _ = dbm.isStoryteller(target_st)
    if t_st:
        raise BotException(f"L'utente selezionato è già uno storyteller")
    
    iu, usr = dbm.isUser(target_st)
    name = ""
    if not iu:
        user = await bot.fetch_user(target_st)
        dbm.registerUser(target_st, user.name, default_language)
        name = user.name
    else:
        name = usr['name']
    
    dbm.db.insert("Storyteller",  userid=target_st)
    return f"{name} ora è Storyteller"

async def gmadm_stunname(ctx, args):
    issuer = str(ctx.message.author.id)
    lid = getLanguage(issuer, dbm)
    helptext = lp.get(lid, "help_gmadm_stunname")

    if len(args) > 1:
        return helptext
    
    target_st = None
    if len(args) == 0: #xd
        target_st = issuer
    else:
        vt, target_st = await validateDiscordMentionOrID(args[0])
        if not vt:
            raise BotException(f"Menziona l'utente con @ o inserisci il suo Discord ID") 

    # permission checks
    ba, _ = dbm.isBotAdmin(issuer)

    if not ba:
        raise BotException("Solo gli admin possono de-nominare gli storyteller")

    iu, usr = dbm.isUser(target_st)
    if not iu:
        raise BotException("Utente non registrato")        
    name = usr['name']

    t_st, _ = dbm.isStoryteller(target_st)
    if not t_st:
        raise BotException(f"L'utente selezionato non è uno storyteller")
    
    n = dbm.db.delete('Storyteller', where='userid=$userid', vars=dict(userid=target_st)) #foreign key is set to cascade. this will also unlink from all chronicles
    if n:
        return f"{name} non è più Storyteller"
    else:
        return f"Nessuna modifica fatta"
    

async def gmadm_deleteTrait(ctx, args):
    return "non implementato"

gameAdmin_subcommands = {
    "listChronicles": [gmadm_listChronicles, "Elenca le cronache"],
    "newChronicle": [gmadm_newChronicle, "Crea una nuova cronaca associata allo ST che invoca il comando"],
    "newTrait": [gmadm_newTrait, "Crea nuovo tratto"],
    "updt": [gmadm_updateTrait, "Modifica un tratto"],
    "delet": [gmadm_deleteTrait, "Cancella un tratto (non implementato)"], #non implementato
    "st_link": [gmadm_stlink, "Associa uno storyteller ad una cronaca"],
    "st_unlink": [gmadm_stunlink, "Disassocia uno storyteller da una cronaca"],
    "st_name": [gmadm_stname, "Nomina storyteller"],
    "st_unname": [gmadm_stunname, "De-nomina storyteller"]
    # todo: lista storyteller
    # todo: dissociazioni varie
    }

def generateNestedCmd(cmd_name, cmd_brief, cmd_dict):
    longdescription = "\n".join(list(map(lambda x: botcmd_prefixes[0]+cmd_name+" "+x+" [arg1, ...]: "+cmd_dict[x][1], cmd_dict.keys())))  + "\n\nInvoca un sottocomando senza argomenti per avere ulteriori informazioni sugli argomenti"

    @bot.command(name=cmd_name, brief=cmd_brief, description = longdescription)
    async def generatedCommand(ctx, *args):
        #issuer = ctx.message.author.id
        #lid = getLanguage(issuer, dbm)
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
