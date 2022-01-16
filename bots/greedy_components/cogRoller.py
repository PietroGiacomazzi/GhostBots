import random
from dataclasses import dataclass
from typing import AnyStr, Callable
from discord.ext import commands

from greedy_components import greedyBase as gb

import support.vtm_res as vtm_res
import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB


#IMPORTANT: 
# longer versions first. DO NOT put a variant before one that contains it -> it will break the emergency splitting
# do NOT have variants that are contained in OTHER command lists, otherwise it will break the emergency splitting in a wai that is VERY hard to debug
# TODO: prevent startup if above conditions are not met
SOMMA_CMD = ["somma", "lapse", "sum"]
DIFF_CMD = ["difficoltà", "difficolta", "difficulty", "diff", "diff."]
MULTI_CMD = ["multi", "mlt"]
DANNI_CMD = ["danni", "danno", "dmg", "damage"]
PROGRESSI_CMD = ["progressi", "progress"]
SPLIT_CMD = ["split"]
PENALITA_CMD = ["penalita", "penalità", "penalty"]
DADI_CMD = ["dadi", "dice"]
ADD_CMD = "+"
SUB_CMD = "-"
PERMANENTE_CMD = ["permanente", "permanent", "perm"]
STATISTICS_CMD = ["statistica", "stats", "stat"]
MINSUCC_CMD = ['minsucc', 'mins', 'ms']

SOAK_CMD = ["soak", "assorbi"]
INIZIATIVA_CMD = ["iniziativa", "initiative", "iniz"]
RIFLESSI_CMD = ["riflessi", "reflexes", "r"]

RollCat = utils.enum("DICE", "INITIATIVE", "REFLEXES", "SOAK") # macro categoria che divide le azioni di tiro
RollArg = utils.enum("DIFF", "MULTI", "SPLIT", "ADD", "ROLLTYPE", "PENALITA", "DADI", "DADI_PERMANENTI",  "PERMANENTE", "STATS", "CHARACTER", "NFACES", "MINSUCC") # argomenti del tiro
RollType = utils.enum("NORMALE", "SOMMA", "DANNI", "PROGRESSI") # valori dell'argomento RollType
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
                #
                'sttar',
                'trast',
                'strar',
                'sbrat',
                'sbratt'
                ]

def prettyRoll(roll: list, diff: int, canceled: int) -> str: # roll is assumed to be SORTED
    for i in range(0, len(roll)-canceled):
        die = roll[i]
        if die == 1:
            roll[i] = '**1**'
        elif die >= diff:
            roll[i] = die_emoji[die]
        else:
            roll[i] = str(die)
    for i in range(len(roll)-canceled, len(roll)):
        roll[i] = f"**~~{roll[i]}~~**"
    random.shuffle(roll)
    return "["+", ".join(roll)+"]"

class RollStatusFormatter:
    def __init__(self, langProvider: lng.LanguageStringProvider, lid: str):
        self.langProvider = langProvider
        self.langId = lid
    def format(self, n: int):
        raise NotImplementedError("Roll status not implemented") # no point in using a lang string here, the user won't see this

class RollStatusDMG(RollStatusFormatter):
    def format(self, n: int) -> str:
        if n == 1:
            return self.langProvider.get(self.langId, 'roll_status_dmg_1dmg')
        elif n > 1:
            return self.langProvider.get(self.langId, "roll_status_dmg_ndmg", n) 
        else:
            return self.langProvider.get(self.langId, 'roll_status_dmg_0dmg')

class RollStatusProgress(RollStatusFormatter):
    def format(self, n: int) -> str:
        if n == 1:
            return self.langProvider.get(self.langId, 'roll_status_prg_1hr')
        elif n > 1:
            return self.langProvider.get(self.langId, 'roll_status_prg_nhr', n) 
        else:
            return self.langProvider.get(self.langId, 'roll_status_prg_0hr')


class RollStatusNormal(RollStatusFormatter):
    def __init__(self, langProvider: lng.LanguageStringProvider, lid: str, minsucc: int = 1):
        super(RollStatusNormal, self).__init__(langProvider, lid)
        self.minsucc = minsucc
    def format(self, n: int) -> str:
        if n == -2:
            return self.langProvider.get(self.langId, 'roll_status_normal_dramafail')
        elif n == -1:
            return self.langProvider.get(self.langId, 'roll_status_normal_critfail')
        elif n >= self.minsucc:
            if n == 1:
                return self.langProvider.get(self.langId, 'roll_status_normal_1succ')
            elif n > 1:
                return self.langProvider.get(self.langId, 'roll_status_normal_nsucc', n)
        else:
            return self.langProvider.get(self.langId, 'roll_status_normal_fail')

