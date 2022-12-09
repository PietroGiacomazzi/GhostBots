from hashlib import new
import random
from typing import Any
import lang as lng

from .utils import *
from .security import *
from .vtm_res import *


RollType = enum("NORMAL", "SUM", "DAMAGE", "PROGRESS", "INITIATIVE", "REFLEXES", "SOAK")
RollArg = enum("DIFF", "MULTI", "SPLIT", "ROLLTYPE", "PENALTY", "DICE", "PERMANENT_DICE", "PERMANENT", "STATS", "CHARACTER", "MINSUCC") # argomenti del tiro

TrackerType = enum("NORMAL", "CAPPED", "HEALTH", "UNCAPPED")

DMG_BASHING = 'c'
DMG_LETHAL = 'l'
DMG_AGGRAVATED = 'a'
DAMAGE_TYPES = [DMG_AGGRAVATED, DMG_LETHAL, DMG_BASHING] # it is important that the order is a, l, c

BASHING_idx = DAMAGE_TYPES.index(DMG_BASHING)
LETHAL_idx = DAMAGE_TYPES.index(DMG_LETHAL)

GameSystems = enum(*GAMESYSTEMS_LIST)

OPCODES_ADD = ('+',)
OPCODES_SUB = ('-',)
OPCODES_EQ = ('=',)
OPCODES_RESET = ('r', 'reset')
DETACH_SPECIAL = OPCODES_ADD+OPCODES_SUB+OPCODES_EQ

OPCODES_ALL = OPCODES_ADD + OPCODES_EQ + OPCODES_RESET +  OPCODES_SUB

ACTIONS_DAMAGE = ('danni', 'danno', 'damage')

def detach_args(args: list[str]) -> list[str]:
    """ Detach stuff like ["exp+1"] to ["exp", "+", "1"]" or ["exp-", "1"] to ["exp", "-", "1"] in args.

    This is a fairly limited function as it is just a nice thing that we do for users."""
    new_args = list(args)
    i = 0
    while i < len(new_args):
        for op in DETACH_SPECIAL:
            arg = new_args[i]
            ix = arg.find(op)
            if ix >= 0:
                new_args = new_args[:i] + list(filter(lambda x: x != '', [arg[:ix], op, arg[ix+1:]])) + new_args[i+1:]
        i += 1
    return new_args

def getGamesystem(gamesystem: str) -> int:
    """ Gets a game system enum from its identifier string """
    if gamesystem in GAMESYSTEMS_LIST:
        return getattr(GameSystems, gamesystem)
    raise lng.LangException("string_error_invalid_rollsystem", gamesystem)

class GreedyRollValidationError(lng.LangSupportException):
    pass

class GreedyRollExecutionError(lng.LangSupportException):
    pass

class GreedyOperationError(lng.LangSupportException):
    pass

class GreedyTraitOperationError(GreedyOperationError):
    pass

class RollItem:
    def __init__(self) -> None:
        self.tag:  str = None
        self.results: list[int] = None
        self.faces: int = None
        self.additional_data: Any = None

class RollItem_STS(RollItem):
    def  __init__(self) -> None:
        super().__init__()
        self.count_successes: int = None
        self.canceled: int = None
        self.difficulty: int = None
        self.minsucc: int = None
        self.extra_succ: int = None

class RollData:
    def __init__(self, rolltype: int, statistics = False) -> None:
        self.rolltype = rolltype
        self.statistics = statistics
        self.data: list[RollItem] = []

class RollSetup:
    def __init__(self, ctx: SecurityContext) -> None:
        self.rollArguments: dict[int, Any] = {}
        self.validatorClasses: list[type[RollSetupValidator]] = []
        self.ctx = ctx
        self.actionHandlers: dict[int, type[RollAction]] = {}
        self.traits = set()
    def roll(self) -> RollData:
        action = self.rollArguments[RollArg.ROLLTYPE] if RollArg.ROLLTYPE in self.rollArguments else RollType.NORMAL  
        if action in self.actionHandlers:
            handlerClass= self.actionHandlers[action]
            handler = handlerClass(self)
            return handler.execute(action)
        raise GreedyRollExecutionError("string_error_roll_invalid_param_combination")
    def validate(self):
        for cls in self.validatorClasses:
            validator = cls()
            validator.validate(self)
    def shouldUseBasePool(self):
        return False
    def getPool(self) -> int:
        arg = RollArg.DICE
        if self.shouldUseBasePool():
            arg = RollArg.PERMANENT_DICE
        pool = 0
        if not arg in self.rollArguments:
            raise GreedyRollValidationError("string_error_no_dice_specified")
        pool = sum([v for k, v in self.rollArguments[arg].items() if k != 0])
        return pool

class RollSetup_General(RollSetup):
    def __init__(self, ctx: SecurityContext) -> None:
        super().__init__(ctx)
        self.actionHandlers[RollType.NORMAL] = RollAction_GeneralRoll
        self.actionHandlers[RollType.SUM] = RollAction_GeneralRoll

