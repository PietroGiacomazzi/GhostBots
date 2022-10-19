import random
from math import inf
from copy import deepcopy
from typing import Any

from greedy_components import greedyBase as gb

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB
import support.security as sec
import support.gamesystems as gms

#IMPORTANT: 
# longer versions first. DO NOT put a variant before one that contains it -> it will break the fallback splitting
# do NOT have variants that are contained in OTHER command lists, otherwise it will break the fallback splitting in a way that is VERY hard to debug
# TODO: prevent startup if above conditions are not met
SOMMA_CMD = ("somma", "lapse", "sum")
DIFF_CMD = ("difficoltà", "difficolta", "difficulty", "diff", "diff.")
MULTI_CMD = ("multi", "mlt")
DANNI_CMD = ("danni", "danno", "dmg", "damage")
PROGRESSI_CMD = ("progressi", "progress")
SPLIT_CMD = ("split")
PENALITA_CMD = ("penalita", "penalità", "penalty")
DADI_CMD = ("dadi", "dice")
ADD_CMD = "+"
SUB_CMD = "-"
PERMANENTE_CMD = ("permanente", "permanent", "perm")
STATISTICS_CMD = ("statistica", "stats", "stat")
MINSUCC_CMD = ('minsucc', 'mins', 'ms')

SOAK_CMD = ("soak", "assorbi")
INIZIATIVA_CMD = ("iniziativa", "initiative", "iniz")
RIFLESSI_CMD = ("riflessi", "reflexes", "r")

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

class GreedyParseValidationError(gb.GreedyCommandError):
    pass


def prettyRollSTS(roll: list, diff: int, canceled: int) -> str: # roll is assumed to be SORTED
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

class RollFormatter:
    def __init__(self, langProvider: lng.LanguageStringProvider, lid: str):
        self.langProvider = langProvider
        self.langId = lid
    def format(self, item: gms.RollItem) -> str:
        return f'{self.formatHeader(item)}{self.formatRoll(item)}{self.formatTail(item)}'
    def formatHeader(self, item: gms.RollItem):
        return f'{item.tag}: '
    def formatRoll(self, item: gms.RollItem):
        return f'{item.results}'
    def formatTail(self, item: gms.RollItem):
        return ''

class RollFormatter_STS(RollFormatter):
    def formatHead(self, item: gms.RollItem_STS):
        return f'{item.tag}: '
    def formatStatus(self, item: gms.RollItem_STS):
        return f'' 
    def formatDiffSummary(self, item: gms.RollItem_STS):
        return f' (diff {item.difficulty}, min. {item.minsucc})' 
    def formatHeader(self, item: gms.RollItem_STS):
        return f'{self.formatHead(item)}{self.formatStatus(item)}{self.formatDiffSummary(item)}: '
    def formatRoll(self, item: gms.RollItem_STS):
        return prettyRollSTS(item.results, item.difficulty, item.canceled)
    def formatTail(self, item: gms.RollItem_STS):
        if item.extra_succ != 0:
            return f' **{"+" if item.extra_succ > 0  else ""} {item.extra_succ}**'
        return ''

class RollFormatter_STS_DMG(RollFormatter_STS):
    def formatStatus(self, item: gms.RollItem_STS) -> str:
        if item.count_successes == 1:
            return self.langProvider.get(self.langId, 'roll_status_dmg_1dmg')
        elif item.count_successes > 1:
            return self.langProvider.get(self.langId, "roll_status_dmg_ndmg", item.count_successes) 
        else:
            return self.langProvider.get(self.langId, 'roll_status_dmg_0dmg')

class RollFormatter_STS_Progress(RollFormatter_STS):
    def formatStatus(self, item: gms.RollItem_STS) -> str:
        if item.count_successes == 1:
            return self.langProvider.get(self.langId, 'roll_status_prg_1hr')
        elif item.count_successes > 1:
            return self.langProvider.get(self.langId, 'roll_status_prg_nhr', item.count_successes) 
        else:
            return self.langProvider.get(self.langId, 'roll_status_prg_0hr')

class RollFormatter_STS_Normal(RollFormatter_STS):
    def formatStatus(self, item: gms.RollItem_STS) -> str:
        if item.count_successes == -1:
            return self.langProvider.get(self.langId, 'roll_status_normal_critfail')
        elif item.count_successes >= item.minsucc:
            if item.count_successes == 1:
                return self.langProvider.get(self.langId, 'roll_status_normal_1succ')
            elif item.count_successes > 1:
                return self.langProvider.get(self.langId, 'roll_status_normal_nsucc', item.count_successes)
        else:
            return self.langProvider.get(self.langId, 'roll_status_normal_fail')

