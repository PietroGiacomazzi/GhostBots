from discord.ext import commands
import urllib

from greedy_components import greedyBase as gb
from greedy_components import greedyConverters as gc
from greedy_components import greedySecurity as gs

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB
import support.security as sec
import support.gamesystems as gms

healthToEmoji = {
    'c': '<:hl_bashing:815338465368604682>',
    'l': '<:hl_lethal:815338465176715325>',
    'a': '<:hl_aggravated:815338465365458994>',
    #
    ' ': '<:hl_free:815338465348026388>',
    'B': '<:hl_blocked:815338465260077077>'
    }

blood_emojis = [":drop_of_blood:", ":droplet:"]
will_emojis = [":white_square_button:", ":white_large_square:"]

me_description = """.me <NomeTratto> [<Operazione>]

<Nometratto>: Nome del tratto (o somma di tratti)
<Operazione>: +n / -n / =n / reset / ...
    (se <Operazione> è assente viene invece visualizzato il valore corrente)

- Richiede sessione attiva nel canale per capire di che personaggio si sta parlando
- Basato sul valore corrente del tratto (potenziamenti temporanei, risorse spendibili...)
- Per modificare il valore "vero" di un tratto, vedi .pgmod
"""
pgmanage_description = """.pgmanage <nomepg> <NomeTratto> [<Operazione>]

<nomepg>: Nome breve del pg
<Nometratto>: Nome del tratto (o somma di tratti)
<Operazione>: +n / -n / =n / reset / ...
    (se <Operazione> è assente viene invece visualizzato il valore corrente)

- Funziona esattamente come '.me', ma funziona anche fuori sessione (solo per consultare i valori).
- Si può usare in 2 modi:
    1) .<nomepg> [argomenti di .me]
    2) .pgmanage <nomepg> [argomenti di .me]
"""

# TRAIT FORMATTERS

class TraitFormatter:
    def __init__(self, lid: str, lp: lng.LanguageStringProvider):
        self.lid = lid
        self.lp = lp
    def format(self, trait) -> str:
        raise NotImplementedError("u lil shit")

class DefaultTraitFormatter(TraitFormatter):
    def format(self, trait) -> str:
        return f"Oh no! devo usare il formatter di default!\n{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}/{trait['pimp_max']}, text: {trait['text_value']}"

class DotTraitFormatter(TraitFormatter):
    def format(self, trait) -> str:
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

class HealthTraitFormatter(TraitFormatter):
    def __init__(self, lid: str, lp: lng.LanguageStringProvider, levels_list: list):
        super().__init__(lid, lp)
        self.levelList = levels_list
    def format(self, trait) -> str:
        penalty, parsed = utils.parseHealth(trait, self.levelList)
        prettytext = f'{trait["traitName"]}:'
        try:
            for line in parsed:
                prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], line)))
        except KeyError:
            raise gb.GreedyCommandError("string_error_invalid_health_expr", (trait['text_value'],))
        return self.lp.get(self.lid, penalty[1]) +"\n"+ prettytext

class VampireHealthFormatter(HealthTraitFormatter):
    def __init__(self, lid: str, lp: lng.LanguageStringProvider):
        super().__init__(lid, lp, utils.hurt_levels_vampire)

class MaxPointTraitFormatter(TraitFormatter):
    def __init__(self, lid: str, lp: lng.LanguageStringProvider,  emojis = [":black_circle:", ":white_circle:"], separator = ""):
        super().__init__(lid, lp)
        self.separator = separator
        self.emojis = emojis
    def format(self, trait) -> str:
        pretty = f"{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}\n"
        pretty += self.separator.join([self.emojis[0]]*trait['cur_value'])
        pretty += self.separator
        pretty += self.separator.join([self.emojis[1]]*(trait['max_value']-trait['cur_value']))
        return pretty

class BloodpointTraitFormatter(MaxPointTraitFormatter):
    def __init__(self, lid: str, lp: lng.LanguageStringProvider):
        super().__init__(lid, lp, blood_emojis, "")