class RollSetup_STS(RollSetup_General):
    def __init__(self, ctx: SecurityContext) -> None:
        super().__init__(ctx)
        self.actionHandlers[RollType.DAMAGE] = RollAction_STS_Damage
        self.actionHandlers[RollType.INITIATIVE] = RollAction_STS_Initiative
        self.actionHandlers[RollType.REFLEXES] = RollAction_STS_RegularRoll
        self.actionHandlers[RollType.SOAK] = RollAction_STS_RegularRoll
    def shouldUseBasePool(self):
        return RollArg.PERMANENT in self.rollArguments
    def getPool(self) -> int:
        pool = super().getPool()
        if RollArg.PENALTY in self.rollArguments:
            character = self.rollArguments[RollArg.CHARACTER] if RollArg.CHARACTER in self.rollArguments else self.ctx.getDBManager().getActiveChar(self.ctx)
            health = self.ctx.getDBManager().getTrait_LangSafe(character['id'], 'salute', self.ctx.getLID())
            penalty, _ = parseHealth(health)
            pool += penalty[0]
        return pool
    def _rollPoolStatistics(self, ndice: int, diff: int, extra_succ: int = 0, canceling: bool = True, spec: bool = False, minsucc: int = 1) -> RollItem_STS:
        statistics_samples = int(self.ctx.getAppConfig()['BotOptions']['stat_samples'])
        total_successes = 0 # total successes, even when the roll is a fail
        pass_successes = 0 # total of successes only when the roll succeeds
        passes = 0 # number of successful rolls
        fails = 0 # number of failed rolls (no critfails)
        critfails = 0 # number of critfailed rolls
        for i in range(statistics_samples):
            successi, _, _ = roller(ndice, 10, diff, canceling, spec, extra_succ)
            if successi > 0:
                if successi >= minsucc:
                    passes += 1
                    pass_successes += successi
                else:
                    fails += 1
                total_successes += successi
            elif successi == 0 or successi == -2:
                fails += 1
            else:
                critfails += 1
        
        ri = RollItem_STS()
        ri.results = range(ndice)
        ri.faces = 10
        ri.difficulty = diff
        ri.minsucc = minsucc
        ri.extra_succ = extra_succ
        ri.additional_data = (statistics_samples, ndice, canceling, spec, passes, fails, critfails, total_successes, pass_successes)

        return ri
    def _rollPool(self, ndice: int, diff: int, extra_succ: int = 0, canceling: bool = True, spec: bool = False, minsucc: int = 1) -> RollItem_STS:
        ri = RollItem_STS()
        ri.faces = 10
        ri.difficulty = diff
        ri.minsucc = minsucc
        ri.extra_succ = extra_succ
        ri.count_successes, ri.results, ri.canceled = roller(ndice, 10, diff, canceling, spec, extra_succ)
        return ri
    def rollPool(self, ndice: int, diff: int, extra_succ: int = 0, canceling: bool = True, spec: bool = False, minsucc: int = 1) -> RollItem_STS:
        if RollArg.STATS in self.rollArguments:
            return self._rollPoolStatistics(ndice, diff, extra_succ, canceling, spec, minsucc)
        else:
            return self._rollPool(ndice, diff, extra_succ, canceling, spec, minsucc)
    def roll(self) -> RollData:
        if not RollArg.DIFF in self.rollArguments:
            self.rollArguments[RollArg.DIFF] = 6
        return super().roll()

class RollSetup_V20HB(RollSetup_STS):        
    def __init__(self, ctx: SecurityContext) -> None:
        super().__init__(ctx)
        self.actionHandlers[RollType.NORMAL] = RollAction_V20HB_RegularRoll
        self.actionHandlers[RollType.DAMAGE] = RollAction_V20HB_Damage
        self.actionHandlers[RollType.PROGRESS] = RollAction_V20HB_RegularRoll
        self.actionHandlers[RollType.REFLEXES] = RollAction_V20HB_RegularRoll
        self.actionHandlers[RollType.SOAK] = RollAction_V20HB_Damage
        
class RollSetup_V20VANILLA(RollSetup_STS):
    def __init__(self, ctx: SecurityContext) -> None:
        super().__init__(ctx)

class RollAction:
    def __init__(self, setup: RollSetup) -> None:
        self.setup = setup
    def initRollData(self, rolltype: int) -> RollData:
        return RollData(rolltype, RollArg.STATS in self.setup.rollArguments)
    def execute(self, rolltype: int) -> RollData:
        return self.initRollData(rolltype)

class RollAction_GeneralRoll(RollAction):
    def execute(self, rolltype: int) -> RollData:
        rdata = self.initRollData(rolltype)
        if RollArg.DICE in self.setup.rollArguments: 
            for faces, number in self.setup.rollArguments[RollArg.DICE].items():
                item = RollItem()
                item.faces = faces
                if faces:
                    item.tag = f'd{faces}'
                    item.results = list(map(lambda x: random.randint(1, faces), range(0, number))) 
                else:
                    item.tag = f'flat'
                    item.results = [number]
                rdata.data.append(item)
        return rdata