class RollFormatter_V20HB_Normal(RollFormatter_STS):
    def formatStatus(self, item: gms.RollItem_STS) -> str:
        if item.count_successes == -2:
            return self.langProvider.get(self.langId, 'roll_status_normal_dramafail')
        elif item.count_successes == -1:
            return self.langProvider.get(self.langId, 'roll_status_normal_critfail')
        elif item.count_successes >= item.minsucc:
            if item.count_successes == 1:
                return self.langProvider.get(self.langId, 'roll_status_normal_1succ')
            elif item.count_successes > 1:
                return self.langProvider.get(self.langId, 'roll_status_normal_nsucc', item.count_successes)
        else:
            return self.langProvider.get(self.langId, 'roll_status_normal_fail')

class RollFormatter_STS_Reflexes(RollFormatter_STS):
    def formatStatus(self, item: gms.RollItem_STS) -> str:
        if item.count_successes >= 1:
            return self.langProvider.get(self.langId, 'roll_status_hitormiss_success') 
        else:
            return self.langProvider.get(self.langId, 'roll_status_hitormiss_fail')

class RollFormatter_STS_Soak(RollFormatter_STS):
    def formatStatus(self, item: gms.RollItem_STS) -> str:
        if item.count_successes == 1:
            return self.langProvider.get(self.langId, 'roll_status_soak_1dmg') 
        elif item.count_successes > 1:
            return self.langProvider.get(self.langId, 'roll_status_soak_ndmg', item.count_successes) 
        else:
            return self.langProvider.get(self.langId, 'roll_status_soak_0dmg') 

class RollFormatter_PlainValues(RollFormatter):
    def formatHeader(self, item: gms.RollItem):
        return f''

class RollFormatter_STS_Initiative(RollFormatter):
    def formatRoll(self, item: gms.RollItem_STS):
        raw_roll = item.results[0]
        bonus = item.extra_succ
        final_val = raw_roll + bonus
        return f'**{final_val}**\n{self.langProvider.get(self.langId, "string_roll")}: [{raw_roll}] + {bonus if bonus else 0}'
    def formatTail(self, item: gms.RollItem):
        details = ''
        bonuses_log = item.additional_data
        if not bonuses_log is None and type(bonuses_log) == list and len(bonuses_log):
            details = f' ({", ".join(bonuses_log)})' 
        return details

class RollFormatter_Stats(RollFormatter):
    pass

class RollFormatter_STS_Stats(RollFormatter_Stats):
    def formatRoll(self, item: gms.RollItem_STS):
        statistics_samples, ndice, canceling, spec, passes, fails, critfails, total_successes, pass_successes = item.additional_data
        response = self.langProvider.get(self.langId,
            'roll_status_statistics_info',
            statistics_samples,
            ndice,
            item.faces,
            item.difficulty,
            item.extra_succ,
            item.minsucc,
            self.langProvider.get(self.langId, 'roll_status_with') if canceling else self.langProvider.get(self.langId, 'roll_status_without'),
            self.langProvider.get(self.langId, 'roll_status_with') if spec else self.langProvider.get(self.langId, 'roll_status_without'),
            round(100*passes/statistics_samples, 2),
            round(100*(fails+critfails)/statistics_samples, 2),
            round(100*fails/statistics_samples, 2),
            round(100*critfails/statistics_samples, 2),
            round(total_successes/statistics_samples, 2),
            round(pass_successes/passes, 2)
        )
        return response

class RollOutputter:
    def __init__(self) -> None:
        self.itemFormatters: dict[int, type[RollFormatter]] = {}
    def joinResults(self, results: list[str], rolldata: gms.RollData, ctx: gb.GreedyContext) -> str:
        if rolldata.rolltype == gms.RollType.SUM:
            total = sum(map(lambda x: sum(x.results), rolldata.data))
            return f'{" ".join(results)} = {total}'
        return "\n".join(results)
    def getFormatter(self, rolltype: int):
        return self.itemFormatters[rolltype] if rolltype in self.itemFormatters else RollFormatter
    def getStatsFormatter(self, rolltype: int):
        return RollFormatter_Stats
    def output(self, rolldata: gms.RollData, ctx: gb.GreedyContext) -> str:
        formatterCls = self.getStatsFormatter(rolldata.rolltype) if rolldata.statistics else self.getFormatter(rolldata.rolltype)
        formatter = formatterCls(ctx.getLanguageProvider(), ctx.getLID())
        results = []
        for ri in rolldata.data:
            results.append(formatter.format(ri))
        return self.joinResults(results,  rolldata, ctx)

class RollOutputter_STS(RollOutputter):
    def __init__(self) -> None:
        super().__init__()
        self.itemFormatters[gms.RollType.DAMAGE] = RollFormatter_STS_DMG
        self.itemFormatters[gms.RollType.NORMAL] = RollFormatter_STS_Normal
        self.itemFormatters[gms.RollType.REFLEXES] = RollFormatter_STS_Reflexes
        self.itemFormatters[gms.RollType.SOAK] = RollFormatter_STS_Soak
        self.itemFormatters[gms.RollType.SUM] = RollFormatter_PlainValues  
        self.itemFormatters[gms.RollType.INITIATIVE] = RollFormatter_STS_Initiative  
    def getStatsFormatter(self, rolltype: int):
        return RollFormatter_STS_Stats