class WillpowerTraitFormatter(MaxPointTraitFormatter):
    def __init__(self, lid: str, lp: lng.LanguageStringProvider):
        super().__init__(lid, lp, will_emojis, " ")

class PointAccumulatorTraitFormatter(TraitFormatter):
    def format(self, trait) -> str:
        return f"{trait['traitName']}: {trait['cur_value']}"

class TextTraitFormatter(TraitFormatter):
    def format(self, trait) -> str:
        return f"{trait['traitName']}: {trait['text_value']}"

class GenerationTraitFormatter(TraitFormatter):
    def format(self, trait) -> str:
        dtf = DotTraitFormatter(self.lid, self.lp)
        return f"{13 - trait['cur_value']}a generazione\n{dtf.format(trait)}"

# HANDLERS

OPCODES_ADD = ('+',)
OPCODES_SUB = ('-',)
OPCODES_EQ = ('=',)
OPCODES_RESET = ('r', 'reset')

DETACH_SPECIAL = OPCODES_ADD+OPCODES_SUB+OPCODES_EQ

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

class PCActionResultOutputter():
    def __init__(self, ctx: sec.SecurityContext) -> None:
        self.ctx = ctx
    def getTraitFormatterClass(self, trait) -> type[TraitFormatter]:
        raise NotImplementedError()
    def outputItem(self, item: gms.PCActionResult):
        if isinstance(item, gms.PCActionResultTrait):
            return self.getTraitFormatterClass(item.trait)(self.ctx.getLID(), self.ctx.getLanguageProvider()).format(item.trait)
        elif isinstance(item, gms.PCActionResultText):
            return item.text
        raise 
    def outputList(self, item_list: list[gms.PCActionResult]) -> str:
        formatted = []
        for s in item_list:
            formatted.append(self.outputItem(s))
        return  "\n".join(formatted)

class PCActionResultOutputter_STS(PCActionResultOutputter):
    def getTraitFormatterClass(self, trait) -> type[TraitFormatter]:
        # formattatori specifici
        if trait['id'] == 'generazione':
            return GenerationTraitFormatter
        # formattatori generici
        if trait['textbased']:
            return TextTraitFormatter
        elif trait['trackertype']==0:
            return DotTraitFormatter
        elif trait['trackertype']==1:
            if trait['id'] == 'sangue':
                return BloodpointTraitFormatter
            else:
                return WillpowerTraitFormatter
        elif trait['trackertype']==2:
            return VampireHealthFormatter
        elif trait['trackertype']==3:
            return PointAccumulatorTraitFormatter
        else:
            return DefaultTraitFormatter

class PCAction_CharacterLink(gms.PCAction):
    def handle(self, *args: tuple[str]) -> list[gms.PCActionResult]:
        parsed = list(urllib.parse.urlparse(self.ctx.getAppConfig()['Website']['website_url'])) # load website url
        parsed[4] = urllib.parse.urlencode({'character': self.character['id']}) # fill query
        unparsed = urllib.parse.urlunparse(tuple(parsed)) # recreate url
        return [gms.PCActionResultText(self.ctx.getLanguageProvider().get(self.ctx.getLID(), "string_msg_charsheet_info", self.character['fullname'], unparsed) )]

class PCActionHandler:
    def __init__(self, ctx: gb.GreedyContext, character) -> None:
        self.ctx = ctx
        self.character = character
        self.actions: dict[tuple[str], type[gms.PCAction]] = {}
        self.traitOps: dict[tuple[str], type[gms.PCTraitAction]] = {}
        self.viewTraitAction: type[gms.PCTraitAction] = None
        self.nullAction: type[gms.PCAction] = PCAction_CharacterLink
    def handle(self, args) -> list[gms.PCActionResult]:
        if len(args) == 0:
            action = self.nullAction(self.ctx, self.character)
            return action.handle()
        args = detach_args(args)

        whatstr = args[0]

        for k, v in self.actions.items():
            if whatstr in k:
                action = v(self.ctx, self.character)
                return action.handle(*args[1:])

        trait = self.ctx.getDBManager().getTrait_LangSafe(self.character['id'], whatstr, self.ctx.getLID())

        if len(args) == 1: # only trait name
            return self.viewTraitAction(self.ctx, self.character, trait).handle()

        traitOpstr = args[1]

        for k, v in self.traitOps.items():
            if traitOpstr in k:
                action = v(self.ctx, self.character, trait)
                return action.handle(*args[2:])

        raise gb.GreedyCommandError("string_error_unsupported_operation", (traitOpstr,))
    def getOutputter(self) -> PCActionResultOutputter:
        return NotImplementedError()
      