class RollAction_STS(RollAction):
    def __init__(self, setup: RollSetup_STS) -> None:
        super().__init__(setup)
        self.setup = setup # here just for type hinting suggestions

class RollAction_STS_Initiative(RollAction):
    def execute(self, rolltype: int) -> RollData:
        lid = self.setup.ctx.getLID()
        rd = self.initRollData(rolltype)

        add = self.setup.rollArguments[RollArg.DICE][0] if 0 in self.setup.rollArguments[RollArg.DICE] else 0
        raw_roll = random.randint(1, 10)
        bonuses_log = []
        bonus = add
        if add:
            bonuses_log.append(self.setup.ctx.getLanguageProvider().get(lid, "string_bonus_X", add))

        character = self.setup.rollArguments[RollArg.CHARACTER] if RollArg.CHARACTER in self.setup.rollArguments else self.setup.ctx.getDBManager().getActiveChar(self.setup.ctx)
        for traitid in ['prontezza', 'destrezza', 'velocità']: # TODO dehardcode?
            try:
                val = self.setup.ctx.getDBManager().getTrait_LangSafe(character['id'], traitid, lid)
                bonus += val["cur_value"]
                bonuses_log.append( f'{val["traitName"]}: {val["cur_value"]}' )
            except ghostDB.DBException:
                pass

        ri = RollItem_STS()
        ri.faces = 10
        ri.results = [raw_roll]
        ri.tag = self.setup.ctx.getLanguageProvider().get(lid, "string_initiative")
        ri.extra_succ = bonus
        ri.additional_data = bonuses_log

        rd.data.append(ri)
        return rd

class RollAction_STS_Damage(RollAction_STS):
    def shouldCancel(self):
        return True
    def execute(self, rolltype: int) -> RollData:
        lid = self.setup.ctx.getLID()
        diff = self.setup.rollArguments[RollArg.DIFF]
        ndice = self.setup.getPool()
        extra_successes = self.setup.rollArguments[RollArg.DICE][0] if 0 in self.setup.rollArguments[RollArg.DICE] else 0
        
        rd = self.initRollData(rolltype)

        roll_item = self.setup.rollPool(ndice, diff, extra_successes, canceling=self.shouldCancel())
        roll_item.tag = f'{self.setup.ctx.getLanguageProvider().get(lid, "string_roll")}'
        rd.data.append(roll_item)

        return rd

class RollAction_STS_RegularRoll(RollAction_STS):
    def execute(self, rolltype: int) -> RollData:
        lid = self.setup.ctx.getLID()
        diff = self.setup.rollArguments[RollArg.DIFF] #if RollArg.DIFF in self.rollArguments else 6
        ndice = self.setup.getPool()
        extra_successes = self.setup.rollArguments[RollArg.DICE][0] if 0 in self.setup.rollArguments[RollArg.DICE] else 0
        min_succ = self.setup.rollArguments[RollArg.MINSUCC] if RollArg.MINSUCC in self.setup.rollArguments else 1

        rd = self.initRollData(rolltype)

        if RollArg.MULTI in self.setup.rollArguments:
            multi = self.setup.rollArguments[RollArg.MULTI] 
            ndice_multi = ndice//multi
            ndice_rem = ndice % multi
            for i in range(multi):
                extra_die = 1 if i < ndice_rem else 0
                roll_item = self.setup.rollPool(ndice_multi+extra_die, diff, extra_successes, minsucc=min_succ)
                roll_item.tag = f'{self.setup.ctx.getLanguageProvider().get(lid, "string_action")} {i+1}'
                rd.data.append(roll_item)
        else: # 1 tiro solo 
            roll_item = self.setup.rollPool(ndice, diff, extra_successes, minsucc=min_succ)
            roll_item.tag = f'{self.setup.ctx.getLanguageProvider().get(lid, "string_roll")}'
            rd.data.append(roll_item)
        return rd

class RollAction_V20HB_Damage(RollAction_STS_Damage):
    def shouldCancel(self):
        return False

