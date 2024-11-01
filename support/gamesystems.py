from math import inf
from copy import deepcopy
from typing import Any
import random, logging
from typing import Any
import lang as lng
from support import ghostDB
from support.security import SecurityContext

from .utils import *
from .security import *
from .vtm_res import *
from .config import *

_log = logging.getLogger(__name__)

RollType = enum("NORMAL", "DIFFICULTY", "SUM", "DAMAGE", "PROGRESS", "INITIATIVE", "REFLEXES", "SOAK")
RollArg = enum("DIFF", "MULTI", "SPLIT", "ROLLTYPE", "PENALTY", "DICE", "PERMANENT", "STATS", "CHARACTER", "MINSUCC", "SESSION") # argomenti del tiro

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
PENALITA_CMD = ("penalita", "penalità", "penalty", "pen")
NOPENALITA_CMD = ("nopenalita", "nopenalità", "nopenalty", "nopen")
DADI_CMD = ("dadi", "dice")
ADD_CMD = "+"
SUB_CMD = "-"
PERMANENTE_CMD = ("permanente", "permanent", "perm")
TEMPORARY_CMD = ("temporanea", "temporaneo", "temporanei", "temporanee", "temporary", "temp", "tmp")
STATISTICS_CMD = ("statistica", "stats", "stat")
MINSUCC_CMD = ('minsucc', 'mins', 'ms')

SOAK_CMD = ("soak", "assorbi")
INIZIATIVA_CMD = ("iniziativa", "initiative", "iniz")
RIFLESSI_CMD = ("riflessi", "reflexes", "r")

TrackerType = enum("NORMAL", "CAPPED", "HEALTH", "UNCAPPED")

DMG_BASHING = 'c'
DMG_LETHAL = 'l'
DMG_AGGRAVATED = 'a'
DAMAGE_TYPES = [DMG_AGGRAVATED, DMG_LETHAL, DMG_BASHING] # it is important that the order is a, l, c

BASHING_idx = DAMAGE_TYPES.index(DMG_BASHING)
LETHAL_idx = DAMAGE_TYPES.index(DMG_LETHAL)

GameSystems = enum(*GAMESYSTEMS_LIST)
GameStates = enum(*GAMESTATES_LIST)

OPCODES_ADD = ('+',)
OPCODES_SUB = ('-',)
OPCODES_EQ = ('=',)
OPCODES_RESET = ('r', 'reset')
DETACH_SPECIAL = OPCODES_ADD+OPCODES_SUB+OPCODES_EQ

OPCODES_ALL = OPCODES_ADD + OPCODES_EQ + OPCODES_RESET + OPCODES_SUB

ACTIONS_DAMAGE = ('danni', 'danno', 'damage', 'dmg')

SILENT_WITHERROR_CMD_PREFIX_MACRO  = '§'
SILENT_NOERROR_CMD_PREFIX_MACRO  = '#'

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

def getGamesystem(gamesystemid: str) -> int:
    """ Gets a game system enum from its identifier string """
    if gamesystemid in GAMESYSTEMS_LIST:
        return getattr(GameSystems, gamesystemid)
    raise lng.LangException("string_error_invalid_rollsystem", gamesystemid)

def getGamesystemId(gamesystem: int) -> str:
    """ Gets a Game system string from its enum value """
    if gamesystem >=0 and gamesystem < len(GAMESYSTEMS_LIST):
        return GAMESYSTEMS_LIST[gamesystem]
    raise lng.LangException("string_error_invalid_rollsystem", gamesystem)

def getGenerationalLimit(generation_dots: int) -> int:
    if generation_dots <= 3:
        return 1
    elif generation_dots == 4:
        return 2
    elif generation_dots == 5:
        return 3
    elif generation_dots == 6:
        return 4
    elif generation_dots == 7:
        return 6
    elif generation_dots == 8:
        return 8
    elif generation_dots == 9:
        return 10
    else:
        return None


class GreedyParseError(lng.LangSupportException):
    pass

class GreedyParseValidationError(lng.LangSupportException):
    pass

class GreedyRollValidationError(lng.LangSupportException):
    pass

class GreedyRollExecutionError(lng.LangSupportException):
    pass

class GreedyOperationError(lng.LangSupportException):
    pass

class GreedyTraitOperationError(GreedyOperationError):
    pass

class GreedyGamesystemError(lng.LangSupportException):
    pass


class RollItem:
    def __init__(self) -> None:
        self.tag:  str = None
        self.results: list[int] = None
        self.faces: int = None
        self.additional_data: Any = None
        self.count_successes: int = None
        self.difficulty: int = None

class RollItem_STS(RollItem):
    def  __init__(self) -> None:
        super().__init__()
        self.canceled: int = None
        self.minsucc: int = None
        self.extra_succ: int = None

class RollData:
    def __init__(self, rolltype: int, comments: list[str], statistics = False) -> None:
        self.rolltype = rolltype
        self.statistics = statistics
        self.data: list[RollItem] = []
        self.comments = comments

class RollSetup:
    def __init__(self, ctx: SecurityContext, gamesystemid: str) -> None:
        self.rollArguments: dict[int, Any] = {}
        self.validatorClasses: list[type[RollSetupValidator]] = []
        self.ctx = ctx
        self.actionHandlers: dict[int, type[RollAction]] = {}
        self.traits = set()
        self.comments: list[str] = []
        self.gamesystemid = gamesystemid
    def roll(self) -> RollData:
        self.buildComments()
        action = self.getRollType()
        if action in self.actionHandlers:
            handlerClass = self.actionHandlers[action]
            handler = handlerClass(self)
            return handler.execute(action)
        raise GreedyRollExecutionError("string_error_roll_invalid_param_combination")
    def getRollType(self) -> int:
        return self.rollArguments[RollArg.ROLLTYPE] if RollArg.ROLLTYPE in self.rollArguments else self.getDefaultRollType() 
    def getDefaultRollType(self) -> int:
        return RollType.NORMAL
    def validate(self):
        for cls in self.validatorClasses:
            validator = cls()
            validator.validate(self)
    def getPool(self) -> int:
        """ Get total number of rolled dice """
        if RollArg.DICE not in self.rollArguments:
            raise GreedyRollValidationError("string_error_no_dice_specified")
        pool = 0
        for k, v in self.rollArguments[RollArg.DICE].items():
            if k != 0:
                pool += self.getPoolFaces(k)
        return pool
    def getPoolFaces(self, faces: int, fallback: int = None) -> int:
        """ Get number of rolled dice for a given die size. If a fallback value is specified, it will be returned in case the die size is unused """
        if fallback is not None and faces not in self.rollArguments[RollArg.DICE]:
            return fallback
        components: list[RollPoolComponent] = self.rollArguments[RollArg.DICE][faces]
        return sum(map(lambda c: c.getDice(self), components))
    def getSession(self):
        if not RollArg.SESSION in self.rollArguments:
            self.rollArguments[RollArg.SESSION] = self.ctx.getRunningSession()
        return self.rollArguments[RollArg.SESSION]
    def getCharacter(self):
        if not RollArg.CHARACTER in self.rollArguments:
            self.rollArguments[RollArg.CHARACTER] = self.ctx.getActiveCharacter()
        return self.rollArguments[RollArg.CHARACTER]
    def addComment(self, commentstr: str):
        self.comments.append(commentstr)
    def addCommentLang(self, commentlabel, *args):
        self.addComment(self.ctx.getLanguageProvider().get(self.ctx.getLID(), commentlabel, *args))
    def buildComments(self):
        pass