class RollOutputter_V20HB(RollOutputter_STS):
    def __init__(self) -> None:
        super().__init__()
        self.itemFormatters[gms.RollType.PROGRESS] = RollFormatter_STS_Progress
        self.itemFormatters[gms.RollType.NORMAL] = RollFormatter_V20HB_Normal

class RollOutPutter_V20VANILLA(RollOutputter_STS):
    pass

class RollArgumentParser:
    def __init__(self, validator: type[gms.RollSetupValidator], has_parameters = False) -> None:
        self.has_parameters = has_parameters
        self.detach_end = False
        self.validatorClass = validator
        self.character = None
        
        # these are used by the parsing methods to keep track of where we are in the argument list
        self.current_keyword = ''
        self.cursor = -1 
        self.arguments =  []
    def _parse_internal(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup):
        raise NotImplementedError()
    def _save_setup(self, currentSetup: gms.RollSetup):
        if (not gms.RollArg.CHARACTER in currentSetup.rollArguments) and (not self.character is None):
            currentSetup.rollArguments[gms.RollArg.CHARACTER] = self.character
    def parse(self, ctx: gb.GreedyContext, arguments: list[str], i: int, currentSetup: gms.RollSetup, keyword = True) -> int:        
        # set the cursor to the current position
        self.current_keyword = arguments[i]
        self.cursor = i+1 if keyword else i
        self.arguments = arguments

        temp_ctx = currentSetup.ctx # ctx cannot be pickled for deepcopy
        currentSetup.ctx = None
        referenceSetup = deepcopy(currentSetup)
        currentSetup.ctx = temp_ctx
        self._parse_internal(ctx, referenceSetup) # cursor will be updated by the parsing methods

        self._save_setup(currentSetup)
        ret = self.cursor

        # this is paranoia but hey
        self.cursor = -1 
        self.current_keyword = ''
        self.arguments =  []

        return ret
    def canDetachEnd(self, keywords: tuple[str, ...], arguments: list[str], i: int) -> bool:
        if not self.detach_end:
            return False
        
        target = arguments[i]
        for kw in keywords:
            if target.endswith(kw) and target != kw:
                return True
    def detachEnd(self, keywords: tuple[str, ...], arguments: list[str], i: int) -> bool:        
        target =  arguments[i]
        for kw in keywords:
            if target.endswith(kw):
                return arguments[:i] + [arguments[i][:-1], kw] + arguments[i+1:]
    def getValidatorClass(self):
        return self.validatorClass
    def mergeDice(self, pool: dict[int, int], pool_permanent: dict[int, int], currentSetup: gms.RollSetup, mergefunc = lambda x, y: x+y):
        if gms.RollArg.DICE in currentSetup.rollArguments:
            currentSetup.rollArguments[gms.RollArg.DICE] = utils.merge(currentSetup.rollArguments[gms.RollArg.DICE], pool, lambda  x, y: x+y)
            currentSetup.rollArguments[gms.RollArg.PERMANENT_DICE] = utils.merge(currentSetup.rollArguments[gms.RollArg.PERMANENT_DICE], pool_permanent, mergefunc)
        else:
            currentSetup.rollArguments[gms.RollArg.DICE] = pool
            currentSetup.rollArguments[gms.RollArg.PERMANENT_DICE] = pool_permanent
    def loadCharacter(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup):
        if self.character is None:
            self.character = refSetup.rollArguments[gms.RollArg.CHARACTER] if gms.RollArg.CHARACTER in refSetup.rollArguments else ctx.bot.dbm.getActiveChar(ctx)
    # parameter parsers
    def parseItem(self) -> str:
        if self.cursor < len(self.arguments):
            item = self.arguments[self.cursor]
            self.cursor += 1
            return item
        
        raise gb.GreedyCommandError("string_error_x_what", (self.current_keyword,))
        #raise gb.GreedyCommandError("string_error_invalid_number_parameters_X", (self.current_keyword,))
    def parseInteger(self, ctx: gb.GreedyContext, err_msg: str = None) -> int:
        item = self.parseItem()
        return self.validateInteger(item, ctx, err_msg)
    def validateInteger(self, item, ctx: gb.GreedyContext, err_msg: str = None):
        try:
            return int(item)
        except ValueError:
            if err_msg == None: 
                err_msg = ctx.bot.getStringForUser(ctx, "string_errorpiece_integer")
            raise GreedyParseValidationError("string_error_x_isnot_y", (item, err_msg))
    def parseBoundedInteger(self, ctx: gb.GreedyContext, min_val: int = -inf, max_val: int = inf, err_msg : str = None) -> int:
        item = self.parseItem()
        return self.validateBoundedInteger(item, ctx, min_val, max_val, err_msg)
    def validateBoundedInteger(self, item, ctx: gb.GreedyContext, min_val: int = -inf, max_val: int = inf, err_msg: str = None) -> int:
        val = self.validateInteger(item, ctx)
        if val < min_val or val > max_val:
            if err_msg == None:
                err_msg = ctx.bot.getStringForUser(ctx, "string_errorpiece_number_in_range", min_val, max_val) 
            raise GreedyParseValidationError("string_error_x_isnot_y", (val, err_msg))
        return val