class PCActionHandler_STS(PCActionHandler):
    def __init__(self, ctx: gb.GreedyContext, character) -> None:
        super().__init__(ctx, character)
        self.traitOps[OPCODES_ADD] = gms.PCTraitAction_STS_ADD
        self.traitOps[OPCODES_EQ] = gms.PCTraitAction_STS_EQ
        self.traitOps[OPCODES_RESET] = gms.PCTraitAction_STS_RESET
        self.traitOps[OPCODES_SUB] = gms.PCTraitAction_STS_SUB
        self.viewTraitAction = gms.PCTraitAction_ViewTrait
    def getOutputter(self) -> PCActionResultOutputter:
        return PCActionResultOutputter_STS(self.ctx)

class PCActionHandler_V20HB(PCActionHandler_STS):
    def __init__(self, ctx: gb.GreedyContext, character) -> None:
        super().__init__(ctx, character)
        self.traitOps[OPCODES_ADD] = gms.PCTraitAction_V20HB_ADD
        self.traitOps[OPCODES_SUB] = gms.PCTraitAction_V20HB_SUB

ActionHandlerMappings: dict[int, type[PCActionHandler]] = {
    #gms.GameSystems.GENERAL: PCActionHandler_STS,
    gms.GameSystems.STORYTELLER_SYSTEM: PCActionHandler_STS,
    gms.GameSystems.V20_VTM_HOMEBREW_00: PCActionHandler_V20HB,
    gms.GameSystems.V20_VTM_VANILLA: PCActionHandler_STS
    #gms.GameSystems.DND_5E: RollParser_DND5E,
}

def getHandler(gamesystem: int):
    """ Gets an Action Handler from a GameSystem enum """
    return ActionHandlerMappings[gamesystem]

# COG 
class GreedyGhostCog_PCmgmt(gb.GreedyGhostCog): 

    async def pc_interact(self, ctx: gb.GreedyContext, pc: object, can_edit: bool, *args_tuple) -> str:
        gamesystemid = self.bot.getGameSystemByChannel(ctx.channel.id)
        gamesystem = gms.getGamesystem(gamesystemid)
        handlerClass = getHandler(gamesystem)
        handler = handlerClass(ctx, pc)
        result = handler.handle(args_tuple)
        return handler.getOutputter().outputList(result)

    @commands.command(name = 'me', brief='Permette ai giocatori di interagire col proprio personaggio durante le sessioni' , help = me_description)
    @commands.before_invoke(gs.command_security(gs.basicRegisteredUser))
    async def me(self, ctx: gb.GreedyContext, *args):
        pc = self.bot.dbm.getActiveChar(ctx)
        response = await self.pc_interact(ctx, pc, True, *args)
        await self.bot.atSend(ctx, response)

    @commands.command(name = 'pgmanage', brief='Permette ai giocatori di interagire col proprio personaggio durante le sessioni' , help = pgmanage_description)
    @commands.before_invoke(gs.command_security(sec.OR(sec.IsAdmin, sec.AND( sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser), sec.genCanViewCharacter(target_character=2)))))
    async def pgmanage(self, ctx: gb.GreedyContext, character: gc.CharacterConverter, *args):
        can_edit = False 
        can_edit, _ = sec.genCanEditCharacter(target_character=2)(ctx).checkSecurity(*ctx.args, **ctx.kwargs)
        
        response = await self.pc_interact(ctx, character, can_edit, *args)
        await self.bot.atSend(ctx, response)