class RollSetup_General(RollSetup):
    def __init__(self, ctx: SecurityContext, gamesystemid: str) -> None:
        super().__init__(ctx, gamesystemid)
        self.actionHandlers[RollType.NORMAL] = RollAction_GeneralRoll
        self.actionHandlers[RollType.SUM] = RollAction_GeneralRoll
        self.actionHandlers[RollType.DIFFICULTY] = RollAction_GeneralRoll
    def getDefaultRollType(self) -> int:
        return RollType.SUM

class RollSetup_STS(RollSetup_General):
    def __init__(self, ctx: SecurityContext, gamesystemid: str) -> None:
        super().__init__(ctx, gamesystemid)
        self.actionHandlers[RollType.DIFFICULTY] = RollAction_STS_RegularRoll
        self.actionHandlers[RollType.DAMAGE] = RollAction_STS_Damage
        self.actionHandlers[RollType.INITIATIVE] = RollAction_STS_Initiative
        self.actionHandlers[RollType.REFLEXES] = RollAction_STS_RegularRoll
        self.actionHandlers[RollType.SOAK] = RollAction_STS_RegularRoll
        self.penaltyValue = None
    def getDefaultRollType(self) -> int:
        return RollType.DIFFICULTY
    def getPenalty(self, recompute = False) -> int:
        """ Gets the penalty dice for the current roll. will take any factors into account, such as explicit penalty, trait settings and game system. passing recompute = True will cause the rollsetup cache penalty value (if present) to be ignored """
        if self.penaltyValue is None or recompute:
            if (RollArg.PENALTY in self.rollArguments) and self.rollArguments[RollArg.PENALTY]:
                character = self.getCharacter()
                health = self.ctx.getDBManager().getTrait_LangSafe(character['id'], 'salute', self.ctx.getLID())
                penalty, _ = parseHealth(health)
                self.penaltyValue = penalty[0] # save penalty value for future use. for example, a validator might ask for getPool, and we want to avoid making extra queries if we can
            else:
                self.penaltyValue = 0
        return self.penaltyValue
    def getPool(self) -> int:
        pool = super().getPool() + self.getPenalty()
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
    def buildComments(self):
        super().buildComments()
        for k, v in self.rollArguments[RollArg.DICE].items():
            if k != 0:
                components: list[RollPoolComponent] = v
                for component in components:
                    if isinstance(component, RollPoolComponent_Trait):
                        pen = self.getPenalty()
                        if component.getSettings(self).autopenalty and pen < 0:
                            self.addCommentLang("string_autopenalty_trait", pen, 10, component.trait['traitName'])
                        perm_not_overridden = self.rollArguments[RollArg.PERMANENT] if RollArg.PERMANENT in self.rollArguments else True
                        if component.getSettings(self).rollpermanent and perm_not_overridden:
                            self.addCommentLang("string_rollpermanent_trait", component.trait['traitName'])

class RollSetup_V20HB(RollSetup_STS):        
    def __init__(self, ctx: SecurityContext, gamesystemid: str) -> None:
        super().__init__(ctx, gamesystemid)
        self.actionHandlers[RollType.DIFFICULTY] = RollAction_V20HB_RegularRoll
        self.actionHandlers[RollType.DAMAGE] = RollAction_V20HB_Damage
        self.actionHandlers[RollType.PROGRESS] = RollAction_V20HB_ProgressRoll
        self.actionHandlers[RollType.REFLEXES] = RollAction_V20HB_RegularRoll
        self.actionHandlers[RollType.SOAK] = RollAction_V20HB_Damage
        
class RollSetup_V20VANILLA(RollSetup_STS):
    def __init__(self, ctx: SecurityContext, gamesystemid: str) -> None:
        super().__init__(ctx, gamesystemid)

class RollPoolComponent:
    def __init__(self, n_dice: int) -> None:
        self.n_dice = n_dice
    def getDice(self, rollSetup: RollSetup) -> int:
        return self.n_dice
    
class RollPoolComponent_Trait(RollPoolComponent):
    def __init__(self, trait, sign = 1) -> None:
        super().__init__(0)
        self.trait = trait
        self.sign = sign
        self.settings: ghostDB.TraitSettings = None
    def getSettings(self, rollSetup: RollSetup):
        if self.settings is None:
            self.settings = rollSetup.ctx.getDBManager().buildTraitSettings(self.trait[ghostDB.FIELDNAME_TRAIT_TRAITID], rollSetup.getSession()[ghostDB.FIELDNAME_GAMESESSION_GAMESTATEID], rollSetup.gamesystemid)
        return self.settings          
    def getDice(self, rollSetup: RollSetup) -> int:
        permanent = False
        if RollArg.PERMANENT in rollSetup.rollArguments:
            permanent = rollSetup.rollArguments[RollArg.PERMANENT]
        else:
            permanent = self.getSettings(rollSetup).rollpermanent
        
        if permanent:
            return self.sign * self.trait[ghostDB.FIELDNAME_TRAIT_MAX_VALUE]
        return self.sign * self.trait[ghostDB.FIELDNAME_TRAIT_CUR_VALUE]
    def getAutoPenalty(self, rollSetup: RollSetup) -> bool:
        return self.getSettings(rollSetup).autopenalty

class RollAction:
    def __init__(self, setup: RollSetup) -> None:
        self.setup = setup
    def initRollData(self, rolltype: int) -> RollData:
        return RollData(rolltype, self.setup.comments, RollArg.STATS in self.setup.rollArguments)
    def execute(self, rolltype: int) -> RollData:
        return self.initRollData(rolltype)

class RollAction_GeneralRoll(RollAction):
    def execute(self, rolltype: int) -> RollData:
        rdata = self.initRollData(rolltype)
        if RollArg.DICE in self.setup.rollArguments: 
            diff = self.setup.rollArguments[RollArg.DIFF] if RollArg.DIFF in self.setup.rollArguments else 0
            for faces, pcs in self.setup.rollArguments[RollArg.DICE].items():
                number = self.setup.getPoolFaces(faces)
                item = RollItem()
                item.faces = faces
                item.difficulty = diff
                item.count_successes = 0
                if faces:
                    item.tag = f'd{faces}'
                    item.results = list(map(lambda x: random.randint(1, faces), range(0, number))) 
                    if diff:
                        item.count_successes = len(list(filter(lambda x: x >= diff, item.results)))
                else:
                    item.tag = f'flat'
                    item.results = [number]
                    item.count_successes = number
                rdata.data.append(item)
        return rdata

class RollAction_STS(RollAction):
    def __init__(self, setup: RollSetup_STS) -> None:
        super().__init__(setup)
        self.setup = setup # here just for type hinting suggestions
    def shouldCancel(self) -> bool:
        return True
    def shouldSpec(self) -> bool:
        return False

class RollAction_STS_Initiative(RollAction_STS):
    def execute(self, rolltype: int) -> RollData:
        lid = self.setup.ctx.getLID()
        rd = self.initRollData(rolltype)

        add = self.setup.getPoolFaces(0, 0)
        raw_roll = random.randint(1, 10)
        bonuses_log = []
        bonus = add
        if add:
            bonuses_log.append(self.setup.ctx.getLanguageProvider().get(lid, "string_bonus_X", add))

        character = self.setup.getCharacter()
        for traitid in ['prontezza', 'destrezza', 'velocità']: # TODO dehardcode into settings? remember that we need both quiet and stress configs!
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
    def execute(self, rolltype: int) -> RollData:
        lid = self.setup.ctx.getLID()
        diff = self.setup.rollArguments[RollArg.DIFF]
        ndice = self.setup.getPool()

        extra_successes = self.setup.getPoolFaces(0, 0)
        
        rd = self.initRollData(rolltype)

        roll_item = self.setup.rollPool(ndice, diff, extra_successes, canceling=self.shouldCancel(), spec=self.shouldSpec())
        roll_item.tag = f'{self.setup.ctx.getLanguageProvider().get(lid, "string_roll")}'
        rd.data.append(roll_item)

        return rd

