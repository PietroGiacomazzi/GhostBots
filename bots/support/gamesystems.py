import random
from typing import Any
import lang as lng

from .utils import *
from .security import *
from .vtm_res import *


RollType = enum("NORMAL", "SUM", "DAMAGE", "PROGRESS", "INITIATIVE", "REFLEXES", "SOAK")
RollArg = enum("DIFF", "MULTI", "SPLIT", "ROLLTYPE", "PENALTY", "DICE", "PERMANENT_DICE",  "PERMANENT", "STATS", "CHARACTER", "MINSUCC") # argomenti del tiro

GameSystems = enum(*GAMESYSTEMS_LIST)

def getGamesystem(gamesystem: str) -> int:
    """ Gets a game system enum from its identifier string """
    if gamesystem in GAMESYSTEMS_LIST:
        return getattr(GameSystems, gamesystem)
    raise lng.LangException("string_error_invalid_rollsystem", gamesystem)

class GreedyRollValidationError(lng.LangSupportException):
    pass

class GreedyRollExecutionError(lng.LangSupportException):
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
