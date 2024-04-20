from configparser import ConfigParser
from discord.ext import commands
import urllib, logging

from greedy_components import greedyBase as gb
from greedy_components import greedyConverters as gc
from greedy_components import greedySecurity as gs
from greedy_components  import greedyRoll as gr

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB
import support.security as sec
import support.gamesystems as gms
import support.config as cfg

_log = logging.getLogger(__name__)

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
    def __init__(self, lid: str, lp: lng.LanguageStringProvider, cfg: ConfigParser):
        self.lid = lid
        self.lp = lp
        self.config = cfg
    def format(self, trait) -> str:
        raise NotImplementedError(f'Abstract {self.__class__.__name__}')

class DefaultTraitFormatter(TraitFormatter):
    def format(self, trait) -> str:
        return f"Oh no! devo usare il formatter di default!\n{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}, text: {trait['text_value']}"

class DotTraitFormatter(TraitFormatter):
    def format(self, trait) -> str:
        pretty = f"{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}\n"
        if max(trait['cur_value'], trait['max_value'], trait['dotvisualmax']) > int(self.config[cfg.SECTION_BOTOPTIONS][cfg.SETTING_MAX_TRAIT_OUTPUT_SIZE]):
            return pretty
        pretty += ":red_circle:"*min(trait['cur_value'], trait['max_value'])
        if trait['cur_value']<trait['max_value']:
            pretty += ":orange_circle:"*(trait['max_value']-trait['cur_value'])
        if trait['cur_value']>trait['max_value']:
            pretty += ":green_circle:"*(trait['cur_value']-trait['max_value'])
        max_dots = trait['dotvisualmax']
        if trait['cur_value'] < max_dots:
            pretty += ":white_circle:"*(max_dots-max(trait['max_value'], trait['cur_value']))
        return pretty

class HealthTraitFormatter(TraitFormatter):
    def __init__(self, lid: str, lp: lng.LanguageStringProvider, cfg: ConfigParser, levels_list: list):
        super().__init__(lid, lp, cfg)
        self.levelList = levels_list
    def format(self, trait) -> str:
        penalty, parsed = utils.parseHealth(trait, self.levelList)
        prettytext = f'{trait["traitName"]}:'
        if trait['cur_value'] > int(self.config[cfg.SECTION_BOTOPTIONS][cfg.SETTING_MAX_TRAIT_OUTPUT_SIZE]):
            prettytext += str(trait['cur_value']) + '\n'
            prettytext += ', '.join(list( map(lambda x: f'{trait["text_value"].count(x[0])} {self.lp.get(self.lid, x[1])}', zip(gms.DAMAGE_TYPES, ["string_aggravated_dmg_plural", "string_lethal_dmg_plural", "string_bashing_dmg_plural"]))))
        else:
            try:
                for line in parsed:
                    prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], line)))
            except KeyError:
                raise gb.GreedyCommandError("string_error_invalid_health_expr", (trait['text_value'],))
        return self.lp.get(self.lid, penalty[1]) +"\n"+ prettytext

class VampireHealthFormatter(HealthTraitFormatter):
    def __init__(self, lid: str, lp: lng.LanguageStringProvider, cfg: ConfigParser):
        super().__init__(lid, lp, cfg, utils.hurt_levels_vampire)

class MaxPointTraitFormatter(TraitFormatter):
    def __init__(self, lid: str, lp: lng.LanguageStringProvider, cfg: ConfigParser,  emojis = [":black_circle:", ":white_circle:"], separator = ""):
        super().__init__(lid, lp, cfg)
        self.separator = separator
        self.emojis = emojis
    def format(self, trait) -> str:
        pretty = f"{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}\n"
        if max(trait['cur_value'], trait['max_value'], trait['dotvisualmax']) > int(self.config[cfg.SECTION_BOTOPTIONS][cfg.SETTING_MAX_TRAIT_OUTPUT_SIZE]):
            return pretty
        pretty += self.separator.join([self.emojis[0]]*trait['cur_value'])
        pretty += self.separator
        pretty += self.separator.join([self.emojis[1]]*(trait['max_value']-trait['cur_value']))
        return pretty

class BloodpointTraitFormatter(MaxPointTraitFormatter):
    def __init__(self, lid: str, lp: lng.LanguageStringProvider, cfg: ConfigParser):
        super().__init__(lid, lp, cfg, blood_emojis, "")

class WillpowerTraitFormatter(MaxPointTraitFormatter):
    def __init__(self, lid: str, lp: lng.LanguageStringProvider, cfg: ConfigParser):
        super().__init__(lid, lp, cfg, will_emojis, " ")