class RollAction_STS_RegularRoll(RollAction_STS):
    def execute(self, rolltype: int) -> RollData:
        lid = self.setup.ctx.getLID()
        diff = self.setup.rollArguments[RollArg.DIFF] #if RollArg.DIFF in self.rollArguments else 6
        ndice = self.setup.getPool()
        extra_successes = self.setup.getPoolFaces(0, 0)
        min_succ = self.setup.rollArguments[RollArg.MINSUCC] if RollArg.MINSUCC in self.setup.rollArguments else 1

        rd = self.initRollData(rolltype)

        if RollArg.MULTI in self.setup.rollArguments:
            multi = self.setup.rollArguments[RollArg.MULTI] 
            ndice_multi = ndice//multi
            ndice_rem = ndice % multi
            for i in range(multi):
                extra_die = 1 if i < ndice_rem else 0
                roll_item = self.setup.rollPool(ndice_multi+extra_die, diff, extra_successes, canceling=self.shouldCancel(), spec=self.shouldSpec(), minsucc=min_succ)
                roll_item.tag = f'{self.setup.ctx.getLanguageProvider().get(lid, "string_action")} {i+1}'
                rd.data.append(roll_item)
        else: # 1 tiro solo 
            roll_item = self.setup.rollPool(ndice, diff, extra_successes, canceling=self.shouldCancel(), spec=self.shouldSpec(), minsucc=min_succ)
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
        extra_successes = self.setup.getPoolFaces(0, 0)
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
                        roll_item = self.setup.rollPool(pools[j], split_diffs[j], extra_successes, canceling=self.shouldCancel(), spec=self.shouldSpec(), minsucc=min_succ)
                        roll_item.tag = f'{base_tag}: {self.setup.ctx.getLanguageProvider().get(lid, "string_roll")} {j+1}'
                        rd.data.append(roll_item)
                else:
                    roll_item = self.setup.rollPool(ndice_m, diff, extra_successes, canceling=self.shouldCancel(), spec=self.shouldSpec(), minsucc=min_succ)
                    roll_item.tag = base_tag
                    rd.data.append(roll_item)
        else: # 1 tiro solo 
            if not split is None:
                split_diffs = split[0]
                pools = [(ndice-ndice//2), ndice//2]
                for j in range(len(pools)):
                    roll_item = self.setup.rollPool(pools[j], split_diffs[j], extra_successes, canceling=self.shouldCancel(), spec=self.shouldSpec(), minsucc=min_succ)
                    roll_item.tag = f'{self.setup.ctx.getLanguageProvider().get(lid, "string_roll")} {j+1}'
                    rd.data.append(roll_item)
            else:
                roll_item = self.setup.rollPool(ndice, diff, extra_successes, canceling=self.shouldCancel(), spec=self.shouldSpec(), minsucc=min_succ)
                roll_item.tag = f'{self.setup.ctx.getLanguageProvider().get(lid, "string_roll")}'
                rd.data.append(roll_item)
        return rd

class RollAction_V20HB_ProgressRoll(RollAction_V20HB_RegularRoll):
    def shouldSpec(self) -> bool:
        return True
    def shouldCancel(self) -> bool:
        return False

class RollSetupValidator:
    def validate(self, setup: RollSetup):
        pass

class RollSetupValidator_DICE(RollSetupValidator):
    def validate(self, setup: RollSetup):
        super().validate(setup)
        pool = setup.getPool()

        max_dice = int(setup.ctx.getAppConfig()['BotOptions']['max_dice'])
        if pool > max_dice:
            raise GreedyRollValidationError("string_error_toomany_dice", (pool,))
        if pool <= 0:
            raise GreedyRollValidationError("string_error_toofew_dice", (pool,))

class RollSetupValidator_GENERAL_DIFF(RollSetupValidator):
    def validate(self, setup: RollSetup):
        super().validate(setup)
        if RollArg.DIFF in setup.rollArguments and RollArg.DICE in setup.rollArguments:
            diff = setup.rollArguments[RollArg.DIFF]
            face_list = list(filter(lambda x: x > 0, setup.rollArguments[RollArg.DICE].keys()))
            min_faces = min(face_list) if len(face_list) else 0 # if no dice, min_faces is 0, which wil fail the check as diff must be at least 1
            if diff < 1 or diff > min_faces:
                raise GreedyRollValidationError('string_error_x_isnot_y', (diff, setup.ctx.getLanguageProvider().get(setup.ctx.getLID(), 'string_errorpiece_valid_diff')))

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
            

#  --- ROLL PARSING  ---

class RollArgumentParser:
    def __init__(self, validator: type[RollSetupValidator], has_parameters = False) -> None:
        self.has_parameters = has_parameters
        self.detach_end = False
        self.validatorClass = validator
        self.character = None
        self.session = None
        
        # these are used by the parsing methods to keep track of where we are in the argument list
        self.current_keyword = ''
        self.cursor = -1 
        self.arguments =  []
    def _parse_internal(self, refSetup: RollSetup):
        raise NotImplementedError()
    def _save_setup(self, currentSetup: RollSetup):
        if (not RollArg.CHARACTER in currentSetup.rollArguments) and (self.character is not None): # every time we successfully parse something, if we got a character from DB, we save the character into the setup for future use
            currentSetup.rollArguments[RollArg.CHARACTER] = self.character
        # we currently (2024-04-30) have no need to retrieve the active session during parsing, but once we do, this will support saving it to the final rollSetup
        if (not RollArg.SESSION in currentSetup.rollArguments) and (self.session is not None):
            currentSetup.rollArguments[RollArg.SESSION] = self.session
    def parse(self, ctx: SecurityContext, arguments: list[str], i: int, currentSetup: RollSetup, keyword = True) -> int:        
        # set the cursor to the current position
        self.current_keyword = arguments[i]
        self.cursor = i+1 if keyword else i
        self.arguments = arguments

        temp_ctx = currentSetup.ctx # ctx cannot be pickled for deepcopy
        currentSetup.ctx = None
        referenceSetup = deepcopy(currentSetup)
        currentSetup.ctx = temp_ctx
        referenceSetup.ctx = temp_ctx
        self._parse_internal(referenceSetup) # cursor will be updated by the parsing methods

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
    def mergeDice(self, pool: dict[int, list[RollPoolComponent]], currentSetup: RollSetup, mergefunc = lambda x, y: x+y):
        if RollArg.DICE in currentSetup.rollArguments:
            currentSetup.rollArguments[RollArg.DICE] = merge(currentSetup.rollArguments[RollArg.DICE], pool, mergefunc)
        else:
            currentSetup.rollArguments[RollArg.DICE] = pool
    def loadSessionCtx(self, refSetup: RollSetup):
        """ utility method for parsers, get the relevant character and session either from the roll setup (if already present) or get it from context """
        if RollArg.CHARACTER in refSetup.rollArguments:
            self.character = refSetup.rollArguments[RollArg.CHARACTER]
        if RollArg.SESSION in refSetup.rollArguments:
            self.session = refSetup.rollArguments[RollArg.SESSION]
        # refsetup has no ctx!
        if self.character is None:
            self.character = refSetup.ctx.getActiveCharacter()
        if self.session is None:
            self.session = refSetup.ctx.getRunningSession()
    # parameter parsers
    def parseItem(self) -> str:
        if self.cursor < len(self.arguments):
            item = self.arguments[self.cursor]
            self.cursor += 1
            return item
        
        raise GreedyParseError("string_error_x_what", (self.current_keyword,))
    def parseInteger(self, ctx: SecurityContext, err_msg: str = None) -> int:
        item = self.parseItem()
        return self.validateInteger(item, ctx, err_msg)
    def validateInteger(self, item, ctx: SecurityContext, err_msg: str = None): # TODO InputValidator
        try:
            return int(item)
        except ValueError:
            if err_msg == None: 
                err_msg = ctx.getLanguageProvider().get(ctx.getLID(), "string_errorpiece_integer")
            raise GreedyParseValidationError("string_error_x_isnot_y", (item, err_msg))
    def parseBoundedInteger(self, ctx: SecurityContext, min_val: int = -inf, max_val: int = inf, err_msg : str = None) -> int:
        item = self.parseItem()
        return self.validateBoundedInteger(item, ctx, min_val, max_val, err_msg)
    def validateBoundedInteger(self, item, ctx: SecurityContext, min_val: int = -inf, max_val: int = inf, err_msg: str = None) -> int: # TODO InputValidator
        val = self.validateInteger(item, ctx)
        if val < min_val or val > max_val:
            if err_msg == None:
                err_msg = ctx.getLanguageProvider().get(ctx.getLID(), "string_errorpiece_number_in_range", min_val, max_val)
            raise GreedyParseValidationError("string_error_x_isnot_y", (val, err_msg))
        return val

class RollArgumentParser_KeywordActivateOnly(RollArgumentParser):
    def __init__(self, validator: RollSetupValidator, rollArgKey: int, rollTypeVal: int = None, rollArgVal = True) -> None:
        super().__init__(validator)
        self.rollArgKey = rollArgKey
        self.rollArgVal = rollArgVal
        self.rollTypeVal = rollTypeVal
    def _parse_internal(self, refSetup: RollSetup):
        pass
    def _save_setup(self, currentSetup: RollSetup):
        super()._save_setup(currentSetup)
        if self.rollArgKey != RollArg.ROLLTYPE:
            currentSetup.rollArguments[self.rollArgKey] = self.rollArgVal
        if not self.rollTypeVal is None:
            currentSetup.rollArguments[RollArg.ROLLTYPE] = self.rollTypeVal

class RollArgumentParser_STS_Initiative(RollArgumentParser_KeywordActivateOnly):
    def __init__(self) -> None:
        super().__init__(RollSetupValidator, RollArg.ROLLTYPE, rollTypeVal=RollType.INITIATIVE)
    def _save_setup(self, currentSetup: RollSetup):
        super()._save_setup(currentSetup)
        pool = {10:[RollPoolComponent(1)]}
        self.mergeDice(pool, currentSetup)

class RollArgumentParser_STS_Reflexes(RollArgumentParser_KeywordActivateOnly):
    def __init__(self) -> None:
        super().__init__(RollSetupValidator, RollArg.ROLLTYPE, rollTypeVal=RollType.REFLEXES)
        self.volonta = None
    def getPoolComponent(self, rollSetup: RollSetup) -> RollPoolComponent_Trait:
        pc = RollPoolComponent_Trait(self.volonta)
        pc.getSettings(rollSetup).rollpermanent = 1 # by default, use permanent WP
        return pc
    def _parse_internal(self, refSetup: RollSetup):
        super()._parse_internal(refSetup)
        lid = refSetup.ctx.getLID()
        self.loadSessionCtx(refSetup)
        self.volonta = refSetup.ctx.getDBManager().getTrait_LangSafe(self.character['id'], "volontà", lid)  
    def _save_setup(self, currentSetup: RollSetup):
        super()._save_setup(currentSetup)
        pool = {10: [self.getPoolComponent(currentSetup)]}
        self.mergeDice(pool, currentSetup)

class RollArgumentParser_V20HB_Reflexes(RollArgumentParser_STS_Reflexes):
    def __init__(self) -> None:
        super().__init__()
        self.prontezza = None
    def getPoolComponent(self, rollSetup: RollSetup) -> RollPoolComponent:
        pc = super().getPoolComponent(rollSetup)
        pc.getSettings(rollSetup).rollpermanent = 0 # by default, use temporary WP
        return pc
    def _parse_internal(self, refSetup: RollSetup):
        super()._parse_internal(refSetup)
        lid = refSetup.ctx.getLID()
        self.prontezza = refSetup.ctx.getDBManager().getTrait_LangSafe(self.character['id'], "prontezza", lid) 
    def _save_setup(self, currentSetup: RollSetup):
        super()._save_setup(currentSetup)
        reflex_diff = 10 - (self.prontezza['cur_value'])
        currentSetup.rollArguments[RollArg.DIFF] = currentSetup.rollArguments[RollArg.DIFF] if RollArg.DIFF in currentSetup.rollArguments else reflex_diff

class RollArgumentParser_STS_Soak(RollArgumentParser_KeywordActivateOnly):
    def __init__(self) -> None:
        super().__init__(RollSetupValidator, RollArg.ROLLTYPE, rollTypeVal=RollType.SOAK)
        self.costituzione = None
        self.robustezza = None
    def _parse_internal(self, refSetup: RollSetup):
        super()._parse_internal(refSetup)
        lid = refSetup.ctx.getLID()
        self.loadSessionCtx(refSetup)
        self.costituzione = refSetup.ctx.getDBManager().getTrait_LangSafe(self.character['id'], "costituzione", lid) 
        try:
            self.robustezza = refSetup.ctx.getDBManager().getTrait_LangSafe(self.character['id'], "robustezza", lid)  
        except ghostDB.DBException:
            pass
    def _save_setup(self, currentSetup: RollSetup):
        super()._save_setup(currentSetup)
        pool_comp = [RollPoolComponent_Trait(self.costituzione)]
        if self.robustezza is not None:
            pool_comp.append(RollPoolComponent_Trait(self.robustezza))
        pool = {10: pool_comp}
        self.mergeDice(pool, currentSetup)
        currentSetup.rollArguments[RollArg.DIFF] = currentSetup.rollArguments[RollArg.DIFF] if RollArg.DIFF in currentSetup.rollArguments else 6

class RollArgumentParser_DiceExpression(RollArgumentParser):
    def  __init__(self, validator: type[RollSetupValidator], has_parameters = False, firstNegative = False, detachEnd = False) -> None:
        super().__init__(validator, has_parameters)
        self.detach_end = detachEnd
        self.character = None
        self.dice = None
        self.traits_seen = None
        self.firstNegative = firstNegative
    def getTraitDefaultFaces(self) -> int:
        raise GreedyParseValidationError('string_error_default_die_face_unavailable')
    def transformTrait(self, traitvalue: int) -> int:
        return int(traitvalue)
    def _parse_internal(self, refSetup: RollSetup):
        expr = self.parseItem()
        self.decodeDiceExpression_Mixed(refSetup, expr, self.firstNegative)
    def _save_setup(self, currentSetup: RollSetup):
        super()._save_setup(currentSetup)
        self.mergeDice(self.dice, currentSetup)
        currentSetup.traits.update(self.traits_seen)
        self.character = None
    def buildTraitComponent(self, refSetup: RollSetup, traitdata, sign: bool) -> RollPoolComponent_Trait:
        raise GreedyParseValidationError('I tratti non sono supportati dal roller generico')
    def decodeDiceExpression_Mixed(self, refSetup: RollSetup, what: str, firstNegative: bool = False):
        self.dice = {} # faces -> roll components  (0 means fixed bonus)
        self.traits_seen = set()

        split_add_list = what.split(ADD_CMD) # split on "+", so each of the results STARTS with something to add
        for i in range(0, len(split_add_list)):
            split_add = split_add_list[i]
            split_sub_list = split_add.split(SUB_CMD) # split on "-", so the first element will be an addition (unless firstNegative is true and i == 0), and everything else is a subtraction

            for j in range(0, len(split_sub_list)):
                term = split_sub_list[j]
                sign = -1 if (j > 0 or (i == 0 and firstNegative)) else 1

                dice_merge = {}
                try: # either a xdy expr
                    n_term, faces_term = self.decodeDiceExpression_Dice(term, refSetup.ctx) 
                    dice_merge = {faces_term: [RollPoolComponent(n_term * sign)]}
                except GreedyParseValidationError as e: # or a trait
                    try:
                        lid = refSetup.ctx.getLID()
                        self.loadSessionCtx(refSetup)
                        traitdata = refSetup.ctx.getDBManager().getTrait_LangSafe(self.character['id'], term, lid)
                        dice_merge = {self.getTraitDefaultFaces(): [self.buildTraitComponent(refSetup, traitdata, sign)]}
                        self.traits_seen.add(term)
                    except ghostDB.DBException as edb:
                        try:
                            n_term = self.validateInteger(term, refSetup.ctx)
                            dice_merge = {0: [RollPoolComponent(n_term * sign)]}
                        except GreedyParseValidationError as ve:
                            raise lng.LangSupportErrorGroup("MultiError", [e, edb, ve])

                self.dice = merge(self.dice, dice_merge, lambda x, y: x+y)

        # is it good that if the espression is just flat numbers we can parse it?
        # for example ".roll 3d10 7" will parse the same as ".roll 3d10 +7"

        return 
    def decodeDiceExpression_Dice(self, what: str, ctx: SecurityContext) -> tuple[int, int]:
        split = what.lower().split("d")
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
    def __init__(self, validator: type[RollSetupValidator], has_parameters=False, firstNegative=False, detachEnd=False) -> None:
        super().__init__(validator, has_parameters, firstNegative, detachEnd)
        self.applyPenalty = False
    def getTraitDefaultFaces(self):
        return 10
    def buildTraitComponent(self, refSetup: RollSetup, traitdata, sign: bool) -> RollPoolComponent_Trait:
        trait_comp = RollPoolComponent_Trait(traitdata, sign)
        if trait_comp.getAutoPenalty(refSetup) and RollArg.PENALTY not in refSetup.rollArguments:
            self.applyPenalty = True
        return trait_comp
    def _save_setup(self, currentSetup: RollSetup):
        super()._save_setup(currentSetup)
        if self.applyPenalty:
            currentSetup.rollArguments[RollArg.PENALTY] = True

class RollArgumentParser_DND5E_DiceExpression(RollArgumentParser_DiceExpression):
    def getTraitDefaultFaces(self):
        return 20
    # def decodeTrait(self, ctx: SecurityContext, refSetup: RollSetup, traitdata) -> tuple[dict[int, int], dict[int, int]]:
    #     if len(self.traits_seen) or len(refSetup.traits):
    #         raise GreedyParseValidationError("string_error_only_one_trait_allowed")

    #     raise GreedyParseValidationError("work in progress!")
    #     # we have a bunch of cases:
    #     #   proficiency just does 1d20 plus proficiency (or adds it to a clean roll)
    #     #   an ability should roll the base modifier
    #     #   a skill should do ability_mod + proficiency_bonus*skill_proficiency (saving throws will be 'skill' traits)
    #     # i need a way to detect if a trait is an ability or a skill -> linked trait status might do the trick

    #     proficiency_bonus = ctx.getDBManager().getTrait_LangSafe(self.character['id'], "competenza", ctx.getLID())  
    #     return super().decodeTrait(ctx, refSetup, traitdata)

class RollArgumentParser_SimpleArgumentList(RollArgumentParser):
    def __init__(self, validator: type[RollSetupValidator], rollArgVar: int) -> None:
        super().__init__(validator, True)
        self.rollArgVal: int = rollArgVar
        self.parametersList: list[Any] = []
    def allowMultiple(self, refSetup: RollSetup) -> bool:
        return False
    def _parse_internal(self, refSetup: RollSetup):
        if self.rollArgVal in refSetup.rollArguments and not self.allowMultiple(refSetup):
            raise GreedyParseValidationError('string_error_multiple_X', (self.current_keyword,))
    def aggregateParameters(self) -> Any:
        return self.parametersList
    def _save_setup(self, currentSetup: RollSetup):
        super()._save_setup(currentSetup)
        currentSetup.rollArguments[self.rollArgVal] = self.aggregateParameters()

class RollArgumentParser_SingleParameter(RollArgumentParser_SimpleArgumentList):
    def __init__(self, validator: type[RollSetupValidator], rollArgVar: int) -> None:
        super().__init__(validator, rollArgVar)
    def  _parse_internal(self, refSetup: RollSetup):
        super()._parse_internal(refSetup)
        self.parametersList.append(self.parseSingleParameter(refSetup.ctx))
    def aggregateParameters(self) -> Any:
        return self.parametersList[0]
    def parseSingleParameter(self, ctx: SecurityContext) -> Any:
        raise NotImplementedError()

class RollArgumentParser_DIFF(RollArgumentParser_SingleParameter):
    def __init__(self, validator: type[RollSetupValidator], min_diff: int, max_diff: int) -> None:
        super().__init__(validator, RollArg.DIFF)
        self.minDiff = min_diff
        self.maxDiff  = max_diff
    def parseDifficulty(self, ctx: SecurityContext) -> int:
        return self.parseBoundedInteger(ctx, self.minDiff, self.maxDiff, ctx.getLanguageProvider().get(ctx.getLID(), "string_errorpiece_valid_diff"))
    def parseSingleParameter(self, ctx: SecurityContext):
        return self.parseDifficulty(ctx)

class RollArgumentParser_GENERAL_DIFF(RollArgumentParser_DIFF):
    def __init__(self) -> None:
        super().__init__(RollSetupValidator_GENERAL_DIFF, 1, 0)
    def parseDifficulty(self, ctx: SecurityContext) -> int:
        self.maxDiff = int(ctx.getAppConfig()['BotOptions']['max_faces'])
        return super().parseDifficulty(ctx)
    def _save_setup(self, currentSetup: RollSetup):
        super()._save_setup(currentSetup)
        currentSetup.rollArguments[RollArg.ROLLTYPE] = RollType.DIFFICULTY

class RollArgumentParser_STS_DIFF(RollArgumentParser_DIFF):
    def __init__(self) -> None:
        super().__init__(RollSetupValidator_STS_DIFF, 2, 10)
    def allowMultiple(self, refSetup: RollSetup) -> bool: # this allows players to do stuff like "roll reflexes diff 5", overriding diffs from stuff like reflexes or soak rolls
        return True

class RollArgumentParser_STS_MULTI(RollArgumentParser_SingleParameter):
    def __init__(self, validator: type[RollSetupValidator] = RollSetupValidator_STS_MULTI) -> None:
        super().__init__(validator, RollArg.MULTI)
    def parseSingleParameter(self, ctx: SecurityContext) -> Any:
        return self.parseBoundedInteger(ctx, 2)

class RollArgumentParser_STS_MINSUCC(RollArgumentParser_SingleParameter):
    def __init__(self) -> None:
        super().__init__(RollSetupValidator, RollArg.MINSUCC)
    def parseSingleParameter(self, ctx: SecurityContext) -> Any:
        return self.parseBoundedInteger(ctx, 1)

class RollArgumentParser_V20HB_SPLIT(RollArgumentParser):
    def __init__(self, validator = RollSetupValidator_V20HB_SPLIT) -> None:
        super().__init__(validator, True)
        self.split = {}
    def _parse_internal(self, refSetup: RollSetup):
        index = None
        if RollArg.MULTI in refSetup.rollArguments:
            index = self.parseBoundedInteger(refSetup.ctx, 1)-1
        else:
            index = 0
        d1 = self.parseBoundedInteger(refSetup.ctx, 2, 10)
        d2 = self.parseBoundedInteger(refSetup.ctx, 2, 10)
        
        if RollArg.SPLIT in refSetup.rollArguments:
            if index in refSetup.rollArguments[RollArg.SPLIT].keys(): # cerco se ho giò splittato questo tiro
                raise GreedyParseError("string_error_already_splitting_X", (index+1,) )

        self.split[index] = (d1, d2)
    def _save_setup(self, currentSetup: RollSetup):
        super()._save_setup(currentSetup)
        if not RollArg.SPLIT in currentSetup.rollArguments:
            currentSetup.rollArguments[RollArg.SPLIT] = {}

        currentSetup.rollArguments[RollArg.SPLIT] = currentSetup.rollArguments[RollArg.SPLIT] | self.split
        self.split = {}

class RollParser:
    def __init__(self, gamesystemid: str, character = None):
        self.rollRollArgumentParsers: dict[tuple[str, ...], RollArgumentParser] = {} #list[RollArgumentParser] = []
        self.nullParser: RollArgumentParser = None
        self.gamesystemid = gamesystemid
        self.character = character
    def generateSetup(self, ctx: SecurityContext) -> RollSetup:
        setup = self.getSetupCls()(ctx, self.gamesystemid)
        for parser in self.rollRollArgumentParsers.values():
            vc = parser.getValidatorClass()
            if vc not in setup.validatorClasses:
                setup.validatorClasses.append(vc)
        return setup
    def getSetupCls(self) -> type[RollSetup]:
        raise NotImplementedError()
    def splitAndParse(self, ctx: SecurityContext, setup: RollSetup, args: list[str], i: int, init_errors: list[Exception]) -> int:
        parse_errors = init_errors
        did_split = False
        for keywords, parser in self.rollRollArgumentParsers.items():
            if parser.has_parameters and len(keywords):
                idx = 0
                while not did_split and idx < len(keywords):
                    cmd = keywords[idx]
                    if args[i].startswith(cmd) and len(cmd) < len(args[i]):
                        mod_args = args[:i] + [cmd, args[i][len(cmd):]] + args[i+1:] # modify the arguments list
                        try:
                            i = parser.parse(ctx, mod_args, i, setup) # attempt parsing again with the split
                            args = mod_args
                            did_split = True
                        except (GreedyParseValidationError, lng.LangSupportErrorGroup) as e2: # why did i originally write a catch only for GreedyParseValidationError?
                            parse_errors.append(e2)
                    idx += 1
                
                if did_split: # this is technically not needed but makes things more readable
                    break

        if not did_split: # F
            raise lng.LangSupportErrorGroup("MultiError", parse_errors)
        
        return i, args
    def parseRoll(self, ctx: SecurityContext, args: list[str]) -> RollSetup:
        setup = self.generateSetup(ctx)
        # fill character if it was passed from outside
        if self.character:
            setup.rollArguments[RollArg.CHARACTER] = self.character

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
            except (GreedyParseValidationError, lng.LangSupportErrorGroup) as e: # if at any point a parse fails, we try to see if the user has not separated an argument from its parameter (diff6, multi3...)
                parse_errors = [GreedyParseError("string_arg_X_in_Y_notclear", (args[parser.cursor-1], prettyHighlightError(args, parser.cursor-1))), GreedyParseValidationError("string_error_notsure_whatroll"), e]
                i, args = self.splitAndParse(ctx, setup, args, i, parse_errors)
                parsed = True

            if not parsed:
                parse_errors = [GreedyParseError("string_arg_X_in_Y_notclear", (args[i], prettyHighlightError(args, i))), GreedyParseValidationError("string_error_notsure_whatroll")]
                i, args = self.splitAndParse(ctx, setup, args, i, parse_errors) 

        return setup

class RollParser_General(RollParser):
    def __init__(self, gamesystemid: str, character=None):
        super().__init__(gamesystemid, character)
        self.rollRollArgumentParsers[DIFF_CMD] = RollArgumentParser_GENERAL_DIFF()
        self.rollRollArgumentParsers[SOMMA_CMD] = RollArgumentParser_KeywordActivateOnly(RollSetupValidator, RollArg.ROLLTYPE, rollTypeVal = RollType.SUM)
        self.rollRollArgumentParsers[(ADD_CMD,)] = RollArgumentParser_DiceExpression(RollSetupValidator_DICE, has_parameters=True, detachEnd=True)
        self.rollRollArgumentParsers[(SUB_CMD,)] = RollArgumentParser_DiceExpression(RollSetupValidator_DICE, has_parameters=True, firstNegative = True, detachEnd=True)
        self.nullParser = RollArgumentParser_DiceExpression(RollSetupValidator_DICE)
    def getSetupCls(self) -> type[RollSetup]:
        return RollSetup_General

class RollParser_STS(RollParser_General):
    def __init__(self, gamesystemid: str, character=None):
        super().__init__(gamesystemid, character)
        self.rollRollArgumentParsers[DIFF_CMD] = RollArgumentParser_STS_DIFF()
        self.rollRollArgumentParsers[MULTI_CMD] = RollArgumentParser_STS_MULTI()
        self.rollRollArgumentParsers[DANNI_CMD] = RollArgumentParser_KeywordActivateOnly(RollSetupValidator, RollArg.ROLLTYPE, rollTypeVal = RollType.DAMAGE)
        self.rollRollArgumentParsers[(ADD_CMD,)] = RollArgumentParser_STS_DiceExpression(RollSetupValidator_STS_DICE, has_parameters=True, detachEnd=True)
        self.rollRollArgumentParsers[(SUB_CMD,)] = RollArgumentParser_STS_DiceExpression(RollSetupValidator_STS_DICE, has_parameters=True, firstNegative = True, detachEnd=True)
        self.rollRollArgumentParsers[PENALITA_CMD] = RollArgumentParser_KeywordActivateOnly(RollSetupValidator, RollArg.PENALTY)
        self.rollRollArgumentParsers[NOPENALITA_CMD] = RollArgumentParser_KeywordActivateOnly(RollSetupValidator, RollArg.PENALTY, rollArgVal=False)
        self.rollRollArgumentParsers[PERMANENTE_CMD] = RollArgumentParser_KeywordActivateOnly(RollSetupValidator, RollArg.PERMANENT)
        self.rollRollArgumentParsers[TEMPORARY_CMD] = RollArgumentParser_KeywordActivateOnly(RollSetupValidator, RollArg.PERMANENT, rollArgVal=False)
        self.rollRollArgumentParsers[STATISTICS_CMD] = RollArgumentParser_KeywordActivateOnly(RollSetupValidator, RollArg.STATS)
        self.rollRollArgumentParsers[MINSUCC_CMD] = RollArgumentParser_STS_MINSUCC()
        self.rollRollArgumentParsers[INIZIATIVA_CMD] = RollArgumentParser_STS_Initiative()
        self.rollRollArgumentParsers[RIFLESSI_CMD] = RollArgumentParser_STS_Reflexes()
        self.rollRollArgumentParsers[SOAK_CMD] = RollArgumentParser_STS_Soak()
        self.nullParser = RollArgumentParser_STS_DiceExpression(RollSetupValidator_STS_DICE)
    def getSetupCls(self):
        return RollSetup_STS

class RollParser_V20HB(RollParser_STS):
    def __init__(self, gamesystemid: str, character=None):
        super().__init__(gamesystemid, character)
        self.rollRollArgumentParsers[SPLIT_CMD] = RollArgumentParser_V20HB_SPLIT()
        self.rollRollArgumentParsers[MULTI_CMD] = RollArgumentParser_STS_MULTI(RollSetupValidator_V20HB_MULTI)
        self.rollRollArgumentParsers[RIFLESSI_CMD] = RollArgumentParser_V20HB_Reflexes()
        self.rollRollArgumentParsers[PROGRESSI_CMD] = RollArgumentParser_KeywordActivateOnly(RollSetupValidator, RollArg.ROLLTYPE, rollTypeVal = RollType.PROGRESS)
    def getSetupCls(self):
        return RollSetup_V20HB

class RollParser_V20VANILLA(RollParser_STS):
    def __init__(self, gamesystemid: str, character=None):
        super().__init__(gamesystemid, character)
    def getSetupCls(self):
        return RollSetup_V20VANILLA

class RollParser_DND5E(RollParser_General):
    def __init__(self, gamesystemid: str, character=None):
        super().__init__(gamesystemid, character)
    #def getSetupCls(self):
    #    return RollSetup_STS ?

RollSystemMappings: dict[int, type[RollParser]] = {
    GameSystems.GENERAL: RollParser_General,
    GameSystems.STORYTELLER_SYSTEM: RollParser_STS,
    GameSystems.V20_VTM_HOMEBREW_00: RollParser_V20HB,
    GameSystems.V20_VTM_VANILLA: RollParser_V20VANILLA
    #GameSystems.DND_5E: RollParser_DND5E,
}

def getParser(gamesystem: int):
    """ Gets a roll parser from a GameSystem enum """
    try:
        return RollSystemMappings[gamesystem]
    except KeyError:
        raise GreedyGamesystemError('string_error_gamesystem_missing_mapping', (getGamesystemId(gamesystem),))

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

class PCActionResultRollData(PCActionResult):
    def __init__(self, data: RollData) -> None:
        super().__init__()
        self.data = data

class PCAction:
    def __init__(self, ctx: SecurityContext, character) -> None:
        self.character = character
        self.ctx = ctx
        self.expectedParameterNumbers: tuple[int] = () # remember, for  TraitActions this means parameters beyond the OPERATION, while for actions it is anything beyond the action code
    def doHandle(self, *args):
        return [PCActionResultText(self.ctx.getLanguageProvider().get(self.ctx.getLID(), "string_error_notimplemented"))]
    def handle(self, *args: tuple[str]) -> list[PCActionResult]:
        self.checkParameterNumber(args)
        return self.doHandle(*args)
    def checkParameterNumber(self, args: list[tuple]):
        if len(self.expectedParameterNumbers) > 0 and not (len(args) in self.expectedParameterNumbers):
            raise GreedyTraitOperationError("string_invalid_number_of_parameters")
    def db_setCurvalue(self, new_val: int, trait):
        dbm = self.ctx.getDBManager()
        transaction = dbm.db.transaction()

        try:
            u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=self.character['id']), cur_value = new_val)
            if u == 1:
                dbm.log(self.ctx.getUserId(), self.character['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_val, trait['cur_value'], self.ctx.getMessageContents())
            elif (u > 1 or (u == 0 and trait['cur_value'] != new_val)):
                raise GreedyTraitOperationError('string_error_database_unexpected_update_rowcount', (u,))
        except:
            transaction.rollback()
            raise
        else:
            transaction.commit()

        return dbm.getTrait_LangSafe(self.character['id'], trait['id'], self.ctx.getLID())
    def db_setTextValue(self, new_value: str, trait):
        dbm = self.ctx.getDBManager()
        transaction = dbm.db.transaction()

        try:
            u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=self.character['id']), text_value = new_value)
            if u == 1:
                dbm.log(self.ctx.getUserId(), self.character['id'], trait['trait'], ghostDB.LogType.TEXT_VALUE, new_value, trait['text_value'], self.ctx.getMessageContents())
            elif (u > 1 or (u == 0 and trait['text_value'] != new_value)):
                raise GreedyTraitOperationError('string_error_database_unexpected_update_rowcount', (u,))
        except:
            transaction.rollback()
            raise
        else:
            transaction.commit()
            
        return dbm.getTrait_LangSafe(self.character['id'], trait['id'], self.ctx.getLID())