class RollArgumentParser_KeywordActivateOnly(RollArgumentParser):
    def __init__(self, validator: gms.RollSetupValidator, rollArgKey: int, rollTypeVal: int = None) -> None:
        super().__init__(validator)
        self.rollArgKey = rollArgKey
        self.rollTypeVal = rollTypeVal
    def _parse_internal(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup):
        pass
    def _save_setup(self, currentSetup: gms.RollSetup):
        super()._save_setup(currentSetup)
        if self.rollArgKey != gms.RollArg.ROLLTYPE:
            currentSetup.rollArguments[self.rollArgKey] = True
        if not self.rollTypeVal is None:
            currentSetup.rollArguments[gms.RollArg.ROLLTYPE] = self.rollTypeVal

class RollArgumentParser_STS_Initiative(RollArgumentParser_KeywordActivateOnly):
    def __init__(self) -> None:
        super().__init__(gms.RollSetupValidator, gms.RollArg.ROLLTYPE, rollTypeVal=gms.RollType.INITIATIVE)
    def _save_setup(self, currentSetup: gms.RollSetup):
        super()._save_setup(currentSetup)
        pool = {10:1}
        self.mergeDice(pool, pool, currentSetup)

class RollArgumentParser_STS_Reflexes(RollArgumentParser_KeywordActivateOnly):
    def __init__(self) -> None:
        super().__init__(gms.RollSetupValidator, gms.RollArg.ROLLTYPE, rollTypeVal=gms.RollType.REFLEXES)
        self.volonta = None
    def _parse_internal(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup):
        super()._parse_internal(ctx, refSetup)
        lid = ctx.getLID()
        self.loadCharacter(ctx, refSetup)
        self.volonta = ctx.bot.dbm.getTrait_LangSafe(self.character['id'], "volontà", lid)  
    def _save_setup(self, currentSetup: gms.RollSetup):
        super()._save_setup(currentSetup)
        pool = {10: self.volonta['cur_value']}
        pool_permanent = {10: self.volonta['max_value']}
        self.mergeDice(pool, pool_permanent, currentSetup)

class RollArgumentParser_V20HB_Reflexes(RollArgumentParser_STS_Reflexes):
    def __init__(self) -> None:
        super().__init__()
        self.prontezza = None
    def _parse_internal(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup):
        super()._parse_internal(ctx, refSetup)
        lid = ctx.getLID()
        self.prontezza = ctx.bot.dbm.getTrait_LangSafe(self.character['id'], "prontezza", lid) 
    def _save_setup(self, currentSetup: gms.RollSetup):
        super()._save_setup(currentSetup)
        reflex_diff = 10 - (self.prontezza['cur_value'] if gms.RollArg.PERMANENT in currentSetup.rollArguments else self.prontezza['max_value'])
        currentSetup.rollArguments[gms.RollArg.DIFF] = currentSetup.rollArguments[gms.RollArg.DIFF] if gms.RollArg.DIFF in currentSetup.rollArguments else reflex_diff

class RollArgumentParser_STS_Soak(RollArgumentParser_KeywordActivateOnly):
    def __init__(self) -> None:
        super().__init__(gms.RollSetupValidator, gms.RollArg.ROLLTYPE, rollTypeVal=gms.RollType.SOAK)
        self.costituzione = None
        self.robustezza = None
    def _parse_internal(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup):
        super()._parse_internal(ctx, refSetup)
        lid = ctx.getLID()
        self.loadCharacter(ctx, refSetup)
        self.costituzione = ctx.bot.dbm.getTrait_LangSafe(self.character['id'], "costituzione", lid) 
        try:
            self.robustezza = ctx.bot.dbm.getTrait_LangSafe(self.character['id'], "robustezza", lid)  
        except ghostDB.DBException:
            pass
    def _save_setup(self, currentSetup: gms.RollSetup):
        super()._save_setup(currentSetup)
        pool = {10: self.costituzione['cur_value'] + (0 if self.robustezza is None else self.robustezza['cur_value'])}
        pool_permanent = {10: self.costituzione['max_value'] + (0 if self.robustezza is None else self.robustezza['max_value'])}
        self.mergeDice(pool, pool_permanent, currentSetup)
        currentSetup.rollArguments[gms.RollArg.DIFF] = currentSetup.rollArguments[gms.RollArg.DIFF] if gms.RollArg.DIFF in currentSetup.rollArguments else 6