class RollAction_V20HB_RegularRoll(RollAction_STS):
    def execute(self, rolltype: int) -> RollData:
        lid = self.setup.ctx.getLID()
        diff = self.setup.rollArguments[RollArg.DIFF] #if RollArg.DIFF in self.rollArguments else 6
        ndice = self.setup.getPool()
        extra_successes = self.setup.rollArguments[RollArg.DICE][0] if 0 in self.setup.rollArguments[RollArg.DICE] else 0
        min_succ = self.setup.rollArguments[RollArg.MINSUCC] if RollArg.MINSUCC in self.setup.rollArguments else 1

        split = None
        if RollArg.SPLIT in self.setup.rollArguments:
            split = self.setup.rollArguments[RollArg.SPLIT]

        rd = self.initRollData(rolltype)
        
        if RollArg.MULTI in self.setup.rollArguments:
            multi = self.setup.rollArguments[RollArg.MULTI]                
            for i in range(multi):
                ndice_m = ndice-i-multi
                base_tag = f'{self.setup.ctx.getLanguageProvider().get(lid, "string_action")} {i+1}'
                if not split is None and i in split:
                    split_diffs = split[i]
                    pools = [(ndice_m-ndice_m//2), ndice_m//2]
                    for j in range(len(pools)):
                        roll_item = self.setup.rollPool(pools[j], split_diffs[j], extra_successes, minsucc=min_succ)
                        roll_item.tag = f'{base_tag}: {self.setup.ctx.getLanguageProvider().get(lid, "string_roll")} {j+1}'
                        rd.data.append(roll_item)
                else:
                    roll_item = self.setup.rollPool(ndice_m, diff, extra_successes, minsucc=min_succ)
                    roll_item.tag = base_tag
                    rd.data.append(roll_item)
        else: # 1 tiro solo 
            if not split is None:
                split_diffs = split[0]
                pools = [(ndice-ndice//2), ndice//2]
                for j in range(len(pools)):
                    roll_item = self.setup.rollPool(pools[j], split_diffs[j], extra_successes,  minsucc=min_succ)
                    roll_item.tag = f'{self.setup.ctx.getLanguageProvider().get(lid, "string_roll")} {j+1}'
                    rd.data.append(roll_item)
            else:
                roll_item = self.setup.rollPool(ndice, diff, extra_successes, minsucc=min_succ)
                roll_item.tag = f'{self.setup.ctx.getLanguageProvider().get(lid, "string_roll")}'
                rd.data.append(roll_item)
        return rd

class RollSetupValidator:
    def validate(self, setup: RollSetup):
        pass

class RollSetupValidator_DICE(RollSetupValidator):
    def validate(self, setup: RollSetup):
        super().validate(setup)
        pool = setup.getPool()

        max_dice = int(setup.ctx.getAppConfig()['BotOptions']['max_dice'])
        if pool > max_dice:
            raise GreedyRollValidationError("string_error_toomany_dice", (max_dice,))
        if pool <= 0:
            raise GreedyRollValidationError("string_error_toofew_dice", (pool,))

class RollSetupValidator_STS_DIFF(RollSetupValidator):
    def validate(self, setup: RollSetup):
        super().validate(setup)
        if RollArg.DIFF in setup.rollArguments:
            diff = setup.rollArguments[RollArg.DIFF]
            if diff < 2 or diff > 10:
                raise GreedyRollValidationError('string_error_x_isnot_y', (diff, setup.ctx.getLanguageProvider().get(setup.ctx.getLID(), 'string_errorpiece_valid_diff')))

class RollSetupValidator_STS_DICE(RollSetupValidator_DICE):
    def validate(self, setup: RollSetup_STS):
        super().validate(setup)
        if RollArg.DICE in setup.rollArguments:
            keys = setup.rollArguments[RollArg.DICE].keys()
            if (not 10 in keys) or len(keys) > 2 or sum(keys) != 10:
                raise GreedyRollValidationError("string_error_face_mixing")

class RollSetupValidator_STS_MULTI(RollSetupValidator):
    def getMaxMoves(self, setup: RollSetup_STS) -> int:
        return setup.getPool()
    def validate(self, setup: RollSetup_STS):
        if not RollArg.MULTI in setup.rollArguments:
            return

        multi = setup.rollArguments[RollArg.MULTI]
        pool = setup.getPool()
        max_moves = self.getMaxMoves(setup)
        if max_moves == 1:
            raise GreedyRollValidationError("string_error_not_enough_dice_multi")
        elif multi > max_moves:
            raise GreedyRollValidationError("string_error_not_enough_dice_multi_MAX_REQUESTED", (max_moves, pool))

class RollSetupValidator_V20HB_MULTI(RollSetupValidator_STS_MULTI):
    def getMaxMoves(self, setup: RollSetup_STS) -> int:
        return int( ((setup.getPool()+1)/2) -0.1) # (pool+1)/2 è il numero di mosse in cui si rompe, non il massimo. togliendo 0.1 e arrotondando per difetto copro sia il caso intero che il caso con .5

class RollSetupValidator_V20HB_SPLIT(RollSetupValidator):
    def validate(self, setup: RollSetup_STS):
        if not RollArg.SPLIT in setup.rollArguments:
            return
        
        splits: dict[int, tuple[int, int]] = setup.rollArguments[RollArg.SPLIT]
        multi = setup.rollArguments[RollArg.MULTI] if RollArg.MULTI in setup.rollArguments else 0
        pool = setup.getPool()
        for roll_index in splits.keys():
            if multi:
                if roll_index >= multi:
                    raise GreedyRollValidationError("string_error_split_X_higherthan_multi_Y",  (roll_index+1, multi) )
            if pool-multi-roll_index < 2:
                raise GreedyRollValidationError("string_error_split_cannot_split_small_pool_X",  (roll_index+1,) )

# PC interactions

def validateDamageExprSTS(param: str, ctx: SecurityContext) -> tuple[int, str]:
    dmgtype = param[-1].lower()
    if not dmgtype in DAMAGE_TYPES:
        raise GreedyTraitOperationError("string_error_invalid_damage_type", (dmgtype,))
    dmgamount_raw = param[:-1]
    dmgamount = 1 if dmgamount_raw == '' else InputValidator(ctx).validateInteger(dmgamount_raw)
    return dmgamount, dmgtype

def validateHealthSTS(health_string: str, max_length: int, immediately_convert_bashing_to_lethal: bool = False) -> str:
    """ parses and validates a health string, reordering damage types and adjusting to allowed length 
    \nimmediately_convert_bashing_to_lethal determines whether bashing damage should be collapsed into lethal on validation
    """
    counts = list(map(lambda x: health_string.count(x), DAMAGE_TYPES))
    if sum(counts) != len(health_string):
        raise GreedyTraitOperationError("string_error_invalid_health_expr", (health_string,))
    if counts[BASHING_idx] > 1 and immediately_convert_bashing_to_lethal:
        counts[LETHAL_idx] = counts[LETHAL_idx] + counts[BASHING_idx]//2
        counts[BASHING_idx] = counts[BASHING_idx] % 2
    new_health = "".join(list(map(lambda x: x[0]*x[1], zip(DAMAGE_TYPES, counts)))) # siamo generosi e riordiniamo l'input
    if sum(counts) > max_length: #  truncate if too long
        new_health = new_health[:max_length]
    return new_health   

class PCActionResult:
    pass

class PCActionResultTrait(PCActionResult):
    def __init__(self, trait) -> None:
        super().__init__()
        self.trait = trait

class PCActionResultText(PCActionResult):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

class PCAction:
    def __init__(self, handler: 'PCActionHandler', ctx: SecurityContext, character) -> None:
        self.character = character
        self.ctx = ctx
        self.expectedParameterNumbers: tuple[int] = () # remember, for  TraitActions this means parameters beyond the OPERATION, while for actions it is anything beyond the action code
        self.handler = handler
    def doHandle(self, *args):
        return [PCActionResultText(self.ctx.getLanguageProvider().get(self.ctx.getLID(), "string_error_notimplemented"))]
    def handle(self, *args: tuple[str]) -> list[PCActionResult]:
        self.checkParameterNumber(args)
        return self.doHandle(*args)
    def checkParameterNumber(self, args: list[tuple]):
        if len(self.expectedParameterNumbers) > 0 and not (len(args) in self.expectedParameterNumbers):
            raise GreedyTraitOperationError("string_invalid_number_of_parameters")
    def db_setCurvalue(self, new_val: int, trait):
        u = self.ctx.getDBManager().db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=self.character['id']), cur_value = new_val)
        self.ctx.getDBManager().log(self.ctx.getUserId(), self.character['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_val, trait['cur_value'], self.ctx.getMessageContents())
        if u == 1 or (u == 0 and trait['cur_value'] == new_val):
            return self.ctx.getDBManager().getTrait_LangSafe(self.character['id'], trait['id'], self.ctx.getLID())
            
        raise GreedyTraitOperationError('string_error_database_unexpected_update_rowcount', (u,))
    def db_setTextValue(self, new_value: str, trait):
        u = self.ctx.getDBManager().db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=self.character['id']), text_value = new_value)
        self.ctx.getDBManager().log(self.ctx.getUserId(), self.character['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_value, trait['text_value'], self.ctx.getMessageContents())
        if u == 1 or (u == 0 and trait['text_value'] == new_value):
            return self.ctx.getDBManager().getTrait_LangSafe(self.character['id'], trait['id'], self.ctx.getLID())         
        raise GreedyTraitOperationError('string_error_database_unexpected_update_rowcount', (u,))

class PCTraitAction(PCAction):
    def  __init__(self, handler: 'PCActionHandler', ctx: SecurityContext, character, trait) -> None:
        super().__init__(handler, ctx, character)
        self.trait = trait
    def doHandle(self, *args: list[str]) -> list[PCActionResult]:
        ttype = int(self.trait['trackertype'])
        if ttype == TrackerType.NORMAL:
            if self.trait['pimp_max'] == 0:
                raise GreedyTraitOperationError("string_error_cannot_modify_trait_curvalue", (self.trait['traitName'],))
            return self._handleOperation_NORMAL(*args)
        elif ttype == TrackerType.CAPPED:
            return self._handleOperation_CAPPED(*args)
        elif ttype == TrackerType.HEALTH:
            return self._handleOperation_HEALTH(*args)
        elif ttype == TrackerType.UNCAPPED:
            return self._handleOperation_UNCAPPED(*args)
        else:
            raise GreedyTraitOperationError("string_error_unknown_trackertype", (ttype,))
    def _handleOperation_Base(self, *args: list[str]) -> list[PCActionResult]:
        raise NotImplementedError()
    def _handleOperation_NORMAL(self, *args: list[str]) -> list[PCActionResult]:
        return self._handleOperation_Base(*args)
    def _handleOperation_CAPPED(self, *args: list[str]) -> list[PCActionResult]:
        return self._handleOperation_Base(*args)
    def _handleOperation_HEALTH(self, *args: list[str]) -> list[PCActionResult]:
        return self._handleOperation_Base(*args)
    def _handleOperation_UNCAPPED(self, *args: list[str]) -> list[PCActionResult]:
        return self._handleOperation_Base(*args)
    

class PCTraitAction_ViewTrait(PCTraitAction):
    def doHandle(self, *args) -> list[PCActionResult]:
        return [PCActionResultTrait(self.trait)]

class PCTraitAction_STS(PCTraitAction):
    def doImmediatelyConvertBashingToLethal(self) -> bool:
        return False 

class PCTraitAction_STS_ModifyCurValue(PCTraitAction_STS):
    def __init__(self, handler: 'PCActionHandler', ctx: SecurityContext, character, trait) -> None:
        super().__init__(handler, ctx, character, trait)
        self.expectedParameterNumbers = (0, 1)
    def newValue(self, args: list[str]):
        raise NotImplementedError()
    def checkBounds(self, args: list[str]):
        new_val = self.newValue(args)
        max_val = max(self.trait['max_value'], self.trait['pimp_max']) 
        if new_val > max_val:
            raise GreedyTraitOperationError("string_error_exceeded_trait_maxvalue", (new_val, self.trait['traitName'].lower(), max_val))
        if new_val < 0:
            raise GreedyTraitOperationError("string_error_not_enough_X", (self.trait['traitName'].lower(),))
    def _handleOperation_CAPPED(self, *args: list[str]) -> list[PCActionResult]:
        self.checkBounds(args)
        return super()._handleOperation_CAPPED(*args)
    def _handleOperation_NORMAL(self, *args: list[str]) -> list[PCActionResult]:
        self.checkBounds(args)
        return super()._handleOperation_NORMAL(*args)
    def _handleOperation_HEALTH(self, *args: list[str]) -> list[PCActionResult]:
        self.checkBounds(args)
        new_val = self.newValue(args)
        new_health = validateHealthSTS(self.trait['text_value'], new_val, self.doImmediatelyConvertBashingToLethal())
        self.trait = self.db_setCurvalue(new_val, self.trait)
        self.trait = self.db_setTextValue(new_health, self.trait)
        return [PCActionResultTrait(self.trait)] 
    def _handleOperation_Base(self, *args: list[str]) -> list[PCActionResult]:
        new_val = self.newValue(args)
        self.trait = self.db_setCurvalue(new_val, self.trait)
        return [PCActionResultTrait(self.trait)]

class PCTraitAction_STS_RESET(PCTraitAction_STS_ModifyCurValue):
    def newValue(self, args: list[str]):
        return self.trait['max_value'] if (int(self.trait['trackertype']) != TrackerType.UNCAPPED) else 0

class PCTraitAction_STS_EQ(PCTraitAction_STS_ModifyCurValue):
    def newValue(self, args: list[str]):
        return InputValidator(self.ctx).validateInteger(args[0])

class PCTraitAction_STS_ADD(PCTraitAction_STS_ModifyCurValue):
    def newValue(self, args: list[str]):
        return self.trait['cur_value'] + InputValidator(self.ctx).validateInteger(args[0])

class PCTraitAction_STS_SUB(PCTraitAction_STS_ModifyCurValue):
    def newValue(self, args: list[str]):
        return self.trait['cur_value'] - InputValidator(self.ctx).validateInteger(args[0])

class PCActionDamage_STS(PCAction):
    def __init__(self, handler: 'PCActionHandler', ctx: SecurityContext, character) -> None:
        super().__init__(handler, ctx, character)
        self.trait = self.ctx.getDBManager().getTrait_LangSafe(self.character['id'], 'salute', self.ctx.getLID())
        self.expectedParameterNumbers = (0, 1, 2)
    def doImmediatelyConvertBashingToLethal(self) -> bool:
        return False
    def canUnpackLethalToBashing(self) -> bool:
        return False
    def doHandle(self, *args: tuple[str]) -> list[PCActionResult]:
        if len(args) == 0: # we're nice and show the health trait if no argument is passed
            return self.handler.viewTraitAction(self.handler, self.ctx, self.character, self.trait).handle()

        op = args[0]
        dmgstr = ""
        if not op in OPCODES_ALL:
            raise GreedyOperationError("string_error_unsupported_operation", (op,))
        if not op in OPCODES_RESET:
            dmgstr = args[1]

        if op in OPCODES_RESET:
            self.trait = self.db_setTextValue('', self.trait)
            response = [PCActionResultTrait(self.trait)]
        elif op in OPCODES_EQ:
            new_health = validateHealthSTS(dmgstr, self.trait['cur_value'], self.doImmediatelyConvertBashingToLethal())
            self.trait = self.db_setTextValue(new_health, self.trait)
            response = [PCActionResultTrait(self.trait)]
        elif op in OPCODES_ADD:
            response = self.doAddDamage(dmgstr)
        elif op in OPCODES_SUB:
            response = self.doSubtractDamage(dmgstr)
        
        
        return response
    def doAddDamage(self, damage_expression: str):
        n, dmgtype = validateDamageExprSTS(damage_expression, self.ctx)
        new_health = validateHealthSTS(self.trait['text_value'], self.trait['cur_value'], self.doImmediatelyConvertBashingToLethal())
        
        rip = False
        for i in range(n): # apply damage one by one
            if len(new_health) < self.trait['cur_value']: # Damage  tracker is not filled yet
                if dmgtype == DMG_BASHING:
                    first_bashing = new_health.find(DMG_BASHING)
                    if first_bashing >= 0 and self.doImmediatelyConvertBashingToLethal():
                        # converting the last char to an l is faster, but does not keep a consistent health string if we switch between systems
                        new_health = new_health[:first_bashing] + DMG_LETHAL + new_health[first_bashing+1:]
                    else:
                        new_health += DMG_BASHING
                elif dmgtype == DMG_AGGRAVATED:
                    new_health = DMG_AGGRAVATED+new_health
                else:
                    la = new_health.rfind(DMG_AGGRAVATED)+1
                    new_health = new_health[:la] + DMG_LETHAL + new_health[la:]    
            else: # Damage tracker is full
                convert_to_agg = False
                if dmgtype == DMG_AGGRAVATED:
                    rip = True
                
                # attempt to convert bashing+bashing to lethal, otherwise just convert the last non aggravated level to aggravated
                if dmgtype == DMG_BASHING:
                    first_bashing = new_health.find(DMG_BASHING)
                    if first_bashing >= 0:
                        new_health = new_health[:first_bashing] + DMG_LETHAL + new_health[first_bashing+1:]
                    else: # no bashing to convert to lethal 
                        convert_to_agg = True
                else:
                    convert_to_agg = True

                if convert_to_agg:
                    la = new_health.rfind(DMG_AGGRAVATED)+1
                    if la < len(new_health):
                        new_health = new_health[:la] + DMG_AGGRAVATED + new_health[la+1:]
                    else: # tracker is filled with aggravated
                        rip = True

        if new_health.count(DMG_AGGRAVATED) >= self.trait['cur_value']:
            rip = True

        new_health = validateHealthSTS(new_health, self.trait['cur_value'], self.doImmediatelyConvertBashingToLethal())
        self.trait = self.db_setTextValue(new_health, self.trait)
        response = [PCActionResultTrait(self.trait)]
        if rip:
            response.append(PCActionResultText("+RIP+"))
        return response
    def doSubtractDamage(self, damage_expression: str):
        n, dmgtype = validateDamageExprSTS(damage_expression, self.ctx)
        new_health = validateHealthSTS(self.trait['text_value'], self.trait['cur_value'], self.doImmediatelyConvertBashingToLethal())

        if dmgtype == DMG_AGGRAVATED:
            if new_health.count(dmgtype) < n:
                raise GreedyTraitOperationError("string_error_not_enough_X", (self.ctx.getLanguageProvider().get(self.ctx.getLID(), "string_aggravated_dmg_plural"),))
            else:
                new_health = new_health[n:]
        elif dmgtype == DMG_LETHAL:
            if new_health.count(dmgtype) < n:
                raise GreedyTraitOperationError("string_error_not_enough_X", (self.ctx.getLanguageProvider().get(self.ctx.getLID(), "string_lethal_dmg_plural"),))
            else:
                fl = new_health.find(dmgtype)
                new_health = new_health[:fl]+new_health[fl+n:]
        else:
            unpack_lethal = self.canUnpackLethalToBashing() 
            if (new_health.count(dmgtype) + new_health.count(DMG_LETHAL)*2*int(unpack_lethal)) < n:
                raise GreedyTraitOperationError("string_error_not_enough_X", (self.ctx.getLanguageProvider().get(self.ctx.getLID(), "string_bashing_dmg_plural"),))
            
            for i in range(n):
                if new_health[-1] == DMG_BASHING:
                    new_health = new_health[:-1]
                elif new_health[-1] == DMG_LETHAL and unpack_lethal:
                    new_health = new_health[:-1]+DMG_BASHING
                else:
                    raise GreedyTraitOperationError("string_error_not_enough_X", (self.ctx.getLanguageProvider().get(self.ctx.getLID(), "string_bashing_dmg_plural"),))

        new_health = validateHealthSTS(new_health, self.trait['cur_value'], self.doImmediatelyConvertBashingToLethal())
        self.trait = self.db_setTextValue(new_health, self.trait)
        return [PCActionResultTrait(self.trait)]

class PCActionDamage_V20HB(PCActionDamage_STS):
    def doImmediatelyConvertBashingToLethal(self) -> bool:
        return True
    def canUnpackLethalToBashing(self) -> bool:
        return True

class PCActionHandler:
    def __init__(self, ctx: SecurityContext, character, can_edit: bool) -> None:
        self.ctx = ctx
        self.character = character
        self.canEditCharacter = can_edit
        self.actions: dict[tuple[str], type[PCAction]] = {}
        self.traitOps: dict[tuple[str], type[PCTraitAction]] = {}
        self.viewTraitAction: type[PCTraitAction] = None
        self.nullAction: type[PCAction] = None
    def handle(self, args, macro = False) -> list[PCActionResult]:
        if len(args) == 0:
            action = self.nullAction(self, self.ctx, self.character)
            return action.handle()
        
        args = detach_args(args)
        whatstr = args[0]
        
        # ACTIONS

        for k, v in self.actions.items():
            if whatstr in k:
                action = v(self, self.ctx, self.character)
                return action.handle(*args[1:])
        
        # MACROS
        
        if not macro: # we don't allow macro nesting
            im, macro = self.ctx.getDBManager().validators.getValidateCharacterMacro(self.character['id'], whatstr).validate()
            if im:
                macro_content = macro[ghostDB.FIELDNAME_CHARACTERMACRO_MACROCOMMANDS]
                return self.handle_macro(macro_content, args)

        # TRAIT OPERATIONS

        trait = self.ctx.getDBManager().getTrait_LangSafe(self.character['id'], whatstr, self.ctx.getLID())

        if len(args) == 1: # only trait name
            return self.viewTraitAction(self, self.ctx, self.character, trait).handle()

        if not self.canEditCharacter:
            raise GreedyOperationError("string_error_cannot_edit_character")

        traitOpstr = args[1]

        for k, v in self.traitOps.items():
            if traitOpstr in k:
                action = v(self, self.ctx, self.character, trait)
                return action.handle(*args[2:])
        raise GreedyOperationError("string_error_unsupported_operation", (traitOpstr,))
    def handle_macro(self, macro_text: str, args: list[str]) -> list[PCActionResult]:
        macro_commands = list(map(lambda x: x.strip(), macro_text.split("\n")))
        results: list[PCActionResult] = []
        silent = False
        for cmd in macro_commands:
            if cmd != '':
                cmd_split = [y for y in cmd.split(" ") if y != ''] 
                base_cmd = cmd_split[0]
                try:
                    if base_cmd == "me":
                        result = self.handle(cmd_split[1:], True)
                        if not silent:
                            results.extend(result)
                    elif base_cmd.lower() == "silent_mode_on":
                        silent = True
                    elif base_cmd.lower() == "silent_mode_off":
                        silent = False
                    elif base_cmd == "roll": # TODO
                        raise NotImplementedError("Soon™")
                    else:
                        #TODO check for character ID? remember that if we do, permissions need to be checked for the character
                        raise GreedyOperationError("string_error_unsupported_operation", (base_cmd,))
                except lng.LangSupportException as e:
                    results.append(PCActionResultText(self.ctx.getLanguageProvider().formatException(self.ctx.getLID(), e)))
                
        return results

class PCActionHandler_STS(PCActionHandler):
    def __init__(self, ctx: SecurityContext, character, can_edit: bool) -> None:
        super().__init__(ctx, character, can_edit)
        self.traitOps[OPCODES_ADD] = PCTraitAction_STS_ADD
        self.traitOps[OPCODES_EQ] = PCTraitAction_STS_EQ
        self.traitOps[OPCODES_RESET] = PCTraitAction_STS_RESET
        self.traitOps[OPCODES_SUB] = PCTraitAction_STS_SUB
        self.actions[ACTIONS_DAMAGE] = PCActionDamage_STS
        self.viewTraitAction = PCTraitAction_ViewTrait

class PCActionHandler_V20HB(PCActionHandler_STS):
    def __init__(self, ctx: SecurityContext, character, can_edit: bool) -> None:
        super().__init__(ctx, character, can_edit)
        self.actions[ACTIONS_DAMAGE] = PCActionDamage_V20HB

ActionHandlerMappings: dict[int, type[PCActionHandler]] = {
    #gms.GameSystems.GENERAL: PCActionHandler_STS,
    GameSystems.STORYTELLER_SYSTEM: PCActionHandler_STS,
    GameSystems.V20_VTM_HOMEBREW_00: PCActionHandler_V20HB,
    GameSystems.V20_VTM_VANILLA: PCActionHandler_STS
    #gms.GameSystems.DND_5E: RollParser_DND5E,
}

def getHandler(gamesystem: int):
    """ Gets an Action Handler from a GameSystem enum """
    return ActionHandlerMappings[gamesystem]