class PCTraitAction(PCAction):
    def  __init__(self, ctx: SecurityContext, character, trait) -> None:
        super().__init__(ctx, character)
        self.trait = trait
    def doHandle(self, *args: list[str]) -> list[PCActionResult]:
        ttype = int(self.trait['trackertype'])
        if ttype == TrackerType.NORMAL:
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
    def newValue(self, args: list[str]):
        raise NotImplementedError()
    def checkSystemBounds(self, args: list[str]):
        new_val = self.newValue(args)
        max_val = int(self.ctx.getAppConfig()[SECTION_GAME][SETTING_MAX_TRAITVALUE])
        if new_val < 0:
            raise GreedyTraitOperationError("string_error_not_enough_X", (self.trait['traitName'].lower(),))
        if new_val > max_val:
            raise GreedyTraitOperationError("string_error_exceeded_trait_maxvalue", (new_val, self.trait['traitName'].lower(), max_val))
    def checkUpperBound(self, args: list[str]):
        new_val = self.newValue(args)
        max_val = self.trait['max_value']
        if new_val > max_val:
            raise GreedyTraitOperationError("string_error_exceeded_trait_maxvalue", (new_val, self.trait['traitName'].lower(), max_val))
    def _handleOperation_CAPPED(self, *args: list[str]) -> list[PCActionResult]:
        self.checkSystemBounds(args)
        self.checkUpperBound(args)
        return super()._handleOperation_CAPPED(*args)
    def _handleOperation_NORMAL(self, *args: list[str]) -> list[PCActionResult]:
        self.checkSystemBounds(args)
        return super()._handleOperation_NORMAL(*args)
    def _handleOperation_HEALTH(self, *args: list[str]) -> list[PCActionResult]:
        self.checkSystemBounds(args)
        new_val = self.newValue(args)
        new_health = validateHealthSTS(self.trait['text_value'], new_val, self.doImmediatelyConvertBashingToLethal())
        self.trait = self.db_setCurvalue(new_val, self.trait)
        self.trait = self.db_setTextValue(new_health, self.trait)
        return [PCActionResultTrait(self.trait)] 
    def _handleOperation_UNCAPPED(self, *args: list[str]) -> list[PCActionResult]:
        self.checkSystemBounds(args)
        return super()._handleOperation_UNCAPPED(*args)   
    def _handleOperation_Base(self, *args: list[str]) -> list[PCActionResult]:
        new_val = self.newValue(args)
        self.trait = self.db_setCurvalue(new_val, self.trait)
        return [PCActionResultTrait(self.trait)]