class RollArgumentParser_DiceExpression(RollArgumentParser):
    def  __init__(self, validator: type[gms.RollSetupValidator], has_parameters = False, firstNegative = False, detachEnd = False) -> None:
        super().__init__(validator, has_parameters)
        self.detach_end = detachEnd
        self.character = None
        self.dice = None
        self.dice_base = None
        self.traits_seen = None
        self.firstNegative = firstNegative
    def getTraitDefaultFaces(self) -> int:
        raise GreedyParseValidationError('string_error_default_die_face_unavailable')
    def transformTrait(self, traitvalue: int) -> int:
        return int(traitvalue)
    def _parse_internal(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup):
        expr = self.parseItem()
        self.dice, self.dice_base, self.traits_seen = self.decodeDiceExpression_Mixed(ctx, refSetup, expr, self.firstNegative)
    def _save_setup(self, currentSetup: gms.RollSetup):
        super()._save_setup(currentSetup)
        self.mergeDice(self.dice, self.dice_base, currentSetup)
        currentSetup.traits.update(self.traits_seen)
        self.character = None
    def decodeTrait(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup, traitdata) -> tuple[dict[int, int], dict[int, int]]:
        raise GreedyParseValidationError('I tratti non sono supportati dal roller generico')
    def decodeDiceExpression_Mixed(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup, what: str, firstNegative: bool = False):
        if gms.RollArg.CHARACTER in refSetup.rollArguments:
            self.character = refSetup.rollArguments[gms.RollArg.CHARACTER]

        self.dice = {} # faces -> dice  (0 means fixed bonus)
        self.dice_base = {}  # faces -> dice. if traits are  present in the expression, this one will contain base values for traits instead of buffed/debuffed traits
        self.traits_seen = set()

        split_add_list = what.split(ADD_CMD) # split on "+", so each of the results STARTS with something to add
        for i in range(0, len(split_add_list)):
            split_add = split_add_list[i]
            split_sub_list = split_add.split(SUB_CMD) # split on "-", so the first element will be an addition (unless firstNegative is true and i == 0), and everything else is a subtraction

            for j in range(0, len(split_sub_list)):
                term = split_sub_list[j]

                merge = {}
                merge_base = {}
                try: # either a xdy expr
                    n_term, faces_term = self.decodeDiceExpression_Dice(term, ctx) 
                    merge = {faces_term: n_term}
                    merge_base = {faces_term: n_term} 
                except GreedyParseValidationError as e: # or a trait
                    try:
                        lid = ctx.getLID()
                        self.loadCharacter(ctx, refSetup)
                        traitdata = ctx.bot.dbm.getTrait_LangSafe(self.character['id'], term, lid)
                        merge, merge_base = self.decodeTrait(ctx, refSetup, traitdata)
                        self.traits_seen.add(term)
                    except ghostDB.DBException as edb:
                        try:
                            n_term = self.validateInteger(term, ctx)
                            merge = {0: n_term}
                            merge_base = {0: n_term} 
                        except GreedyParseValidationError as ve:
                            raise lng.LangSupportErrorGroup("MultiError", [GreedyParseValidationError("string_error_notsure_whatroll"), e, edb, ve])

                if j > 0 or (i == 0 and firstNegative):
                    merge = {k: -v for k, v in merge.items()}
                    merge_base = {k: -v for k, v in merge_base.items()}

                self.dice = utils.merge(self.dice, merge, lambda x, y: x+y)
                self.dice_base = utils.merge(self.dice_base, merge_base, lambda x, y: x+y)

        # is it good that if the espression is just flat numbers we can parse it?
        # for example ".roll 3d10 7" will parse the same as ".roll 3d10 +7"

        return 
    def decodeDiceExpression_Dice(self, what: str, ctx: gb.GreedyContext) -> tuple[int, int]:
        split = what.split("d")
        if len(split) > 2:
            raise GreedyParseValidationError('string_error_toomany_d')
        if len(split) == 1:
            raise GreedyParseValidationError('string_error_not_XdY', (split[0],))
        if split[0] == "":
            split[0] = "1"
        if not split[0].isdigit():
            raise GreedyParseValidationError('string_error_not_positive_integer', (split[0],))
        if split[1] == "":
            split[1] = "10"
        if not split[1].isdigit():
            raise GreedyParseValidationError('string_error_not_positive_integer', (split[1],))
        n = int(split[0])
        faces = int(split[1])
        if n == 0:
            raise GreedyParseValidationError('string_error_not_gt0', (n,))
        if faces == 0:
            raise  GreedyParseValidationError('string_error_not_gt0', (faces,))
        if n > int(ctx.getAppConfig()['BotOptions']['max_dice']):
            raise GreedyParseValidationError('string_error_toomany_dice', (n,))
        if faces > int(ctx.getAppConfig()['BotOptions']['max_faces']):
            raise GreedyParseValidationError('string_error_toomany_faces', (faces,))

        return n, faces

