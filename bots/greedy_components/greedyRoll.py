import random, logging

from greedy_components import greedyBase as gb

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB
import support.security as sec
import support.gamesystems as gms

_log = logging.getLogger(__name__)

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
    def formatRollSummary(self, rolldata: gms.RollData) -> str:
        return ''
    def format(self, item: gms.RollItem) -> str:
        return f'{self.formatHeader(item)}{self.formatRoll(item)}{self.formatTail(item)}'
    def formatHeader(self, item: gms.RollItem):
        return f'{item.tag}: '
    def formatRoll(self, item: gms.RollItem):
        return f'{item.results}'
    def formatTail(self, item: gms.RollItem):
        return ''
    def lstr(self, string_id: str, *formats) -> str:
        return self.langProvider.get(self.langId, string_id, *formats)

class RollFormatter_GENERAL_Difficulty(RollFormatter):
    def formatRoll(self, item: gms.RollItem):
        return f'{self.formatSuccessStatus(item)}: {self.formatHighlightSuccesses(item)}'
    def formatSuccessStatus(self, item: gms.RollItem):
        if item.count_successes == 1:
            return self.lstr('roll_status_generic_1succ')
        else:
            return self.lstr('roll_status_generic_nsucc', item.count_successes)
    def formatHighlightSuccesses(self, item: gms.RollItem):
        return f'[{", ".join(map(lambda x: f"**{x}**" if x >= item.difficulty else str(x), item.results))}]'
    def formatRollSummary(self, rolldata: gms.RollData) -> str:
        count_successes = sum(map(lambda x: x.count_successes, rolldata.data))
        success_str = self.lstr('roll_status_generic_1succ') if count_successes == 1 else self.lstr('roll_status_generic_nsucc', count_successes)
        return f'\n**{self.lstr("string_word_total")}:** {success_str}'

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
        return self.getJoinString().join(results)
    def getJoinString(self) -> str:
        return "\n"
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
        return f'{self.joinResults(results, rolldata, ctx)} {formatter.formatRollSummary(rolldata)}'

class RollOutputter_GENERAL(RollOutputter):
    def __init__(self) -> None:
        super().__init__()
        self.itemFormatters[gms.RollType.DIFFICULTY] = RollFormatter_GENERAL_Difficulty

class RollOutputter_STS(RollOutputter):
    def __init__(self) -> None:
        super().__init__()
        self.itemFormatters[gms.RollType.DAMAGE] = RollFormatter_STS_DMG
        self.itemFormatters[gms.RollType.DIFFICULTY] = RollFormatter_STS_Normal
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
        self.itemFormatters[gms.RollType.DIFFICULTY] = RollFormatter_V20HB_Normal

class RollOutPutter_V20VANILLA(RollOutputter_STS):
    pass

##

class RollHandler:
    def rollParserCls(self) -> type[gms.RollParser]:
        raise NotImplementedError()
    def rollOutputterCls(self) -> type[RollOutputter]:
        raise NotImplementedError()

class RollHandler_General(RollHandler):
    def rollParserCls(self) -> type[gms.RollParser]:
        return gms.RollParser_General
    def rollOutputterCls(self) -> type[RollOutputter]:
        return RollOutputter_GENERAL

class RollHandler_STS(RollHandler):
    def rollParserCls(self) -> type[gms.RollParser]:
        return gms.RollParser_STS
    def rollOutputterCls(self) -> type[RollOutputter]:
        return RollOutputter_STS
    
class RollHandler_V20HB(RollHandler):
    def rollParserCls(self) -> type[gms.RollParser]:
        return gms.RollParser_V20HB
    def rollOutputterCls(self) -> type[RollOutputter]:
        return RollOutputter_V20HB
        
class RollHandler_V20VANILLA(RollHandler):
    def rollParserCls(self) -> type[gms.RollParser]:
        return gms.RollParser_V20VANILLA
    def rollOutputterCls(self) -> type[RollOutputter]:
        return RollOutPutter_V20VANILLA

RollHandlerMappings: dict[int, type[RollHandler]] = {
    gms.GameSystems.GENERAL: RollHandler_General,
    gms.GameSystems.STORYTELLER_SYSTEM: RollHandler_STS,
    gms.GameSystems.V20_VTM_HOMEBREW_00: RollHandler_V20HB,
    gms.GameSystems.V20_VTM_VANILLA: RollHandler_V20HB
    #gms.GameSystems.DND_5E: RollParser_DND5E,
}

def getHandler(gamesystem: int):
    """ Gets a roll handler from a GameSystem enum """
    try:
        return RollHandlerMappings[gamesystem]
    except KeyError:
        raise gms.GreedyGamesystemError('string_error_gamesystem_missing_mapping', (gms.getGamesystemId(gamesystem),))