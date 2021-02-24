#!/usr/bin/env python3

from discord.ext import commands
import random, sys, configparser
import support.vtm_res

if len(sys.argv) == 1:
    print("Specifica un file di configurazione!")
    sys.exit()

config = configparser.ConfigParser()
config.read(sys.argv[1])

TOKEN = config['Discord']['token']



bot = commands.Bot(['gg', '.'])

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


@bot.command('rossellini')
async def rossellini(ctx):
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
		 ]
	await ctx.send(f'{random.choice(insulti)}')

bot.run(TOKEN)
