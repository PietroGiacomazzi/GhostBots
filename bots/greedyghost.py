#!/usr/bin/env python3

from discord.ext import commands
import random, sys, configparser
import support.vtm_res as vtm_res

if len(sys.argv) == 1:
    print("Specifica un file di configurazione!")

config = configparser.ConfigParser()
config.read(sys.argv[1])

TOKEN = config['Discord']['token']


SOMMA_CMD = ["somma", "s"]
DIFF_CMD = ["diff", "d"]
MULTI_CMD = ["multi", "m"]
DANNI_CMD = ["danni", "dmg"]
PROGRESSI_CMD = ["progressi", "p"]
SPLIT_CMD = ["split"]

NORMALE = 0
SOMMA = 1
DANNI = 2
PROGRESSI = 3

max_dice = 100
max_faces = 100

bot = commands.Bot(['gg', '.'])

die_emoji = {
    2: ":two:",
    3: ":three",
    4: ":four:",
    5: ":five:",
    6: ":six:",
    7: ":seven:",
    8: ":eight:",
    9: ":nine:",
    10: ":keycap_ten:"
    }

def prettyRoll(roll, diff, cancel):
    for i in range(0, len(roll)-cancel):
        die = roll[i]
        if die == 1:
            roll[i] = '**1**'
        elif die >= diff:
            roll[i] = die_emoji[die]
        else:
            roll[i] = str(die)
    for i in range(len(roll)-cancel, len(roll)):
        roll[i] = f"**~~{roll[i]}~~**"
    random.shuffle(roll)
    return "["+", ".join(roll)+"]"

def atSend(ctx, msg):
    return ctx.send(f'{ctx.message.author.mention} '+msg)

#executed once on bot boot
@bot.event
async def on_ready():
    for guild in bot.guilds:
        print(
            f'{bot.user} is connected to the following guild:\n'
            f'{guild.name} (id: {guild.id})'
        )
    #members = '\n - '.join([member.name for member in guild.members])
    #print(f'Guild Members:\n - {members}')
    #await bot.get_channel(int(config['DISCORD_DEBUG_CHANNEL'])).send("bot is online")

@bot.event
async def on_error(event, *args, **kwargs):
    print(f"On_error: {args[0]}")
    #await bot.get_channel(int(config['DISCORD_DEBUG_CHANNEL'])).send(f'Unhandled message: {args[0]}')
    raise

@bot.command(name='coin', help = 'Testa o Croce.')
async def coin(ctx):
    moneta=['Testa' , 'Croce']
    await atSend(ctx, f'{random.choice(moneta)}')

