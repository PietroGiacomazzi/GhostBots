from typing import Any, Callable

from greedy_components import greedyBase as gb
from discord.ext import commands
from lang.lang import LangSupportException
from support import security as sec

class BotSecurityCheckException(gb.GreedyCommandError):
    pass

basicRegisteredUser: type[sec.CommandSecurity] = sec.OR(sec.IsAdmin, sec.AND(sec.IsUser, sec.IsActiveOnGuild), sec.IsPrivateChannelWithRegisteredUser)
basicStoryTeller: type[sec.CommandSecurity] = sec.OR(sec.IsAdmin, sec.AND( sec.IsStoryteller, sec.OR(sec.IsActiveOnGuild, sec.IsPrivateChannelWithRegisteredUser)))

def command_security(security_item: type[sec.CommandSecurity] = sec.NoCheck, *additional_security_items: type[sec.CommandSecurity], **security_options):
    """ Add security checks to a command with before_invoke, needs CommandSecurity objects as parameters
    If all the CommandSecurity items pass their checks, then the command executes.
    
    Example
    ---------
    
    @commands.command(name = 'my_command')
    @commands.before_invoke(command_security(gs.isUser))\n
    async def my_command(self, ctx: commands.Context, *args):
        pass

    """
    async def before_invoke_command_security(instance : gb.GreedyGhostCog, ctx: commands.Context):
        security_check_class = security_item
        if len(additional_security_items):
            security_check_class = sec.AND(security_item, *additional_security_items)

        if not issubclass(security_check_class, sec.CommandSecurity):
            raise BotSecurityCheckException(f"Type {security_check_class} is not a {sec.CommandSecurity} object")
        
        security_check_instance = None
        
        bot_instance: gb.GreedyGhost = None
        if isinstance(instance, gb.GreedyGhostCog):
            bot_instance = instance.bot
        elif isinstance(instance, gb.GreedyGhost): # should never happen but will save us if we define a command in the main bot instead of cogs
            bot_instance = instance
        
        if (not bot_instance is None):
            security_check_instance = security_check_class(ctx, **security_options)
        else:
            raise BotSecurityCheckException(f"Command security is supported only for commands defined in a GreedyGhostCog. Provided object type: {type(instance)}")

        security_pass, security_comment = await security_check_instance.checkSecurity(*ctx.args, **ctx.kwargs)
        if not security_pass:
            raise BotSecurityCheckException("string_error_permission_denied", (bot_instance.formatException(ctx, security_comment), ))
    return before_invoke_command_security
