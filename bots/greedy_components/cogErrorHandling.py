
import MySQLdb
from discord.ext import commands

from greedy_components import greedyBase as gb
from greedy_components.cogPCmgmt import GreedyGhostCog_PCmgmt

import lang.lang as lng

class GreedyGhostCog_ErrorHandling(gb.GreedyGhostCog):
    """ Does Error handling for the bot """
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: gb.GreedyContext, error: Exception):
        with ctx.getSession() as session:
            with session.begin(): # this ensures commit on success/rollback on failure
                lid = ctx.getLID()
                error = getattr(error, 'original', error)
                #ignored = (commands.CommandNotFound, )
                #if isinstance(error, ignored):
                #    print(error)
                if isinstance(error, commands.CommandNotFound):
                    executed_pgmanage = False
                    try:
                        msgsplit = ctx.message.content.split(" ")
                        prefix = await self.bot.get_prefix(ctx.message)
                        if isinstance(prefix, list):
                            prefix: str = prefix[0]
                        msgsplit[0] = msgsplit[0][len(prefix):] # toglie prefisso
                        msgsplit = [y for y in msgsplit if y != '']  # toglie stringhe vuote
                        charid = msgsplit[0]
                        ic, _ = self.bot.dbm.validators.getValidateCharacter(charid).validate()
                        if ic:
                            pgmanage_cog: GreedyGhostCog_PCmgmt = self.bot.get_cog(GreedyGhostCog_PCmgmt.__name__)
                            if pgmanage_cog is not None: 
                                TARGET_COMMAND = 'pgmanage'
                                ctx.message.content = " ".join([prefix+TARGET_COMMAND]+msgsplit)
                                newctx = await self.bot.get_context(ctx.message)
                                await self.bot.invoke(newctx)
                                executed_pgmanage = True
                        return
                    except Exception as e:
                        error = e
                        
                    if not executed_pgmanage:
                        await self.bot.atSendLang(ctx, "string_error_wat")
                if isinstance(error, gb.BotException):
                    await self.bot.atSend(ctx, f'{error}')
                elif isinstance(error, lng.LangSupportErrorGroup):
                    await self.bot.atSend(ctx, self.bot.formatException(ctx, error))
                elif isinstance(error, lng.LangSupportException):
                    await self.bot.atSend(ctx, self.bot.languageProvider.formatException(lid, error))
                elif isinstance(error, gb.GreedyCommandError):
                    await self.bot.atSend(ctx, self.bot.languageProvider.formatException(lid, error))
                elif isinstance(error, commands.MissingRequiredArgument):
                    await ctx.send_help(ctx.command)
                elif isinstance(error, lng.LangException):
                    await self.bot.atSend(ctx, f'{error}')
                else:
                    if isinstance(error, MySQLdb.OperationalError):
                        if error.args[0] == 2006:
                            await self.bot.atSendLang(ctx, "string_error_database_noanswer")
                            self.bot.dbm.reconnect()
                        else:
                            await self.bot.atSendLang(ctx, "string_error_database_generic")
                    elif isinstance(error, MySQLdb.IntegrityError):
                        await self.bot.atSendLang(ctx, "string_error_database_dataviolation")
                    else:
                        await self.bot.atSendLang(ctx, "string_error_unhandled_exception")
                    #print("debug user:", int(config['Discord']['debuguser']))
                    debug_userid = self.bot.config['Discord']['debuguser'] # TODO use Logtodebuguser and make it more robust
                    debug_user = ''
                    lid = self.bot.getLID(debug_userid) # this does not raise, and does not need that the user exists
                    error_details = self.bot.languageProvider.get(lid, "string_error_details", ctx.message.content, type(error), error)
                    # figure out where to send the error
                    if debug_userid and debug_userid != '':
                        debug_user = await self.bot.fetch_user(int(debug_userid))            
                    if debug_user != '':
                        await debug_user.send(error_details)
                    else:
                        print(error_details) # TODO logs
           