class RollArgumentParser_STS_DiceExpression(RollArgumentParser_DiceExpression):
    def getTraitDefaultFaces(self):
        return 10
    def decodeTrait(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup, traitdata) -> tuple[dict[int, int], dict[int, int]]:
        n_term = self.transformTrait(traitdata['cur_value'])
        n_term_perm = self.transformTrait(traitdata['max_value'])
        faces_term = self.getTraitDefaultFaces()
        return {faces_term: n_term}, {faces_term: n_term_perm}

class RollArgumentParser_DND5E_DiceExpression(RollArgumentParser_DiceExpression):
    def getTraitDefaultFaces(self):
        return 20
    def decodeTrait(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup, traitdata) -> tuple[dict[int, int], dict[int, int]]:
        if len(self.traits_seen) or len(refSetup.traits):
            raise GreedyParseValidationError("string_error_only_one_trait_allowed")

        raise GreedyParseValidationError("work in progress!")
        # we have a bunch of cases:
        #   proficiency just does 1d20 plus proficiency (or adds it to a clean roll)
        #   an ability should roll the base modifier
        #   a skill should do ability_mod + proficiency_bonus*skill_proficiency (saving throws will be 'skill' traits)
        # i need a way to detect if a trait is an ability or a skill -> linked trait status might do the trick

        proficiency_bonus = ctx.bot.dbm.getTrait_LangSafe(self.character['id'], "competenza", ctx.getLID())  
        return super().decodeTrait(ctx, refSetup, traitdata)

class RollArgumentParser_SimpleArgumentList(RollArgumentParser):
    def __init__(self, validator: type[gms.RollSetupValidator], rollArgVar: int) -> None:
        super().__init__(validator, True)
        self.rollArgVal: int = rollArgVar
        self.parametersList: list[Any] = []
    def allowMultiple(self, refSetup: gms.RollSetup) -> bool:
        return gms.RollArg.ROLLTYPE in refSetup.rollArguments and refSetup.rollArguments[gms.RollArg.ROLLTYPE] != gms.RollType.NORMAL
    def _parse_internal(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup):
        if self.rollArgVal in refSetup.rollArguments and not self.allowMultiple(refSetup):
            raise GreedyParseValidationError('string_error_multiple_X', (self.current_keyword,))
    def aggregateParameters(self) -> Any:
        return self.parametersList
    def _save_setup(self, currentSetup: gms.RollSetup):
        super()._save_setup(currentSetup)
        currentSetup.rollArguments[self.rollArgVal] = self.aggregateParameters()

class RollArgumentParser_SingleParameter(RollArgumentParser_SimpleArgumentList):
    def __init__(self, validator: type[gms.RollSetupValidator], rollArgVar: int) -> None:
        super().__init__(validator, rollArgVar)
    def  _parse_internal(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup):
        super()._parse_internal(ctx, refSetup)
        self.parametersList.append(self.parseSingleParameter(ctx, refSetup))
    def aggregateParameters(self) -> Any:
        return self.parametersList[0]
    def parseSingleParameter(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup) -> Any:
        raise NotImplementedError()

class RollArgumentParser_STS_DIFF(RollArgumentParser_SingleParameter):
    def __init__(self) -> None:
        super().__init__(gms.RollSetupValidator_STS_DIFF, gms.RollArg.DIFF)
    def parseDifficulty(self, ctx: gb.GreedyContext):
        return self.parseBoundedInteger(ctx, 2, 10, ctx.bot.getStringForUser(ctx, "string_errorpiece_valid_diff"))
    def parseSingleParameter(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup):
        return self.parseDifficulty(ctx)

class RollArgumentParser_STS_MULTI(RollArgumentParser_SingleParameter):
    def __init__(self, validator: type[gms.RollSetupValidator] = gms.RollSetupValidator_STS_MULTI) -> None:
        super().__init__(validator, gms.RollArg.MULTI)
    def parseSingleParameter(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup) -> Any:
        return self.parseBoundedInteger(ctx, 2)

class RollArgumentParser_STS_MINSUCC(RollArgumentParser_SingleParameter):
    def __init__(self) -> None:
        super().__init__(gms.RollSetupValidator, gms.RollArg.MINSUCC)
    def parseSingleParameter(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup) -> Any:
        return self.parseBoundedInteger(ctx, 1)