class RollStatusReflexes(RollStatusFormatter):
    def format(self, n: int) -> str:
        if n >= 1:
            return self.langProvider.get(self.langId, 'roll_status_hitormiss_success') 
        else:
            return self.langProvider.get(self.langId, 'roll_status_hitormiss_fail')

class RollStatusSoak(RollStatusFormatter):
    def format(self, n: int) -> str:
        if n == 1:
            return self.langProvider.get(self.langId, 'roll_status_soak_1dmg') 
        elif n > 1:
            return self.langProvider.get(self.langId, 'roll_status_soak_ndmg', n) 
        else:
            return self.langProvider.get(self.langId, 'roll_status_soak_0dmg') 


def findSplit(idx: int, splits: list) -> list:
    for si in range(len(splits)):
        if idx == splits[si][0]:
            return splits[si][1:]
    return []


@dataclass
class DiceExprParsed:
    """ Parsed dice expression """
    n_dice: int
    n_dice_permanent: int
    n_faces: int
    character: object


class GreedyGhostCog_Roller(commands.Cog):
    def __init__(self, bot: gb.GreedyGhost):
        self.bot = bot

    def rollAndFormatVTM(self, ctx: commands.Context, ndice: int, nfaces: int, diff: int, statusFunc: RollStatusFormatter, extra_succ: int = 0, canceling: bool = True, spec: bool = False, statistics: bool = False, minsucc: int = 1) -> str:
        if statistics:
            statistics_samples = int(self.bot.config['BotOptions']['stat_samples'])
            total_successes = 0 # total successes, even when the roll is a fail
            pass_successes = 0 # total of successes only when the roll succeeds
            passes = 0
            fails = 0
            critfails = 0
            for i in range(statistics_samples):
                successi, _, _ = vtm_res.roller(ndice, nfaces, diff, canceling, spec, extra_succ)
                if successi > 0:
                    if successi > minsucc:
                        passes += 1
                        pass_successes += successi
                    else:
                        fails += 1
                    total_successes += successi
                elif successi == 0 or successi == -2:
                    fails += 1
                else:
                    critfails += 1
            response =  self.bot.getStringForUser(ctx,
                'roll_status_statistics_info',
                statistics_samples,
                ndice,
                nfaces,
                diff,
                extra_succ,
                self.bot.getStringForUser(ctx, 'roll_status_with') if canceling else self.bot.getStringForUser(ctx,'roll_status_without'),
                self.bot.getStringForUser(ctx, 'roll_status_with') if spec else self.bot.getStringForUser(ctx, 'roll_status_without'),
                round(100*passes/statistics_samples, 2),
                round(100*(fails+critfails)/statistics_samples, 2),
                round(100*fails/statistics_samples, 2),
                round(100*critfails/statistics_samples, 2),
                round(total_successes/statistics_samples, 2),
                round(pass_successes/passes, 2)
            )
            return response
        else:        
            successi, tiro, cancels = vtm_res.roller(ndice, nfaces, diff, canceling, spec, extra_succ)
            pretty = prettyRoll(tiro, diff, cancels)
            status = statusFunc.format(successi)
            response = status + f' (diff {diff}, min. {minsucc}): {pretty}' 
            if extra_succ > 0:
                response += f' **+{extra_succ}**'
            if extra_succ < 0:
                response += f' **{extra_succ}**'
            return response

    def parseDiceExpression_Dice(self, ctx: commands.Context, what: str, forced10: bool = False) -> DiceExprParsed:
        split = what.split("d")
        if len(split) > 2:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_toomany_d"))
        if len(split) == 1:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_not_XdY", split[0] ) )
        if split[0] == "":
            split[0] = "1"
        if not split[0].isdigit():
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_not_positive_integer", split[0]))
        if split[1] == "":
            split[1] = "10"
        if not split[1].isdigit():
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_not_positive_integer", split[1]))
        n = int(split[0])
        faces = int(split[1])
        if forced10 and faces != 10:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_not_d10", split[1]))
        if n == 0:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_not_gt0", n) )
        if  faces == 0:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_not_gt0", faces))
        if n > int(self.bot.config['BotOptions']['max_dice']):
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_toomany_dice", n) )
        if faces > int(self.bot.config['BotOptions']['max_faces']):
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_toomany_faces", faces))

        return DiceExprParsed(n, n, faces, None)

    def parseDiceExpression_Mixed(self, ctx: commands.Context, what: str, firstNegative: bool = False, forced10: bool = True, character = None) -> DiceExprParsed:
        lid = self.bot.getLID(ctx.message.author.id)

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
                    parsed_expr =  self.parseDiceExpression_Dice(ctx, term, forced10)  
                    n_term = parsed_expr.n_dice
                    n_term_perm = parsed_expr.n_dice_permanent
                    nf = parsed_expr.n_faces
                    saw_notd10 = saw_notd10 or (nf != 10)
                    if faces and (faces != nf): # we do not support mixing different face numbers for now
                        raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_face_mixing"))
                    faces = nf
                except gb.BotException as e: # or a trait
                    try:
                        if not character:
                            character = self.bot.dbm.getActiveChar(ctx) # can raise
                        temp = self.bot.dbm.getTrait_LangSafe(character['id'], term, lid) 
                        n_term = temp['cur_value']
                        n_term_perm = temp['max_value']
                        saw_trait = True
                        faces = 10
                    except ghostDB.DBException as edb:
                        raise gb.BotException("\n".join([ self.bot.getStringForUser(ctx, "string_error_notsure_whatroll"), f'{e}', f'{self.bot.languageProvider.formatException(lid, edb)}']) )
                
                if j > 0 or (i == 0 and firstNegative):
                    n -= n_term
                    n_perm -= n_term_perm
                else:
                    n += n_term
                    n_perm += n_term_perm

        if saw_trait and saw_notd10: # forced10 = false only lets through non d10 expressions that DO NOT use traits
            raise gb.BotException( self.bot.getStringForUser(ctx, "string_error_not_d10"))

        return DiceExprParsed(n, n_perm, faces, character)

    def validateInteger(self, ctx: commands.Context, args: list, i: int, err_msg: str = None) -> utils.ValidatedIntSeq:
        if err_msg == None:
            err_msg = self.bot.getStringForUser(ctx, "string_errorpiece_integer") 
        try:
            return i, int(args[i])
        except ValueError:
            raise ValueError(self.bot.getStringForUser(ctx, "string_error_x_isnot_y", args[i], err_msg))

    def validateBoundedInteger(self, ctx: commands.Context, args: list, i: int, min_val: int, max_val: int, err_msg : str = None) -> utils.ValidatedIntSeq:
        if err_msg == None:
            err_msg = self.bot.getStringForUser(ctx, "string_errorpiece_number_in_range", min_val, max_val) 
        j, val = self.validateInteger(ctx, args, i)
        if val < min_val or val > max_val:
            raise ValueError(self.bot.getStringForUser(ctx, "string_error_x_isnot_y", args[i], err_msg))
        return j, val

    def validateNumber(self, ctx: commands.Context, args: list, i: int, err_msg: str = None) -> utils.ValidatedIntSeq:
        if err_msg == None:
            err_msg = self.bot.getStringForUser(ctx, "string_errorpiece_positive_integer") 
        if not args[i].isdigit():
            raise ValueError(self.bot.getStringForUser(ctx, "string_error_x_isnot_y", args[i], err_msg))
        return i, int(args[i])

    def validateBoundedNumber(self, ctx: commands.Context, args, i, min_bound, max_bound, err_msg = None) -> utils.ValidatedIntSeq:
        if err_msg == None:
            err_msg = self.bot.getStringForUser(ctx, "string_errorpiece_number_in_range", min_bound, max_bound) 
        _, num = self.validateNumber(ctx, args, i)
        if num > max_bound or num < min_bound:
            raise ValueError(self.bot.getStringForUser(ctx, "string_error_x_isnot_y", num, err_msg) )
        return i, num

    def validateIntegerGreatZero(self, ctx: commands.Context, args: list, i: int) -> utils.ValidatedIntSeq:
        return self.validateBoundedNumber(ctx, args, i, 1, utils.INFINITY, self.bot.getStringForUser(ctx, "string_errorpiece_integer_gt0") )

    def validateDifficulty(self, ctx: commands.Context,  args: list, i: int) -> utils.ValidatedIntSeq:
        return self.validateBoundedNumber(ctx, args, i, 2, 10, self.bot.getStringForUser(ctx, "string_errorpiece_valid_diff") )


    # input: sequenza di argomenti per .roll
    # output: dizionario popolato con gli argomenti validati
    def parseRollArgs(self, ctx: commands.Context, args_raw: tuple) -> dict:
        parsed = {
            RollArg.ROLLTYPE: RollType.NORMALE, # default
            RollArg.MINSUCC: 1,
            RollArg.CHARACTER: None
            }
        args = list(args_raw)

        # detaching + or - from the end of an expression needs to be done immediately
        i = 0
        while i < len(args): # TODO just split everything by ADD_CMD and SUB_CMD so that everything is separated past this pointt
            if args[i].endswith(ADD_CMD) and args[i] != ADD_CMD: 
                args = args[:i] + [args[i][:-1], ADD_CMD] + args[i+1:]
            if args[i].endswith(SUB_CMD) and args[i] != SUB_CMD: 
                args = args[:i] + [args[i][:-1], SUB_CMD] + args[i+1:]
            i += 1

        # do the actual parsing
    
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
                raise ValueError(self.bot.getStringForUser(ctx, "string_arg_X_in_Y_notclear", args[i], utils.prettyHighlightError(args, i)) )
            last_i = i
            
            if args[i] in SOMMA_CMD:
                parsed[RollArg.ROLLTYPE] = RollType.SOMMA
            elif args[i] in DIFF_CMD:
                if RollArg.DIFF in parsed:
                    raise ValueError(self.bot.getStringForUser(ctx, "string_error_multiple_diff"))
                if len(args) == i+1:
                    raise ValueError(self.bot.getStringForUser(ctx, "string_error_x_what", args[i]))
                i, diff = self.validateDifficulty(ctx, args, i+1)
                parsed[RollArg.DIFF] = diff
            elif args[i] in MULTI_CMD:
                if RollArg.SPLIT in parsed:
                    raise ValueError(self.bot.getStringForUser(ctx, "string_error_split_before_multi"))
                if RollArg.MULTI in parsed:
                    raise ValueError(self.bot.getStringForUser(ctx, "string_error_multiple_multi"))
                if len(args) == i+1:
                    raise ValueError(self.bot.getStringForUser(ctx, "string_error_x_what", args[i]))
                i, multi = self.validateBoundedNumber(ctx, args, i+1, 2, utils.INFINITY, self.bot.getStringForUser(ctx, "string_errorpiece_validarg_multi", args[i]) )# controlliamo il numero di mosse sotto, dopo aver applicato bonus o penalità al numero di dadi
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
                        raise ValueError(self.bot.getStringForUser(ctx, "string_error_X_takes_Y_params", args[i], 3) +" "+ self.bot.getStringForUser(ctx, "string_errorpiece_with_multi") )
                    i, temp = self.validateIntegerGreatZero(ctx, args, i+1)
                    roll_index = temp-1
                    if roll_index >= parsed[RollArg.MULTI]:
                        raise ValueError(self.bot.getStringForUser(ctx, "string_error_split_X_higherthan_multi_Y", args[i+1], multi) )
                    if sum(filter(lambda x: x[0] == roll_index, split)): # cerco se ho giò splittato questo tiro
                        raise ValueError(self.bot.getStringForUser(ctx, "string_error_already_splitting_X", roll_index+1) )
                else: # not an elif because reasons
                    if len(args) < i+3:
                        raise ValueError(self.bot.getStringForUser(ctx,  "string_error_X_takes_Y_params", args[i], 2))
                i, d1 = self.validateIntegerGreatZero(ctx, args, i+1)
                i, d2 = self.validateIntegerGreatZero(ctx, args, i+1)
                split.append( [roll_index] + list(map(int, [d1, d2])))
                parsed[RollArg.SPLIT] = split # save the new split
            elif args[i] in [ADD_CMD, SUB_CMD]:
                if len(args) == i+1:
                    raise ValueError(self.bot.getStringForUser(ctx, "string_error_x_what", args[i]))
                # 3 options here: XdY (and variants), trait(s), integers.
                try:
                    sign = ( 1 - 2 * ( args[i] == SUB_CMD)) # 1 or -1 depenging on args[i]
                    i, add = self.validateIntegerGreatZero(ctx, args, i+1) # simple positive integer -> add as successes
                    if RollArg.ADD in parsed:
                        parsed[RollArg.ADD] += add * sign
                    else:
                        parsed[RollArg.ADD] = add * sign
                except ValueError as e_add: # not an integer -> try to parse it as a dice expression
                    parsed_expr = self.parseDiceExpression_Mixed(ctx, args[i+1], firstNegative = args[i] == SUB_CMD, forced10 = (i != 0), character = parsed[RollArg.CHARACTER]) # TODO: we're locked into d10s by this point, non-vtm dice rolls are limited to the first argument for .roll
                    #n_dice = parsed_expr.n_dice
                    #n_dice_perm = parsed_expr.n_dice_permanent
                    #nfaces = parsed_expr.n_faces
                    #character = parsed_expr.character
                    if RollArg.DADI in parsed:
                        parsed[RollArg.DADI] += parsed_expr.n_dice
                        parsed[RollArg.DADI_PERMANENTI] += parsed_expr.n_dice_permanent 
                    else:
                        parsed[RollArg.DADI] = parsed_expr.n_dice
                        parsed[RollArg.DADI_PERMANENTI] = parsed_expr.n_dice_permanent
                    if parsed_expr.character != None:
                        parsed[RollArg.CHARACTER] = parsed_expr.character
                    if RollArg.NFACES in parsed and parsed[RollArg.NFACES] != parsed_expr.n_faces:
                        raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_face_mixing"))
                    parsed[RollArg.NFACES] = parsed_expr.n_faces
                    i += 1
            elif args[i] in PENALITA_CMD:
                parsed[RollArg.PENALITA] = True
            elif args[i] in DADI_CMD:
                if len(args) == i+1:
                    raise ValueError(self.bot.getStringForUser(ctx, "string_error_x_what", args[i]))
                i, val = self.validateBoundedInteger(ctx, args, i+1, -100, +100) # this is also checked later on the final number
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
            elif args[i] in MINSUCC_CMD:
                i, minsucc = self.validateIntegerGreatZero(ctx, args, i+1) # simple positive integer -> add as successes
                parsed[RollArg.MINSUCC] = minsucc
            else:
                #try parsing a dice expr
                try:
                    parsed_expr = self.parseDiceExpression_Mixed(ctx, args[i], firstNegative = False, forced10 = (i != 0), character = parsed[RollArg.CHARACTER])

                    if RollArg.DADI in parsed:
                        parsed[RollArg.DADI] += parsed_expr.n_dice
                        parsed[RollArg.DADI_PERMANENTI] += parsed_expr.n_dice_permanent 
                    else:
                        parsed[RollArg.DADI] = parsed_expr.n_dice
                        parsed[RollArg.DADI_PERMANENTI] = parsed_expr.n_dice_permanent
                    if parsed_expr.character != None:
                        parsed[RollArg.CHARACTER] = parsed_expr.character
                    if RollArg.NFACES in parsed and parsed[RollArg.NFACES] != parsed_expr.n_faces:
                        raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_face_mixing"))
                    parsed[RollArg.NFACES] = parsed_expr.n_faces
                except gb.BotException as e:
                    # provo a staccare parametri attaccati
                    did_split = False
                    idx = 0
                    tests = DIFF_CMD+MULTI_CMD+DADI_CMD+[ADD_CMD, SUB_CMD]
                    while not did_split and idx < len(tests):
                        cmd = tests[idx]
                        if args[i].startswith(cmd):
                            args = args[:i] + [cmd, args[i][len(cmd):]] + args[i+1:]
                            did_split = True
                        idx += 1

                    if not did_split: # F
                        raise gb.BotException("\n".join([ self.bot.getStringForUser(ctx, "string_arg_X_in_Y_notclear", args[i], utils.prettyHighlightError(args, i)), f'{e}']) )
                    else:
                        i -= 1 # forzo rilettura
            i += 1
        return parsed

    async def roll_initiative(self, ctx: commands.Context, parsed: dict) -> str:
        if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE or RollArg.DIFF in parsed:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_roll_invalid_param_combination") )
        lid = self.bot.getLID(ctx.message.author.id)
        add = parsed[RollArg.ADD] if RollArg.ADD in parsed else 0
        raw_roll = random.randint(1, 10)
        bonuses_log = []
        bonus = add
        if add:
            bonuses_log.append(self.bot.getStringForUser(ctx, "string_bonus_X", add))
        try:
            character = self.bot.dbm.getActiveChar(ctx)
            for traitid in ['prontezza', 'destrezza', 'velocità']:
                try:
                    val = self.bot.dbm.getTrait_LangSafe(character['id'], traitid, lid)
                    bonus += val["cur_value"]
                    bonuses_log.append( f'{val["traitName"]}: {val["cur_value"]}' )
                except ghostDB.DBException:
                    pass
        except ghostDB.DBException:
            bonuses_log.append(self.bot.getStringForUser(ctx, "string_comment_no_pc"))
        details = ""
        if len(bonuses_log):
            details = ", ".join(bonuses_log)
        final_val = raw_roll+bonus
        return f'{self.bot.getStringForUser(ctx, "string_initiative")}: **{final_val}**\n{self.bot.getStringForUser(ctx, "string_roll")}: [{raw_roll}] + {bonus if bonus else 0} ({details})'

    async def roll_reflexes(self, ctx: commands.Context, parsed: dict) -> str:
        if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE or RollArg.DIFF in parsed:    
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_roll_invalid_param_combination"))
        lid = self.bot.getLID(ctx.message.author.id)
        add = parsed[RollArg.ADD] if RollArg.ADD in parsed else 0
        character = self.bot.dbm.getActiveChar(ctx)
        volonta = self.bot.dbm.getTrait_LangSafe(character['id'], 'volonta', lid)#['cur_value']
        prontezza = self.bot.dbm.getTrait_LangSafe(character['id'], 'prontezza', lid)#['cur_value']
        diff = 10 - prontezza['cur_value']
        response = f'{volonta["traitName"]}: {volonta["cur_value"]}, {prontezza["traitName"]}: {prontezza["cur_value"]} -> {volonta["cur_value"]}d{10} {self.bot.getStringForUser(ctx, "string_diff")} ({diff} = {10}-{prontezza["cur_value"]})\n'
        response += self.rollAndFormatVTM(ctx, volonta['cur_value'], 10, diff, RollStatusReflexes(self.bot.languageProvider, lid), add, statistics = RollArg.STATS in parsed)
        return response

    async def roll_soak(self, ctx: commands.Context, parsed: dict) -> str:
        if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or RollArg.ADD in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_roll_invalid_param_combination"))
        lid = self.bot.getLID(ctx.message.author.id)
        diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
        character = self.bot.dbm.getActiveChar(ctx)
        pool = self.bot.dbm.getTrait_LangSafe(character['id'], 'costituzione', lid)['cur_value']
        try:
            pool += self.bot.dbm.getTrait_LangSafe(character['id'], 'robustezza', lid)['cur_value']
        except ghostDB.DBException:
            pass
        return self.rollAndFormatVTM(ctx, pool, 10, diff, RollStatusSoak(self.bot.languageProvider, lid), 0, False, statistics = RollArg.STATS in parsed)

    async def roll_dice(self, ctx: commands.Context, parsed: dict) -> str:
        lid =  self.bot.getLID(ctx.message.author.id)
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
                character = self.bot.dbm.getActiveChar(ctx)
            health = self.bot.dbm.getTrait_LangSafe(character['id'], 'salute', lid)
            penalty, _ = utils.parseHealth(health)
            ndice += penalty[0]

        max_dice = int(self.bot.config['BotOptions']['max_dice'])
        if ndice > max_dice:
            raise gb.BotException(self.bot.getStringForUser(ctx,  "string_error_toomany_dice", max_dice))
        if ndice <= 0:
            raise gb.BotException(self.bot.getStringForUser(ctx,  "string_error_toofew_dice", ndice) )

        # check n° di mosse per le multiple
        if RollArg.MULTI in parsed:
            multi = parsed[RollArg.MULTI]
            max_moves = int( ((ndice+1)/2) -0.1) # (ndice+1)/2 è il numero di mosse in cui si rompe, non il massimo. togliendo 0.1 e arrotondando per difetto copro sia il caso intero che il caso con .5
            if max_moves == 1:
                raise gb.BotException(self.bot.getStringForUser(ctx,  "string_error_not_enough_dice_multi") )
            elif multi > max_moves:
                raise gb.BotException(self.bot.getStringForUser(ctx,  "string_error_not_enough_dice_multi_MAX_REQUESTED", max_moves, ndice) )

        # decido cosa fare

        add = parsed[RollArg.ADD] if RollArg.ADD in parsed else 0

        # simple roll
        if not (RollArg.MULTI in parsed) and not (RollArg.DIFF in parsed) and not (RollArg.SPLIT in parsed) and (parsed[RollArg.ROLLTYPE] == RollType.NORMALE or parsed[RollArg.ROLLTYPE] == RollType.SOMMA):
            raw_roll = list(map(lambda x: random.randint(1, nfaces), range(ndice)))
            if add != 0 or parsed[RollArg.ROLLTYPE] == RollType.SOMMA:
                roll_sum = sum(raw_roll) + add
                return f'{repr(raw_roll)} {"+" if add >= 0 else "" }{add} = **{roll_sum}**'
            else:
                return repr(raw_roll)
            
        if nfaces != 10:
            raise gb.BotException(self.bot.getStringForUser(ctx,  'string_error_not_d10') )
        # past this point, we are in d10 territory
        
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
                    raise gb.BotException(self.bot.getStringForUser(ctx,  "string_error_missing_diff"))
                for i in range(multi):
                    parziale = ''
                    ndadi = ndice-i-multi
                    split_diffs = findSplit(i, split)
                    if len(split_diffs):
                        pools = [(ndadi-ndadi//2), ndadi//2]
                        for j in range(len(pools)):
                            parziale += f'\n{self.bot.getStringForUser(ctx,  "string_roll")} {j+1}: '+ self.rollAndFormatVTM(ctx, pools[j], nfaces, split_diffs[j], RollStatusNormal(self.bot.languageProvider, lid, parsed[RollArg.MINSUCC]), statistics = stats)
                    else:
                        parziale = self.rollAndFormatVTM(ctx, ndadi, nfaces, parsed[RollArg.DIFF], RollStatusNormal(self.bot.languageProvider, lid, parsed[RollArg.MINSUCC]), statistics = stats, minsucc = parsed[RollArg.MINSUCC])
                    response += f'\n{self.bot.getStringForUser(ctx,  "string_action")} {i+1}: '+parziale # line break all'inizio tanto c'è il @mention
            else:
                raise gb.BotException(self.bot.getStringForUser(ctx,  "string_error_roll_invalid_param_combination"))
        else: # 1 tiro solo 
            if RollArg.SPLIT in parsed:
                split = parsed[RollArg.SPLIT]
                if parsed[RollArg.ROLLTYPE] == RollType.NORMALE:
                    pools = [(ndice-ndice//2), ndice//2]
                    response = ''
                    for i in range(len(pools)):
                        parziale = self.rollAndFormatVTM(ctx, pools[i], nfaces, split[0][i+1], RollStatusNormal(self.bot.languageProvider, lid, parsed[RollArg.MINSUCC] ), statistics = stats)
                        response += f'\n{self.bot.getStringForUser(ctx, "string_roll")} {i+1}: '+parziale
                else:
                    raise gb.BotException(self.bot.getStringForUser(ctx,  "string_error_roll_invalid_param_combination"))
            else:
                if parsed[RollArg.ROLLTYPE] == RollType.NORMALE: # tiro normale
                    if not RollArg.DIFF in parsed:
                        raise gb.BotException(self.bot.getStringForUser(ctx,  "string_error_missing_diff"))
                    response = self.rollAndFormatVTM(ctx, ndice, nfaces, parsed[RollArg.DIFF], RollStatusNormal(self.bot.languageProvider, lid, parsed[RollArg.MINSUCC] ), add, statistics = stats, minsucc = parsed[RollArg.MINSUCC])
                elif parsed[RollArg.ROLLTYPE] == RollType.DANNI:
                    diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
                    response = self.rollAndFormatVTM(ctx, ndice, nfaces, diff, RollStatusDMG(self.bot.languageProvider, lid), add, False, statistics = stats)
                elif parsed[RollArg.ROLLTYPE] == RollType.PROGRESSI:
                    diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
                    response = self.rollAndFormatVTM(ctx, ndice, nfaces, diff, RollStatusProgress(self.bot.languageProvider, lid), add, False, True, statistics = stats)
                else:
                    raise gb.BotException(self.bot.getStringForUser(ctx,  "string_error_unknown_rolltype", RollArg.ROLLTYPE))
        return response

    @commands.command(name='roll', aliases=['r', 'tira', 'lancia', 'rolla'], brief = 'Tira dadi', description = roll_longdescription) 
    async def roll(self, ctx: commands.Context, *args):
        if len(args) == 0:
            raise gb.BotException(self.bot.getStringForUser(ctx, "string_error_x_what", "roll")+" diomadonna") #xd
        args_list = list(args)
        
        # capisco che tipo di tiro ho di fronte
        what = args_list[0].lower()

        action = None
        if what in INIZIATIVA_CMD:
            action = RollCat.INITIATIVE
        elif what in RIFLESSI_CMD:
            action = RollCat.REFLEXES
        elif what in SOAK_CMD:
            action = RollCat.SOAK
        else:
            action = RollCat.DICE
        
        # leggo e imposto le varie opzioni
        parsed = None
        start_arg = 0 if action == RollCat.DICE else 1
        try:
            parsed = self.parseRollArgs(ctx, args_list[start_arg:])
        except ValueError as e:
            await self.bot.atSend(ctx, str(e))
            return

        # gestisco i tiri specifici
        response = ''
        if action == RollCat.INITIATIVE:
            response = await self.roll_initiative(ctx, parsed)
        elif action == RollCat.REFLEXES:
            response = await self.roll_reflexes(ctx, parsed)
        elif action == RollCat.SOAK:
            response = await self.roll_soak(ctx, parsed)
        else:
            response = await self.roll_dice(ctx, parsed)
        await self.bot.atSend(ctx, response)
    
    @commands.command(name = 'search', brief = "Cerca un tratto", description = "Cerca un tratto:\n\n .search <termine di ricerca> -> elenco dei risultati")
    async def search_trait(self, ctx: commands.Context, *args):
        if len(args) == 0:
            await self.bot.atSendLang("string_error_no_searchterm")
            return

        searchstring = "%" + (" ".join(args)) + "%"
        lower_version = searchstring.lower()
        traits = self.bot.dbm.db.select("LangTrait", where="langId=$langid and (traitId like $search_lower or traitShort like $search_lower or traitName like $search_string)", vars=dict(search_lower=lower_version, search_string = searchstring, langid=self.bot.getLID(ctx.message.author.id)))
        
        if not len(traits):
            await self.bot.atSendLang("string_msg_no_match")
            return

        response = self.bot.getStringForUser(ctx, "string_msg_found_traits") +":\n"
        for trait in traits:
            response += f"\n {trait['traitShort']} ({trait['traitId']}): {trait['traitName']}"
        await self.bot.atSend(ctx, response)

    @commands.command(brief = "Richiama l'attenzione dello storyteller", description = "Richiama l'attenzione dello storyteller della cronaca attiva nel canale in cui viene invocato")
    async def call(self, ctx: commands.Context, *args):
        character = self.bot.dbm.getActiveChar(ctx)
        sts = self.bot.dbm.getChannelStoryTellers(ctx.channel.id)
        response = f"{character['fullname']} ({ctx.message.author}) richiede la tua attenzione!"
        for st in sts:
            stuser = await self.bot.fetch_user(st['storyteller'])
            response += f' {stuser.mention}'
        await self.bot.atSend(ctx, response)

    @commands.command(brief = "Tira 1d100 per l'inizio giocata", description = "Tira 1d100 per l'inizio giocata")
    async def start(self, ctx: commands.Context, *args):
        await self.bot.atSend(ctx, f'{random.randint(1, 100)}')

    @commands.command(aliases = strat_list, brief = "Tira 1d100 per l'inizio giocata", description = "Tira 1d100 per l'inizio giocata anche se l'invocatore è ubriaco")
    async def strat(self, ctx: commands.Context, *args):
        await self.bot.atSend(ctx, f'{random.randint(1, 100)}, però la prossima volta scrivilo giusto <3')