class PCTraitAction_STS_RESET(PCTraitAction_STS_ModifyCurValue):
    def __init__(self, ctx: SecurityContext, character, trait) -> None:
        super().__init__(ctx, character, trait)
        self.expectedParameterNumbers = (0,)
    def newValue(self, args: list[str]):
        return self.trait['max_value'] if (int(self.trait['trackertype']) != TrackerType.UNCAPPED) else 0

class PCTraitAction_STS_EQ(PCTraitAction_STS_ModifyCurValue):
    def __init__(self, ctx: SecurityContext, character, trait) -> None:
        super().__init__(ctx, character, trait)
        self.expectedParameterNumbers = (1,)
    def newValue(self, args: list[str]):
        return InputValidator(self.ctx).validateInteger(args[0])

class PCTraitAction_STS_ADD(PCTraitAction_STS_ModifyCurValue):
    def __init__(self, ctx: SecurityContext, character, trait) -> None:
        super().__init__(ctx, character, trait)
        self.expectedParameterNumbers = (1,)
    def newValue(self, args: list[str]):
        return self.trait['cur_value'] + InputValidator(self.ctx).validateInteger(args[0])

class PCTraitAction_STS_SUB(PCTraitAction_STS_ModifyCurValue):
    def __init__(self, ctx: SecurityContext, character, trait) -> None:
        super().__init__(ctx, character, trait)
        self.expectedParameterNumbers = (1,)
    def newValue(self, args: list[str]):
        return self.trait['cur_value'] - InputValidator(self.ctx).validateInteger(args[0])