class RollArgumentParser_V20HB_SPLIT(RollArgumentParser):
    def __init__(self, validator = gms.RollSetupValidator_V20HB_SPLIT) -> None:
        super().__init__(validator, True)
        self.split = {}
    def _parse_internal(self, ctx: gb.GreedyContext, refSetup: gms.RollSetup):
        index = None
        if gms.RollArg.MULTI in refSetup.rollArguments:
            index = self.parseBoundedInteger(ctx, 1)-1
        else:
            index = 0
        d1 = self.parseBoundedInteger(ctx, 2, 10)
        d2 = self.parseBoundedInteger(ctx, 2, 10)
        
        if gms.RollArg.SPLIT in refSetup.rollArguments:
            if index in refSetup.rollArguments[gms.RollArg.SPLIT].keys(): # cerco se ho giò splittato questo tiro
                raise gb.GreedyCommandError("string_error_already_splitting_X", (index+1,) )

        self.split[index] = (d1, d2)
    def _save_setup(self, currentSetup: gms.RollSetup):
        super()._save_setup(currentSetup)
        if not gms.RollArg.SPLIT in currentSetup.rollArguments:
            currentSetup.rollArguments[gms.RollArg.SPLIT] = {}

        currentSetup.rollArguments[gms.RollArg.SPLIT] = currentSetup.rollArguments[gms.RollArg.SPLIT] | self.split
        self.split = {}

class RollParser:
    def __init__(self):
        self.rollRollArgumentParsers: dict[tuple[str, ...], RollArgumentParser] = {} #list[RollArgumentParser] = []
        self.nullParser: RollArgumentParser = None
    def generateSetup(self, ctx: sec.SecurityContext) -> gms.RollSetup:
        setup = self.getSetup(ctx)
        for parser in self.rollRollArgumentParsers.values():
            setup.validatorClasses.append(parser.getValidatorClass())
        return setup
    def getSetup(self, ctx: sec.SecurityContext) -> gms.RollSetup:
        raise NotImplementedError()
    def getOutputter(self) -> RollOutputter:
        return RollOutputter()
    def splitAndParse(self, ctx: gb.GreedyContext, setup: gms.RollSetup, args: list[str], i: int, init_errors: list[Exception]) -> int:
        parse_errors = init_errors
        did_split = False
        for keywords, parser in self.rollRollArgumentParsers.items():
            if parser.has_parameters and len(keywords):
                idx = 0
                while not did_split and idx < len(keywords):
                    cmd = keywords[idx]
                    if args[i].startswith(cmd) and len(cmd) < len(args[i]):
                        mod_args = args[:i] + [cmd, args[i][len(cmd):]] + args[i+1:] # modify the  arguments list
                        try:
                            i = parser.parse(ctx, mod_args, i, setup) # attempt parsing again with the split
                            args = mod_args
                            did_split = True
                        except GreedyParseValidationError as e2:
                            parse_errors.append(e2)
                    idx += 1
                
                if did_split: # this is technically not needed but makes things more readable
                    break

        if not did_split: # F
            raise lng.LangSupportErrorGroup("MultiError", parse_errors)
        
        return i, args
    def parseRoll(self, ctx: gb.GreedyContext, args: list[str]) -> gms.RollSetup:
        setup = self.generateSetup(ctx)

        # detaching + or - from the end of an expression needs to be done immediately
        i = 0
        while i < len(args):
            for keywords, parser in self.rollRollArgumentParsers.items():
                if parser.canDetachEnd(keywords, args, i):
                    args = parser.detachEnd(keywords, args, i)
            i += 1

        # do the actual parsing
    
        i = 0
        while i < len(args):
            parsed =  False
            parser = None

            try:
                for keywords, parser in self.rollRollArgumentParsers.items():
                    if args[i] in keywords:
                        i = parser.parse(ctx, args, i, setup)
                        parsed = True
                        break
                if not parsed and not self.nullParser is None:
                    parser = self.nullParser
                    i = parser.parse(ctx, args, i, setup, False)
                    parsed = True
            except (GreedyParseValidationError, lng.LangSupportErrorGroup)as e: # if at any point a parse fails, we try to see if the user has not separated an argument from its parameter (diff6, multi3...)
                parse_errors = [gb.GreedyCommandError("string_arg_X_in_Y_notclear", (args[i], utils.prettyHighlightError(args, parser.cursor-1))), e]
                i, args = self.splitAndParse(ctx, setup, args, i, parse_errors)
                parsed = True

            if not parsed:
                parse_errors = [gb.GreedyCommandError("string_arg_X_in_Y_notclear", (args[i], utils.prettyHighlightError(args, i)))]
                i, args = self.splitAndParse(ctx, setup, args, i, parse_errors) 

        return setup

class RollParser_General(RollParser):
    def  __init__(self):
        super().__init__()
        self.rollRollArgumentParsers[SOMMA_CMD] = RollArgumentParser_KeywordActivateOnly(gms.RollSetupValidator, gms.RollArg.ROLLTYPE, rollTypeVal = gms.RollType.SUM)
        self.rollRollArgumentParsers[(ADD_CMD,)] = RollArgumentParser_DiceExpression(gms.RollSetupValidator_DICE, has_parameters=True, detachEnd=True)
        self.rollRollArgumentParsers[(SUB_CMD,)] = RollArgumentParser_DiceExpression(gms.RollSetupValidator_DICE, has_parameters=True, firstNegative = True, detachEnd=True)
        self.nullParser = RollArgumentParser_DiceExpression(gms.RollSetupValidator_DICE)
    def getSetup(self, ctx: sec.SecurityContext) -> gms.RollSetup:
        return gms.RollSetup_General(ctx)