class PointAccumulatorTraitFormatter(TraitFormatter):
    def format(self, trait) -> str:
        return f"{trait['traitName']}: {trait['cur_value']}"

class TextTraitFormatter(TraitFormatter):
    def format(self, trait) -> str:
        return f"{trait['traitName']}: {trait['text_value']}"

class GenerationTraitFormatter(TraitFormatter):
    def format(self, trait) -> str:
        dtf = DotTraitFormatter(self.lid, self.lp, self.config)
        gen_formatted = dtf.format(trait)
        gen_number = 13 - trait['cur_value']
        return (self.lp.get(self.lid, 'web_string_calc_generation', gen_number) + "\n" if gen_number > 0 else "") + gen_formatted            

# HANDLERS

class PCActionResultOutputter():
    def __init__(self, ctx: sec.SecurityContext) -> None:
        self.ctx = ctx
    def getTraitFormatterClass(self, trait) -> type[TraitFormatter]:
        NotImplementedError(f'Abstract {self.__class__.__name__}')
    def getRollDataFormatterClass(self) -> type[gr.RollOutputter]:
        return gr.RollOutputter_GENERAL
    def outputItem(self, item: gms.PCActionResult):
        if isinstance(item, gms.PCActionResultTrait):
            return self.getTraitFormatterClass(item.trait)(self.ctx.getLID(), self.ctx.getLanguageProvider(), self.ctx.getAppConfig()).format(item.trait)
        elif isinstance(item, gms.PCActionResultText):
            return item.text
        elif isinstance(item, gms.PCActionResultRollData):
            return self.getRollDataFormatterClass()().output(item.data, self.ctx)
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
    def getRollDataFormatterClass(self) -> type[gr.RollOutputter]:
        return gr.RollOutputter_STS

class PCActionResultOutputter_V20HB(PCActionResultOutputter_STS):
    def getRollDataFormatterClass(self) -> type[gr.RollOutputter]:
        return gr.RollOutputter_V20HB
    
class PCActionResultOutputter_V20VANILLA(PCActionResultOutputter_STS):
    def getRollDataFormatterClass(self) -> type[gr.RollOutputter]:
        return gr.RollOutPutter_V20VANILLA

class PCAction_CharacterLink(gms.PCAction):
    def handle(self, *args: tuple[str]) -> list[gms.PCActionResult]:
        parsed = list(urllib.parse.urlparse(self.ctx.getAppConfig()['Website']['website_url'])) # load website url
        parsed[4] = urllib.parse.urlencode({'character': self.character['id']}) # fill query
        unparsed = urllib.parse.urlunparse(tuple(parsed)) # recreate url
        return [gms.PCActionResultText(self.ctx.getLanguageProvider().get(self.ctx.getLID(), "string_msg_charsheet_info", self.character['fullname'], unparsed) )]

ActionResultOutputterMappings: dict[int, type[PCActionResultOutputter]] = {
    #gms.GameSystems.GENERAL: PCActionHandler_STS,
    gms.GameSystems.STORYTELLER_SYSTEM: PCActionResultOutputter_STS,
    gms.GameSystems.V20_VTM_HOMEBREW_00: PCActionResultOutputter_V20HB,
    gms.GameSystems.V20_VTM_VANILLA: PCActionResultOutputter_V20VANILLA
    #gms.GameSystems.DND_5E: RollParser_DND5E,
}

def getOutputter(gamesystem: int, ctx: gb.GreedyContext):
    """ Gets an ActionResultOutputter object from a GameSystem enum """
    try:
        return ActionResultOutputterMappings[gamesystem](ctx)
    except KeyError:
        raise gms.GreedyGamesystemError('string_error_gamesystem_missing_mapping', (gms.getGamesystemId(gamesystem),))

# COG 
class GreedyGhostCog_PCmgmt(gb.GreedyGhostCog): 

    async def pc_interact(self, ctx: gb.GreedyContext, pc: object, can_edit: bool, *args_tuple) -> str:
        gamesystemid = self.bot.dbm.getGameSystemIdByCharacter(pc, self.bot.getGameSystemIdByChannel(ctx.channel.id)) 
        gamesystem = gms.getGamesystem(gamesystemid)
        handler = gms.buildHandler(ctx, gamesystem, pc, can_edit)
        handler.nullAction = PCAction_CharacterLink
        result = handler.handle(args_tuple)
        return getOutputter(gamesystem, ctx).outputList(result)

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
        can_edit, _ = sec.canEditCharacter_BOT(target_character=2)(ctx).checkSecurity(*ctx.args, **ctx.kwargs)
        
        response = await self.pc_interact(ctx, character, can_edit, *args)
        await self.bot.atSend(ctx, response)