class PCActionDamage_STS(PCAction):
    def __init__(self, ctx: SecurityContext, character) -> None:
        super().__init__(ctx, character)
        self.trait = self.ctx.getDBManager().getTrait_LangSafe(self.character['id'], 'salute', self.ctx.getLID())
        self.expectedParameterNumbers = (0, 1, 2)
    def checkParameterNumber(self, args: list[tuple]):
        super().checkParameterNumber(args)
        if len(args) == 1 and not args[0] in OPCODES_RESET:
            raise GreedyTraitOperationError("string_invalid_number_of_parameters")
    def doImmediatelyConvertBashingToLethal(self) -> bool:
        return False
    def canUnpackLethalToBashing(self) -> bool:
        return False
    def doHandle(self, *args: tuple[str]) -> list[PCActionResult]:
        if len(args) == 0: # we're nice and show the health trait if no argument is passed
            return PCTraitAction_ViewTrait(self.ctx, self.character, self.trait).handle()

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
                    break
                
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
                        break

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
    def __init__(self, ctx: SecurityContext, game_system: int, character, can_edit: bool) -> None:
        self.ctx = ctx
        self.character = character
        self.canEditCharacter = can_edit
        self.actions: dict[tuple[str], type[PCAction]] = {}
        self.traitOps: dict[tuple[str], type[PCTraitAction]] = {}
        self.viewTraitAction: type[PCTraitAction] = None
        self.nullAction: type[PCAction] = None
        self.gamesystem =  game_system
    def getGameSystem(self) -> int:
        #return NotImplementedError(f'Abstract {self.__class__.__name__}')
        return self.gamesystem
    def getRollParserCls(self):
        return getParser(self.getGameSystem())
    def handle(self, args, macro = False) -> list[PCActionResult]:
        if len(args) == 0:
            action = self.nullAction(self.ctx, self.character)
            return action.handle()
        
        args = detach_args(args)
        whatstr = args[0]
        
        # ACTIONS

        for k, v in self.actions.items():
            if whatstr in k:
                action = v(self.ctx, self.character)
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
            return self.viewTraitAction(self.ctx, self.character, trait).handle()

        if not self.canEditCharacter:
            raise GreedyOperationError("string_error_cannot_edit_character")

        traitOpstr = args[1]

        for k, v in self.traitOps.items():
            if traitOpstr in k:
                action = v(self.ctx, self.character, trait)
                return action.handle(*args[2:])
        raise GreedyOperationError("string_error_unsupported_operation", (traitOpstr,))
    def handle_macro(self, macro_text: str, args: list[str]) -> list[PCActionResult]:
        macro_commands = list(map(lambda x: x.strip(), macro_text.split("\n")))
        results: list[PCActionResult] = []
        for cmd in macro_commands:
            silent = 0
            if cmd.startswith(SILENT_WITHERROR_CMD_PREFIX_MACRO):
                silent = 1
                cmd = cmd[len(SILENT_WITHERROR_CMD_PREFIX_MACRO):]
            if cmd.startswith(SILENT_NOERROR_CMD_PREFIX_MACRO):
                silent = 2
                cmd = cmd[len(SILENT_NOERROR_CMD_PREFIX_MACRO):]
            if cmd != '':
                cmd_split = [y for y in cmd.split(" ") if y != ''] 
                base_cmd = cmd_split[0]
                try:
                    result = None
                    if base_cmd == "me":
                        result = self.handle(cmd_split[1:], True)
                    elif base_cmd == "roll": # TODO
                        parser = self.getRollParserCls()(getGamesystemId(self.getGameSystem()),self.character)
                        setup = parser.parseRoll(self.ctx, cmd_split[1:])
                        setup.validate()
                        rd = setup.roll()
                        result = [PCActionResultRollData(rd)]
                    elif base_cmd in ["echo", "say", "print"]:
                        result = [PCActionResultText(cmd[len(base_cmd)+1:])]
                    else:
                        #TODO check for character ID? remember that if we do, permissions need to be checked for the character
                        raise GreedyOperationError("string_error_unsupported_operation", (base_cmd,))
                        
                    if silent == 0:
                        results.extend(result)
                except (lng.LangSupportException, lng.LangSupportErrorGroup) as e:
                    if silent != 2:
                        results.append(PCActionResultText(self.ctx.getLanguageProvider().formatException(self.ctx.getLID(), e)))
                
        return results

