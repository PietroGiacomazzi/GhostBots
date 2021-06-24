#!/usr/bin/env python3

import os
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

import discord
from discord.ext import commands
import random, sys, configparser
import support.vtm_res

if len(sys.argv) == 1:
    print("Specifica un file di configurazione!")
    sys.exit()

config = configparser.ConfigParser()
config.read(sys.argv[1])

TOKEN = config['Discord']['token']


bot = commands.Bot(['gg', '.'], help_command=None)


attivita = [
    (discord.ActivityType.watching, "il polpaccio di Rossellini"),
    (discord.ActivityType.watching, "Jerome con odio"),
    (discord.ActivityType.playing,  "all'impiccato con Joshua"),
    (discord.ActivityType.watching, "l'immondizia"),
    (discord.ActivityType.watching, "l'immondizia. Cioè Rossellini"),
    (discord.ActivityType.watching, "Rossellini con aria affamata")
    ]

#executed once on bot boot
@bot.event
async def on_ready():
    for guild in bot.guilds:
        print(
            f'{bot.user} is connected to the following guild:\n'
            f'{guild.name} (id: {guild.id})'
        )
    acttype, actstring = random.choice(attivita)
    await bot.change_presence(activity=discord.Activity(type=acttype, name=actstring))   
    #await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Rossellini con aria affamata"))
    #members = '\n - '.join([member.name for member in guild.members])
    #print(f'Guild Members:\n - {members}')
    #await bot.get_channel(int(config['DISCORD_DEBUG_CHANNEL'])).send("bot is online")

@bot.event
async def on_error(event, *args, **kwargs):
    print(f"On_error: {args[0]}")
    #await bot.get_channel(int(config['DISCORD_DEBUG_CHANNEL'])).send(f'Unhandled message: {args[0]}')
    raise

@bot.command('help')
async def help(context, *args):
    if len(args):
        if args[0] in ["roll", "me"]:
            await context.send("Sto mangiando. Ti risponde quell'altro")
        elif args[0] == 'rossellini':
            epiteti = [
                "quel maledetto"     
                ]
            await context.send(f"Ti dirò quello che penso di {random.choice(epiteti)} di un Rossellini")


@bot.command('rossellini')
async def rossellini(ctx):
    if random.random() < float(config['Settings']['activity_pct']):
        acttype, actstring = random.choice(attivita)
        await bot.change_presence(activity=discord.Activity(type=acttype, name=actstring))
    insulti=['Ti stacco i tendini a morsi, sciacquatore di palle' ,
            'Pezzo di Fango che mi incrosta il pelo' ,
            'Speleologo dei culi rotti' ,
            'Ossa, mafia e mandolino' ,
            'AAAAAAAAAAAAAAAAAAAAAAAAA' ,
            'Sei peggio della spazzatura che mastico ogni giorno' ,
            'Non puoi morire, finché non ti ammazzo io' ,
            'Kkkekkkkekkkkkekkke' ,
            'Meglio un cassonetto oggi che un Rossellini tutta la vita' ,
            'Soporifero come le esalazioni fognarie' ,
            'La tua famiglia è come un tesoro: ti servono mappa e pala per trovarla' ,
            'Ti odio più di quella cagna di tua cugina' ,
            'Sacchetto de monnezza' ,
            'Le rose sono rosse, le viole son blu, il primo a crepare sarai proprio tu' ,
            "Hai un bidone dell'immondizia al posto del cuore, e io sono affamato" ,
            'Rossellini fa rima con "ti scortico la faccia"' ,
            'Evocami di nuovo e ti cavo gli occhi' ,
            '+1 ad Iniziativa' ,
            'È stato subito odio a prima vista'  ,
            'Io mi fingo morto, tu lo sarai davvero' ,
            'È meglio se inizi a correre' ,
            'Quando sarà buio ti troverò e ti riempirò di botte' ,
            'Kkkrrkkkekkkkekkkkkrkekkkkekkekkkkkkkrekkkkkekkekkkekkrkekk' ,
            'Ho mangiato mele marce molto più dignitose di te' ,
            'Ho trovato una cosa interessante nella pattumiera: la tua faccia' ,
            'Il ratto che vive nella pattumiera accanto ha più palle di te' ,
            'Riuscirai a fare schifo anche oggi? Si.. ovvio che si' ,
            'Ma tu guarda! Devo insultarti ancora, che lavoro delizioso. Fai schifo.' ,
            'Sarebbe stato più produttivo rovistare nella casella postale della discarica' ,
            'Non ti bastava essere Italiano? Dovevi per forza essere anche osceno?' ,
            "Nessuno si stanca mai di ricordarti che è meglio il bidone dell'umido" ,
            'Oggi nel bidone della monnezza ho trovato le tue palle, da quanto le avevi perse?' ,
            'Sei più imbarazzante del tuo amico nero' ,
            'Prima o poi riuscirò a morderti davvero' ,
            'Guardarti in faccia rischia di farmi morire di nuovo' ,
            'Maledetto Rossellini' ,
            'Oggi mi sento buono, +1 iniziativa ma non a Rossellini' ,
            '+1 ad iniziativa solo a Rossellini, così crepa prima' ,
            'Resuscita la vastità del cazzo che me ne frega di te' ,
            "Lorenzo sai che ora è? È ora che ti levi dal cazzo" ,
            'Entra nel tuo ambiente naturale: muori' ,
            'Ho trovato una cosa che ti farebbe bene: un sacco pieno di ceffoni' ,
            'Hai il carisma di una fetta merdosa di una torta al guano' ,
            'Con quel muso mi fai perdere il pelo fantasma che mi rimane' ,
            "+ 1 all'iniziativa di chi ti insulta nei prossimi 3 secondi" ,
            'Maledetta quella volta che mamma Rossellini e papà Rossellini hanno deciso di vomitare assieme' ,
            'Non potevi rimanere in Italia? Qui abbiamo già i nostri problemi del cazzo' ,
            'La prossima volta chiedi aiuto al Papa' ,
	    'Usa quei rituali, razza di topo de fogna' ,
	    'Fammi indovinare, quel coso si è mosso, meglio sparagli, vero?' ,
	    '+1 Iniziativa fino a quando Rossellini non usa un rituale' ,
	    "Tra un po' sono più utile io di te, e ti ricordo che sono morto, e mi vedi solo tu"
             ]
    await ctx.send(f'{random.choice(insulti)}')


@bot.command(aliases=['paradiso' , 'torta'] , brief='Ricorda a Sam il vero Vietnam' , help = 'Il regno del colesterolo')
async def paradise(ctx):
    replies=['https://funnelcakesparadise.com/wp-content/uploads/2020/06/FUNNEL-CAKE-PARADISE-MENU-4.png' ,
             'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT_U_TC2RrY1HupVVnqaYbh8icE5fQ5RtZaEA&usqp=CAU' ,
             ':motorized_wheelchair: :cake: :baby_bottle: :drop_of_blood:' ,
             'https://funnelcakesparadise.com/wp-content/uploads/2017/12/Catering-Menu-2.png' ]
    await ctx.send(f'Ti sblocco un ricordo: {random.choice(replies)}')	
		

bot.run(TOKEN)
