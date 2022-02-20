
from dataclasses import dataclass
from typing import Any, Callable

from greedy_components import greedyBase as gb
from discord.ext import commands
from lang.lang import LangSupportException
import support.utils as utils

async def _chronicle_validator(bot: gb.GreedyGhost, input_string: str) -> bool:
    valid, _ = bot.dbm.isValidChronicle(input_string)
    return valid

async def _character_validator(bot: gb.GreedyGhost, input_string: str) -> bool:
    valid, _ = bot.dbm.isValidCharacter(input_string)
    return valid

async def _user_validator(bot: gb.GreedyGhost, input_string: str) -> bool:
    valid, userid = await bot.validateDiscordMentionOrID(input_string)
    if valid:
        valid, _ = bot.dbm.isUser(userid)
    return valid

#async def _storyteller_validator(bot: gb.GreedyGhost, input_string: str) -> bool:
#    valid, target_st = await bot.validateDiscordMentionOrID(input_string)
#    #TODO
#    return valid

class SecuritySetupError(Exception):
    pass

class SecurityCheckException(LangSupportException):
    pass

class MissingParameterException(LangSupportException):
    pass

class ParameterValidationFailedException(LangSupportException):
    pass

class CommandSecurity:
    def __init__(self, bot: gb.GreedyGhost, ctx: commands.Context, **kwargs):
        self.bot = bot
        self.ctx = ctx
        self.options = kwargs
    def checkSecurity(self, *args, **kwargs) -> tuple(bool, Any):
        """ performs the security check """
        raise NotImplementedError("Base command security does not check anything!")

class IsUser(CommandSecurity):
    def checkSecurity(self, *args, **kwargs) -> tuple(bool, Any):
        issuer = str(self.ctx.message.author.id)
        return self.bot.dbm.isValidUser(issuer)

class IsStoryteller(CommandSecurity):
    def checkSecurity(self, *args, **kwargs) -> tuple(bool, Any):
        issuer = str(self.ctx.message.author.id)
        return self.bot.dbm.isValidStoryteller(issuer)

class IsAdmin(CommandSecurity):
    def checkSecurity(self, *args, **kwargs) -> tuple(bool, Any):
        issuer = str(self.ctx.message.author.id)
        return self.bot.dbm.isValidBotAdmin(issuer)

class IsAdminOrStoryteller(CommandSecurity):
    def checkSecurity(self, *args, **kwargs) -> tuple(bool, Any):
        issuer = str(self.ctx.message.author.id)
        st, _ = self.bot.dbm.isValidStoryteller(issuer)
        ba, _ = self.bot.dbm.isValidBotAdmin(issuer)
        valid = st or ba
        comment = None if valid else SecurityCheckException(0, "L'Utente non è Admin o Storyteller") 
        return valid, comment

class ParametrizedCommandSecurity(CommandSecurity):
    async def getParameter(self, param_idx: str, validator: Callable,  args: tuple): # TODO callable to something more precise
        if param_idx >= len(args):
            raise MissingParameterException(0, 'string_error_security_option_required', param_idx) # this is the user's fault
        param_content = args[param_idx]
        valid = await validator(self.bot, param_content)
        if not valid:
            raise ParameterValidationFailedException(0, 'string_error_security_option_validation_failed', param_content) # this is the user's fault
        return param_content
    async def tryGetParameter(self, param_idx: str, validator: Callable,  args: tuple, fallback):
        try:
            return await self.getParameter(param_idx, validator, args)
        except MissingParameterException:
            return fallback

def genIsAdminOrChronicleStoryteller(target_chronicle):
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple(bool, Any):
            issuer = str(self.ctx.message.author.id)  
            chronid = await self.getParameter(target_chronicle, _chronicle_validator, args)
            st, _ = self.bot.dbm.isChronicleStoryteller(issuer, chronid)
            ba, _ = self.bot.dbm.isValidBotAdmin(issuer)
            valid = st or ba
            comment = None if valid else SecurityCheckException(0, "L'Utente non è Admin o Storyteller") 
            return valid, comment
    return GeneratedCommandSecurity

def genCanUnlinkStorytellerFromChronicle(target_chronicle, target_user):
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple(bool, Any):
            issuer = str(self.ctx.message.author.id)
            chronid = await self.getParameter(target_chronicle, _chronicle_validator, args)
            target_st = await self.tryGetParameter(target_user, _user_validator, args, issuer)
            ba, _ = self.bot.dbm.isBotAdmin(issuer)
            st, _ = self.bot.dbm.isChronicleStoryteller(target_st, chronid)
            if st and ba: # Bot admin can unlink anything
                return True, None
            elif st and issuer == target_st: # ST can unlink themselves
                return True, None
            else:
                return False, SecurityCheckException(0, "Solo gli admin possono disassociare un utente diverso da loro stessi da una cronaca") 
    return GeneratedCommandSecurity

def command_security(security_item: type[CommandSecurity], **security_options):
    """ setup command security for a command created in a GreedyGhostCog """
    def decorator(func):
        async def wrapper(self: gb.GreedyGhostCog, ctx: commands.Context, *args, **kwargs):
            secItem: CommandSecurity = None
            if isinstance(self, gb.GreedyGhostCog):
                secItem = security_item(self.bot, ctx, **security_options)
            elif isinstance(self, gb.GreedyGhost):
                secItem = security_item(self, ctx, **security_options)
            else:
                raise SecuritySetupError("Command security is supported only for commands defined in a GreedyGhostCog or GreedyGhost object")
            if not issubclass(security_item, CommandSecurity):
                raise SecuritySetupError(f"Type {secItem} is not a {CommandSecurity} object")
            security_pass, security_comment = await secItem.checkSecurity(*args, **kwargs)
            if security_pass:
                await func(self, ctx, *args, **kwargs)
            else:
                raise SecurityCheckException(0, "string_error_permission_denied", secItem.bot.formatException(security_comment))
        return wrapper
    return decorator