class RollParser_STS(RollParser_General):
    def __init__(self):
        super().__init__()
        self.rollRollArgumentParsers[DIFF_CMD] = RollArgumentParser_STS_DIFF()
        self.rollRollArgumentParsers[MULTI_CMD] = RollArgumentParser_STS_MULTI()
        self.rollRollArgumentParsers[DANNI_CMD] = RollArgumentParser_KeywordActivateOnly(gms.RollSetupValidator, gms.RollArg.ROLLTYPE, rollTypeVal = gms.RollType.DAMAGE)
        self.rollRollArgumentParsers[PROGRESSI_CMD] = RollArgumentParser_KeywordActivateOnly(gms.RollSetupValidator, gms.RollArg.ROLLTYPE, rollTypeVal = gms.RollType.PROGRESS)
        self.rollRollArgumentParsers[(ADD_CMD,)] = RollArgumentParser_STS_DiceExpression(gms.RollSetupValidator_STS_DICE, has_parameters=True, detachEnd=True)
        self.rollRollArgumentParsers[(SUB_CMD,)] = RollArgumentParser_STS_DiceExpression(gms.RollSetupValidator_STS_DICE, has_parameters=True, firstNegative = True, detachEnd=True)
        self.rollRollArgumentParsers[PENALITA_CMD] = RollArgumentParser_KeywordActivateOnly(gms.RollSetupValidator, gms.RollArg.PENALTY)
        self.rollRollArgumentParsers[PERMANENTE_CMD] = RollArgumentParser_KeywordActivateOnly(gms.RollSetupValidator, gms.RollArg.PERMANENT)
        self.rollRollArgumentParsers[STATISTICS_CMD] = RollArgumentParser_KeywordActivateOnly(gms.RollSetupValidator, gms.RollArg.STATS)
        self.rollRollArgumentParsers[MINSUCC_CMD] = RollArgumentParser_STS_MINSUCC()
        self.rollRollArgumentParsers[INIZIATIVA_CMD] = RollArgumentParser_STS_Initiative()
        self.rollRollArgumentParsers[RIFLESSI_CMD] = RollArgumentParser_STS_Reflexes()
        self.rollRollArgumentParsers[SOAK_CMD] = RollArgumentParser_STS_Soak()
        self.nullParser = RollArgumentParser_STS_DiceExpression(gms.RollSetupValidator_STS_DICE)
    def getSetup(self, ctx: gb.GreedyContext):
        return gms.RollSetup_STS(ctx)
    def getOutputter(self) -> RollOutputter_STS:
        return RollOutputter_STS()

class RollParser_V20HB(RollParser_STS):
    def __init__(self):
        super().__init__()
        self.rollRollArgumentParsers[SPLIT_CMD] = RollArgumentParser_V20HB_SPLIT()
        self.rollRollArgumentParsers[MULTI_CMD] = RollArgumentParser_STS_MULTI(gms.RollSetupValidator_V20HB_MULTI)
        self.rollRollArgumentParsers[RIFLESSI_CMD] = RollArgumentParser_V20HB_Reflexes()
    def getSetup(self, ctx: gb.GreedyContext):
        return gms.RollSetup_V20HB(ctx)
    def getOutputter(self) -> RollOutputter_V20HB:
        return RollOutputter_V20HB()

class RollParser_V20VANILLA(RollParser_STS):
    def __init__(self):
        super().__init__()
    def getSetup(self, ctx: gb.GreedyContext):
        return gms.RollSetup_V20VANILLA(ctx)
    def getOutputter(self) -> RollOutPutter_V20VANILLA:
        return RollOutPutter_V20VANILLA()

class RollParser_DND5E(RollParser_General):
    def __init__(self):
        super().__init__()
    #def getSetup(self, ctx: gb.GreedyContext):
    #    return gms.RollSetup_STS(ctx)
    #def getOutputter(self) -> RollOutputter_STS:
    #    return RollOutputter_STS()

RollSystemMappings: dict[int, type[RollParser]] = {
    gms.GameSystems.GENERAL: RollParser_General,
    gms.GameSystems.STORYTELLER_SYSTEM: RollParser_STS,
    gms.GameSystems.V20_VTM_HOMEBREW_00: RollParser_V20HB,
    gms.GameSystems.V20_VTM_VANILLA: RollParser_V20VANILLA
    #gms.GameSystems.DND_5E: RollParser_DND5E,
}

def getParser(gamesystem: int):
    """ Gets a roll parser from a GameSystem enum """
    return RollSystemMappings[gamesystem]