class PCActionHandler_STS(PCActionHandler):
    def __init__(self, ctx: SecurityContext, game_system: int, character, can_edit: bool) -> None:
        super().__init__(ctx, game_system, character, can_edit)
        self.traitOps[OPCODES_ADD] = PCTraitAction_STS_ADD
        self.traitOps[OPCODES_EQ] = PCTraitAction_STS_EQ
        self.traitOps[OPCODES_RESET] = PCTraitAction_STS_RESET
        self.traitOps[OPCODES_SUB] = PCTraitAction_STS_SUB
        self.actions[ACTIONS_DAMAGE] = PCActionDamage_STS
        self.viewTraitAction = PCTraitAction_ViewTrait


class PCActionHandler_V20HB(PCActionHandler_STS):
    def __init__(self, ctx: SecurityContext, game_system: int, character, can_edit: bool) -> None:
        super().__init__(ctx, game_system, character, can_edit)
        self.actions[ACTIONS_DAMAGE] = PCActionDamage_V20HB

ActionHandlerMappings: dict[int, type[PCActionHandler]] = {
    #GameSystems.GENERAL: PCActionHandler_STS,
    GameSystems.STORYTELLER_SYSTEM: PCActionHandler_STS,
    GameSystems.V20_VTM_HOMEBREW_00: PCActionHandler_V20HB,
    GameSystems.V20_VTM_VANILLA: PCActionHandler_STS
    #GameSystems.DND_5E: RollParser_DND5E,
}

def getHandler(gamesystem: int):
    """ Gets an Action Handler class from a GameSystem enum """
    try:
        return ActionHandlerMappings[gamesystem]
    except KeyError:
        raise GreedyGamesystemError('string_error_gamesystem_missing_mapping', (getGamesystemId(gamesystem),))
    
def buildHandler(ctx: SecurityContext, game_system: int, character, can_edit: bool):
    """ Builds an Action Handler object from a GameSystem enum """
    handlerCls = getHandler(game_system)
    return handlerCls(ctx,  game_system, character, can_edit)