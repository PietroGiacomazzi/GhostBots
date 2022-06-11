
from typing import Callable
import urllib
from discord.ext import commands

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs
from greedy_components import greedyConverters as gc

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB

FormatterType = Callable[[object, str, lng.LanguageStringProvider], str]

damage_types = ["a", "l", "c"]
reset_aliases = ["reset"]

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
<Operazione>: +n / -n / =n / reset
    (se <Operazione> è assente viene invece visualizzato il valore corrente)

- Richiede sessione attiva nel canale per capire di che personaggio si sta parlando
- Basato sul valore corrente del tratto (potenziamenti temporanei, risorse spendibili...)
- Per modificare il valore "vero" di un tratto, vedi .pgmod
"""
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

def defaultTraitFormatter(trait, lid: str, lp: lng.LanguageStringProvider) -> str:
    return f"Oh no! devo usare il formatter di default!\n{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}/{trait['pimp_max']}, text: {trait['text_value']}"

def prettyDotTrait(trait, lid: str, lp: lng.LanguageStringProvider) -> str:
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

def prettyHealth(trait , lid: str, lp: lng.LanguageStringProvider, levels_list: list = utils.hurt_levels_vampire) -> str:
    penalty, parsed = utils.parseHealth(trait, levels_list)
    prettytext = f'{trait["traitName"]}:'
    for line in parsed:
        prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], line)))
    return lp.get(lid, penalty[1]) +"\n"+ prettytext

#def prettyFDV(trait, lid: str, lp: lng.LanguageStringProvider) -> str:
#    return defaultTraitFormatter(trait, lid, lp)

def prettyMaxPointTracker(trait, lid: str, lp: lng.LanguageStringProvider, emojis = [":black_circle:", ":white_circle:"], separator = "") -> str:
    pretty = f"{trait['traitName']}: {trait['cur_value']}/{trait['max_value']}\n"
    pretty += separator.join([emojis[0]]*trait['cur_value'])
    pretty += separator
    pretty += separator.join([emojis[1]]*(trait['max_value']-trait['cur_value']))
    return pretty

def prettyPointAccumulator(trait, lid: str, lp: lng.LanguageStringProvider) -> str:
    return f"{trait['traitName']}: {trait['cur_value']}"

def prettyTextTrait(trait, lid: str, lp: lng.LanguageStringProvider) -> str:
    return f"{trait['traitName']}: {trait['text_value']}"

def prettyGeneration(trait, lid: str, lp: lng.LanguageStringProvider) -> str:
    return f"{13 - trait['cur_value']}a generazione\n{prettyDotTrait(trait, lid, lp)}"

def getTraitFormatter(trait: object) -> FormatterType:
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
            return lambda x, y, z: prettyMaxPointTracker(x, y, z, blood_emojis)
        else:
            return lambda x, y, z: prettyMaxPointTracker(x, y, z, will_emojis, " ")
    elif trait['trackertype']==2:
        return prettyHealth
    elif trait['trackertype']==3:
        return prettyPointAccumulator
    else:
        return defaultTraitFormatter

       
class GreedyGhostCog_PCmgmt(gb.GreedyGhostCog): 

    def formatTrait(self, ctx: commands.Context, formatter: FormatterType, trait) -> str:
        return formatter(trait, self.bot.getLID(ctx.message.author.id), self.bot.languageProvider)

    async def pc_interact(self, ctx: commands.Context, pc: object, can_edit: bool, *args_tuple) -> str:
        lid = self.bot.getLID(ctx.message.author.id)

        args = list(args_tuple)

        response = ''
        if len(args) == 0:
            parsed = list(urllib.parse.urlparse(self.bot.config['Website']['website_url'])) # load website url
            parsed[4] = urllib.parse.urlencode({'character': pc['id']}) # fill query
            unparsed = urllib.parse.urlunparse(tuple(parsed)) # recreate url
            return f"Personaggio: {pc['fullname']}\nScheda: {unparsed}"
        
        # detach stuff like ["exp+1"] to ["exp", "+1"]" or ["exp-", "1"] to ["exp", "-", "1"] in args
        for op in ["+", "-", "="]:
            idx = args[0].find(op)
            if idx > 0:
                args = [args[0][:idx]] + [args[0][idx:]] + args[1:]
                break

        trait_id = args[0].lower()
        if len(args) == 1:
            trait = self.bot.dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
            prettyFormatter = getTraitFormatter(trait)
            return self.formatTrait(ctx, prettyFormatter, trait)# prettyFormatter(trait, lid)

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

        trait = self.bot.dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
        #trait = dbm.getTrait(pc['id'], trait_id)
        prettyFormatter = getTraitFormatter(trait)
        if trait['pimp_max']==0 and trait['trackertype']==0:
            raise gb.BotException(f"Non puoi modificare il valore corrente di {trait['traitName']}")
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
                    raise gb.BotException(f"Tracker {trait['trackertype']} non supportato")
            elif operazione == "=":
                n = int(param[1:]) - trait['cur_value'] # tricks
            else:
                n = int(param)
            new_val = trait['cur_value'] + n
            max_val = max(trait['max_value'], trait['pimp_max']) 
            if new_val<0:
                raise gb.BotException(f'Non hai abbastanza {trait["traitName"].lower()}!')
            elif new_val > max_val and trait['trackertype'] != 3:
                raise gb.BotException(f"Non puoi avere {new_val} {trait['traitName'].lower()}. Valore massimo: {max_val}")
            #
            u = self.bot.dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=pc['id']), cur_value = new_val)
            self.bot.dbm.log(ctx.message.author.id, pc['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_val, trait['cur_value'], ctx.message.content)
            if u == 1:
                trait = self.bot.dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
                return self.formatTrait(ctx, prettyFormatter, trait)#prettyFormatter(trait, lid)
            elif u == 0:
                trait = self.bot.dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
                return self.formatTrait(ctx, prettyFormatter, trait)#prettyFormatter(trait, lid)+'\n(nessuna modifica effettuata)'
            else:
                return f'Qualcosa è andato storto, righe aggiornate:  {u}'

        # salute
        response = ''
        n = param[1:-1] # 1st char is the operation, last char is the damaage type
        if n == '':
            n = 1
        elif n.isdigit():
            n = int(n)
        elif operazione == "=" or operazione == "r":
            pass
        else:
            raise gb.BotException(f'"{n}" non è un parametro valido!')
        dmgtype = param[-1].lower()
        new_health = trait['text_value']
        if (not dmgtype in damage_types) and operazione != "r":
            raise gb.BotException(f'"{dmgtype}" non è un tipo di danno valido')
        if operazione == "r":
            new_health = ""
            
            u = self.bot.dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=pc['id']), text_value = new_health, cur_value = trait['max_value'])
            self.bot.dbm.log(ctx.message.author.id, pc['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_health, trait['text_value'], ctx.message.content)
            if u != 1:
                raise gb.BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
            trait = self.bot.dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
            response = self.formatTrait(ctx, prettyFormatter, trait)#prettyFormatter(trait, lid)        
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
                                trait['cur_value'] = trait['max_value']
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
            
            u = self.bot.dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=pc['id']), text_value = new_health, cur_value = trait['cur_value'])
            self.bot.dbm.log(ctx.message.author.id, pc['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_health, trait['text_value'], ctx.message.content)
            if u != 1 and not rip:
                raise gb.BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
            trait = self.bot.dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
            response = self.formatTrait(ctx, prettyFormatter, trait)#prettyFormatter(trait, lid)
            if rip:
                response += "\n\n RIP"
        elif operazione == "-":
            if dmgtype == "a":
                if new_health.count(dmgtype) < n:
                    raise gb.BotException("Non hai tutti quei danni aggravati")
                else:
                    new_health = new_health[n:]
            elif dmgtype == "l":
                if new_health.count(dmgtype) < n:
                    raise gb.BotException("Non hai tutti quei danni letali")
                else:
                    fl = new_health.find(dmgtype)
                    new_health = new_health[:fl]+new_health[fl+n:]
            else: # dio can
                if ( (int(trait['cur_value']) == 0) + new_health.count(dmgtype)+new_health.count("l")*2) < n:
                    raise gb.BotException("Non hai tutti quei danni contundenti")
                for i in range(n):
                    if trait['cur_value'] == 0:
                        trait['cur_value'] = trait['max_value'] # togli il mezzo aggravato
                    else:
                        if new_health[-1] == 'c':
                            new_health = new_health[:-1]
                        elif new_health[-1] == 'l':
                            new_health = new_health[:-1]+'c'
                        else:
                            raise gb.BotException("Non hai tutti quei danni contundenti")# non dovrebbe mai succedere
            u = self.bot.dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=pc['id']), text_value = new_health, cur_value = trait['cur_value'])
            self.bot.dbm.log(ctx.message.author.id, pc['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_health, trait['text_value'], ctx.message.content)
            if u != 1:
                raise gb.BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
            trait = self.bot.dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
            response = self.formatTrait(ctx, prettyFormatter, trait)#prettyFormatter(trait, lid)
        else: # =
            full = param[1:]
            counts = list(map(lambda x: full.count(x), damage_types))
            if sum(counts) !=  len(full):
                raise gb.BotException(f'"{full}" non è un parametro valido!')
            new_health = "".join(list(map(lambda x: x[0]*x[1], zip(damage_types, counts)))) # siamo generosi e riordiniamo l'input
            
            u = self.bot.dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=pc['id']), text_value = new_health, cur_value = 1)
            self.bot.dbm.log(ctx.message.author.id, pc['id'], trait['trait'], ghostDB.LogType.CUR_VALUE, new_health, trait['text_value'], ctx.message.content)
            if u != 1:
                raise gb.BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
            trait = self.bot.dbm.getTrait_LangSafe(pc['id'], trait_id, lid)
            response = self.formatTrait(ctx, prettyFormatter, trait)#prettyFormatter(trait, lid)

        return response

    @commands.command(name = 'me', brief='Permette ai giocatori di interagire col proprio personaggio durante le sessioni' , help = me_description)
    @commands.before_invoke(gs.command_security(gs.IsActiveOnGuild, gs.IsUser))
    async def me(self, ctx: commands.Context, *args):
        pc = self.bot.dbm.getActiveChar(ctx)
        response = await self.pc_interact(ctx, pc, True, *args)
        await self.bot.atSend(ctx, response)

    @commands.command(name = 'pgmanage', brief='Permette ai giocatori di interagire col proprio personaggio durante le sessioni' , help = pgmanage_description)
    @commands.before_invoke(gs.command_security(gs.IsActiveOnGuild, gs.IsUser))
    async def pgmanage(self, ctx: commands.Context, *args):
        if len(args)==0:
            raise gb.BotException('Specifica un pg!')

        charid = args[0].lower()
        isChar, character = self.bot.dbm.validators.getValidateCharacter(charid).validate()
        if not isChar:
            raise gb.BotException(f"Il personaggio {charid} non esiste!")

        # TODO move to security. The reason why we do this here is because "ce" is computed in security checks, but is needed in the command (to be passed to pc_interact)
        # we need a way for security checks to pass on some stuff to the command (maybe with the ctx object?)

        # permission checks
        issuer = str(ctx.message.author.id)
        playerid = character['player']
        
        st, _ = self.bot.dbm.isStorytellerForCharacter(issuer, charid)
        ba, _ = self.bot.dbm.validators.getValidateBotAdmin(issuer).validate()
        co = playerid == issuer  
        ce = st or ba # can edit
        if co and (not ce):
            #1: unlinked
            cl, _ = self.bot.dbm.isCharacterLinked(charid)
            #2 active session
            sa, _ = self.bot.dbm.isSessionActiveForCharacter(charid, ctx.channel.id)
            ce = (not cl) or sa   
        if not (st or ba or co):
            return # non vogliamo che .rossellini faccia cose
            #raise BotException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Admin o Storyteller")

        response = await self.pc_interact(ctx, character, ce, *args[1:])
        await self.bot.atSend(ctx, response)