@bot.command(name='roll', help = 'Soon™')
async def roll(ctx, *args):
    #print("roll args:", repr(args))
    try:
        if len(args) == 0:
            raise ValueError("roll cosa diomadonna")
        split = args[0].split("d")
        if len(split) > 2:
            raise ValueError("Troppe 'd' b0ss")
        if len(split) == 1:
            raise ValueError(f'"{split[0]}" cosa')
        if split[0] == "":
            split[0] = "1"
        if not split[0].isdigit():
            raise ValueError(f'"{split[0]}" non è un numero intero')
        if split[1] == "":
            split[1] = "10"
        if not split[1].isdigit():
            raise ValueError(f'"{split[1]}" non è un numero intero')
        n = int(split[0])
        faces = int(split[1])
        if n <= 0:
            raise ValueError(f'{n} non è un numero <= 0')
        if faces <= 0:
            raise ValueError(f'{faces} non è un numero <= 0')
        if n > max_dice:
            raise ValueError(f'{n} dadi sono troppi b0ss')
        if faces > max_faces:
            raise ValueError(f'{faces} facce sono un po\' tante')
        if len(args) == 1: #simple roll
            raw_roll = list(map(lambda x: random.randint(1, faces), range(n)))
            response = repr(raw_roll)
        else:
            diff = None
            multi = None
            split = None
            rolltype = 0 # somma, progressi...
            add = None # extra successi
            # leggo gli argomenti
            i = 1
            while i < len(args):
                if args[i] in SOMMA_CMD:
                    rolltype = SOMMA
                elif args[i] in DIFF_CMD:
                    if diff:
                        raise ValueError(f'eeh deciditi')
                    if len(args) == i+1:
                        raise ValueError(f'diff cosa')
                    if not args[i+1].isdigit():
                        raise ValueError(f'"{args[i+1]}" non è una difficoltà valida')
                    diff = int(args[i+1])
                    if diff > 10 or diff < 2:
                        raise ValueError(f'{args[i+1]} non è una difficoltà valida')
                    i += 1 
                elif args[i] in MULTI_CMD:
                    if multi:
                        raise ValueError(f'eeh deciditi')
                    if len(args) == i+1:
                        raise ValueError(f'multi cosa')
                    if not args[i+1].isdigit():
                        raise ValueError(f'"{args[i+1]}" non è un numero di mosse valido')
                    multi = int(args[i+1])
                    if multi < 2:
                        raise ValueError(f'una multipla deve avere almeno 2 tiri!')
                    if n-multi-(multi-1) <= 0:
                        raise ValueError(f'non hai abbastanza dadi per questo numero di mosse!')
                    i += 1
                elif args[i] in DANNI_CMD:
                    rolltype = DANNI
                elif args[i] in PROGRESSI_CMD:
                    rolltype = PROGRESSI
                elif args[i] in SPLIT_CMD:
                    raise ValueError(f'Non implementato')
                elif args[i].startswith("+"):
                    raise ValueError(f'Non implementato')
                else:
                    raise ValueError(f'coes')
                i += 1
            # decido cosa fare
            if multi:
                if rolltype == NORMALE:
                    response = ""
                    if split:
                        pass 
                    else:
                        if not diff:
                            raise ValueError(f'Si ma mi devi dare una difficoltà')
                    for i in range(multi):
                        raw_roll = list(map(lambda x: random.randint(1, faces), range(n-i-multi)))
                        # todo split index
                        successi, tiro = vtm_res.decider(sorted(raw_roll), diff)
                        response += f'Azione {i+1}: {successi} successi a diff {diff}, tiro: {raw_roll}\n'
                else:
                    raise ValueError(f'Combinazione di parametri non supportata')
            else: # 1 tiro solo 
                raw_roll = list(map(lambda x: random.randint(1, faces), range(n)))
                if split:
                    pass
                else:
                    if rolltype == NORMALE: # tiro normale
                        if not diff:
                            raise ValueError(f'Si ma mi devi dare una difficoltà')
                        #successi, tiro = vtm_res.decider(sorted(raw_roll), diff)
                        successi, tiro, cancel = vtm_res.roller(n, faces, diff)
                        pretty = prettyRoll(tiro, diff, cancel)
                        response = f'{successi} successi a diff {diff}, tiro: {pretty}'
                    elif rolltype == SOMMA:
                        somma = sum(raw_roll)
                        response = f'somma: {somma}, tiro: {raw_roll}'
                    elif rolltype == DANNI:
                        if not diff:
                            diff = 6
                        successi, tiro = vtm_res.decider(sorted(raw_roll), diff,  failcancel = 0)
                        response = f'{successi} danni, tiro: {raw_roll}'
                        if diff != 6:
                            response += f' (diff {diff})'
                    elif rolltype == PROGRESSI:
                        if not diff:
                            diff = 6
                        successi, tiro = vtm_res.decider(sorted(raw_roll), diff, failcancel = 0, spec = True, spec_reroll = False)
                        response = f'progressi: {successi}, tiro: {raw_roll}'
                        if diff != 6:
                            response += f' (diff {diff})'
                    else:
                        raise ValueError(f'Tipo di tiro sconosciuto: {rolltype}')
            
    except ValueError as e:
        response = str(e)
    await atSend(ctx, response)


@bot.command(brief='Lascia che il Greedy Ghost ti saluti.')
async def salut(ctx):
    await atSend(ctx, 'Shalom!')

@bot.command(brief='sapere il ping del Bot')
async def ping(ctx):
    await atSend(ctx, f' Ping: {round(bot.latency * 1000)}ms')

@bot.command(aliases=['divinazione' , 'div'] , brief='Avere risposte.')
async def divina(ctx, *, question):
    responses=['Certamente.',
	 	'Sicuramente.' ,
 		'Probabilmente si.' ,
	 	'Forse.' ,
	  	'Mi sa di no.' ,
		'Probabilmente no.' ,
	 	'Sicuramente no.',
		'Per come la vedo io, si.',
		'Non è scontato.',
		'Meglio chiedere a Rossellini.',
		'Le prospettive sono buone.',
		'Ci puoi contare.',
		'Nebuloso il futuro è.',
		'Sarebbe meglio non risponderti adesso.',
		'Sarebbe uno spoiler troppo grosso.',
		'Non ci contare.',
		'I miei contatti mi dicono di no.'
		]
    await atSend(ctx, f'Domanda: {question}\nRisposta:{random.choice(responses)}')

bot.run(TOKEN)
