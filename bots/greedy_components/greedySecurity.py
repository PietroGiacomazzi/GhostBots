
from greedy_components import greedyBase as gb
from discord.ext import commands

class CommandSecurity:
    def __init__(self, bot: gb.GreedyGhost, ctx: commands.Context, **kwargs):
        self.bot = bot
        self.ctx = ctx
        self.options = kwargs
    def checkSecurity(self) -> bool:
        """ performs the security check """
        raise NotImplementedError("Base command security does not check anything!")

class IsUser(CommandSecurity):
    def checkSecurity(self) -> bool:
        issuer = str(self.ctx.message.author.id)
        iu, _ = self.bot.dbm.isUser(issuer)
        return iu

class IsStoryteller(CommandSecurity):
    def checkSecurity(self) -> bool:
        issuer = str(self.ctx.message.author.id)
        iu, _ = self.bot.dbm.isStoryteller(issuer)
        return iu

class IsAdmin(CommandSecurity):
    def checkSecurity(self) -> bool:
        issuer = str(self.ctx.message.author.id)
        iu, _ = self.bot.dbm.isBotAdmin(issuer)
        return iu

def command_security_cog(security_item: type[CommandSecurity], **security_options):
    """ setup command security for a command created in a GreedyGhostCog """
    def decorator(func):
        def wrapper(self: gb.GreedyGhostCog, ctx: commands.Context, *args, **kwargs):
            print("Self type:", type(self))
            secItem = security_item(self.bot, ctx, security_options)
            if secItem.checkSecurity():
                func(self, ctx, *args, **kwargs)
            else:
                raise self.bot.getBotExceptionLang("string_error_permission_denied")
        return wrapper
    return decorator
