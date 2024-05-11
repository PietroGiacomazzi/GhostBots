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
    def __init__(self, ctx: sec.SecurityContext, trait):
        self.ctx = ctx
        self.lid = ctx.getLID()
        self.lp = ctx.getLanguageProvider()
        self.config = ctx.getAppConfig()
        self.trait = trait
    def formatTrait(self) -> str:
        raise NotImplementedError(f'Abstract {self.__class__.__name__}')
    def formatAdditionalInfoPre(self) -> str:
        return ''
    def formatAdditionalInfoPost(self) -> str:
        return ''
    def format(self):
        pretty = self.formatTrait()
        ai_pre = self.formatAdditionalInfoPre()
        if ai_pre != '':
            pretty = ai_pre + '\n'+ pretty
        ai_post = self.formatAdditionalInfoPost()
        if ai_post != '':
            pretty = pretty + '\n' + ai_post
        return pretty

class DefaultTraitFormatter(TraitFormatter):
    def formatTrait(self) -> str:
        return f"Oh no! devo usare il formatter di default!\n{self.trait['traitName']}: {self.trait['cur_value']}/{self.trait['max_value']}, text: {self.trait['text_value']}"

class DotTraitFormatter(TraitFormatter):
    def formatTrait(self) -> str:
        pretty = f"{self.trait['traitName']}: {self.trait['cur_value']}/{self.trait['max_value']}\n"
        if max(self.trait['cur_value'], self.trait['max_value'], self.trait['dotvisualmax']) > int(self.config[cfg.SECTION_BOTOPTIONS][cfg.SETTING_MAX_TRAIT_OUTPUT_SIZE]):
            return pretty
        pretty += ":red_circle:"*min(self.trait['cur_value'], self.trait['max_value'])
        if self.trait['cur_value']<self.trait['max_value']:
            pretty += ":orange_circle:"*(self.trait['max_value']-self.trait['cur_value'])
        if self.trait['cur_value']>self.trait['max_value']:
            pretty += ":green_circle:"*(self.trait['cur_value']-self.trait['max_value'])
        max_dots = self.trait['dotvisualmax']
        if self.trait['cur_value'] < max_dots:
            pretty += ":white_circle:"*(max_dots-max(self.trait['max_value'], self.trait['cur_value']))
        return pretty

class HealthTraitFormatter(TraitFormatter):
    def __init__(self, ctx: sec.SecurityContext, trait, levels_list: list):
        super().__init__(ctx, trait)
        self.levelList = levels_list
        self.penalty, self.parsed = utils.parseHealth(self.trait, levels_list)
    def formatTrait(self) -> str:
        prettytext = f'{self.trait["traitName"]}:'
        if self.trait['cur_value'] > int(self.config[cfg.SECTION_BOTOPTIONS][cfg.SETTING_MAX_TRAIT_OUTPUT_SIZE]):
            prettytext += str(self.trait['cur_value']) + '\n'
            prettytext += ', '.join(list( map(lambda x: f'{self.trait["text_value"].count(x[0])} {self.lp.get(self.lid, x[1])}', zip(gms.DAMAGE_TYPES, ["string_aggravated_dmg_plural", "string_lethal_dmg_plural", "string_bashing_dmg_plural"]))))
        else:
            try:
                for line in self.parsed:
                    prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], line)))
            except KeyError:
                raise gb.GreedyCommandError("string_error_invalid_health_expr", (self.trait['text_value'],))
        return prettytext
    def formatAdditionalInfoPre(self) -> str:
        return self.lp.get(self.lid, self.penalty[1])

class VampireHealthFormatter(HealthTraitFormatter):
    def __init__(self, ctx: sec.SecurityContext, trait):
        super().__init__(ctx, trait, utils.hurt_levels_vampire)

class MaxPointTraitFormatter(TraitFormatter):
    def __init__(self, ctx: sec.SecurityContext, trait, emojis = [":black_circle:", ":white_circle:"], separator = ""):
        super().__init__(ctx, trait)
        self.separator = separator
        self.emojis = emojis
    def formatTrait(self) -> str:
        pretty = f"{self.trait['traitName']}: {self.trait['cur_value']}/{self.trait['max_value']}\n"
        if max(self.trait['cur_value'], self.trait['max_value'], self.trait['dotvisualmax']) > int(self.config[cfg.SECTION_BOTOPTIONS][cfg.SETTING_MAX_TRAIT_OUTPUT_SIZE]):
            return pretty
        pretty += self.separator.join([self.emojis[0]]*self.trait['cur_value'])
        pretty += self.separator
        pretty += self.separator.join([self.emojis[1]]*(self.trait['max_value']-self.trait['cur_value']))
        return pretty

class BloodpointTraitFormatter(MaxPointTraitFormatter):
    def __init__(self, ctx: sec.SecurityContext, trait):
        super().__init__(ctx, trait, blood_emojis, "")
    def formatAdditionalInfoPost(self) -> str:
        try:
            generation_trait = self.ctx.getDBManager().getTrait_LangSafe(self.trait[ghostDB.FIELDNAME_CHARACTERTRAIT_PLAYERCHAR], 'generazione', self.lid)
            gl = gms.getGenerationalLimit(generation_trait[ghostDB.FIELDNAME_TRAIT_CUR_VALUE])
            return self.lp.get(self.lid, "web_generational_blood_limit", gl if gl is not None else '???')
        except ghostDB.DBException:
            return super().formatAdditionalInfoPost()

class WillpowerTraitFormatter(MaxPointTraitFormatter):
    def __init__(self, ctx: sec.SecurityContext, trait):
        super().__init__(ctx, trait, will_emojis, " ")

class PointAccumulatorTraitFormatter(TraitFormatter):
    def formatTrait(self) -> str:
        return f"{self.trait['traitName']}: {self.trait['cur_value']}"

class TextTraitFormatter(TraitFormatter):
    def formatTrait(self) -> str:
        return f"{self.trait['traitName']}: {self.trait['text_value']}"

class GenerationTraitFormatter(DotTraitFormatter):
    def formatAdditionalInfoPre(self) -> str:
        subtract = self.trait[ghostDB.FIELDNAME_TRAIT_CUR_VALUE]
        for highgen_flaw, sub in zip(['14gen', '15gen'], [-1, -2]):
            try:
                _ = self.ctx.getDBManager().getTrait_LangSafe(self.trait[ghostDB.FIELDNAME_CHARACTERTRAIT_PLAYERCHAR], highgen_flaw, self.lid)
                if subtract > 0:
                    return self.lp.get(self.lid, 'web_string_calc_generation', '?')
                subtract = sub
            except ghostDB.DBException:
                pass
        gen_number = 13-subtract
        if gen_number < 1:
            gen_number = '?'
        return self.lp.get(self.lid, 'web_string_calc_generation', gen_number)
    def formatAdditionalInfoPost(self) -> str:
        gl = gms.getGenerationalLimit(self.trait[ghostDB.FIELDNAME_TRAIT_CUR_VALUE])
        return self.lp.get(self.lid, "web_generational_blood_limit", gl if gl is not None else '???')

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
            return self.getTraitFormatterClass(item.trait)(self.ctx, item.trait).format()
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