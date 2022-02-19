
from typing import Any
from greedy_components import greedyBase as gb
from discord.ext import commands
import support.utils as utils

PARAMETER_INDEXES = utils.enum("chronid", "charid", "user")

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

OPTION_VALIDATORS = {
    PARAMETER_INDEXES.chronid: _chronicle_validator,
    PARAMETER_INDEXES.charid: _character_validator,
    PARAMETER_INDEXES.storyteller: _user_validator
}

class CommandSecurity:
    def __init__(self, bot: gb.GreedyGhost, ctx: commands.Context, **kwargs):
        self.bot = bot
        self.ctx = ctx
        self.options = kwargs
    def checkSecurity(self, *args, **kwargs) -> bool:
        """ performs the security check """
        raise NotImplementedError("Base command security does not check anything!")
    async def getOption(self, option_id: str, args: tuple):
        if not option_id in self.options:
            raise Exception(f"Security item is wrongly configured: missing option {option_id}") # user should not see this as it is likely the programmer's fault
        if self.options[option_id] >= len(args):
            raise self.bot.getBotExceptionLang(self.ctx, 'string_error_security_option_required', option_id) # this is the user's fault
        option_content = args[self.options[option_id]]
        valid = await OPTION_VALIDATORS[option_id](self.bot, option_content)
        if not valid:
            raise self.bot.getBotExceptionLang(self.ctx, 'string_error_security_option_validation_failed', option_content) # this is the user's fault
        return option_content
    async def tryGetOption(self, option_id: str, args: tuple, fallback):
        try:
            return await self.getOption(option_id, args)
        except gb.BotException:
            return fallback

class IsUser(CommandSecurity):
    def checkSecurity(self, *args, **kwargs) -> bool:
        return _user_validator(self.bot,  str(self.ctx.message.author.id))

class IsStoryteller(CommandSecurity):
    def checkSecurity(self, *args, **kwargs) -> bool:
        issuer = str(self.ctx.message.author.id)
        iu, _ = self.bot.dbm.isStoryteller(issuer)
        return iu

class IsAdmin(CommandSecurity):
    def checkSecurity(self, *args, **kwargs) -> bool:
        issuer = str(self.ctx.message.author.id)
        iu, _ = self.bot.dbm.isBotAdmin(issuer)
        return iu

class IsAdminOrStoryteller(CommandSecurity):
    def checkSecurity(self, *args, **kwargs) -> bool:
        issuer = str(self.ctx.message.author.id)
        st, _ = self.bot.dbm.isStoryteller(issuer)
        ba, _ = self.bot.dbm.isBotAdmin(issuer)
        return st or ba

class IsAdminOrChronicleStoryteller(CommandSecurity):
    async def checkSecurity(self, *args, **kwargs) -> bool:
        issuer = str(self.ctx.message.author.id)  
        chronid = await self.getOption(PARAMETER_INDEXES.chronid, args)
        st, _ = self.bot.dbm.isChronicleStoryteller(issuer, chronid)
        ba, _ = self.bot.dbm.isBotAdmin(issuer)
        return st or ba

class CanUnlinkStorytellerFromChronicle(CommandSecurity):
    async def checkSecurity(self, *args, **kwargs) -> bool:
        issuer = str(self.ctx.message.author.id)
        chronid = await self.getOption(PARAMETER_INDEXES.chronid, args)
        target_st = await self.tryGetOption(PARAMETER_INDEXES.user, args, issuer)
        ba, _ = self.bot.dbm.isBotAdmin(issuer)
        st, _ = self.bot.dbm.isChronicleStoryteller(target_st, chronid)
        if st and ba: # Bot admin can unlink anything
            return True
        elif st and issuer == target_st: # ST can unlink themselves
            return True
        else:
            return False

def command_security(security_item: type[CommandSecurity], **security_options):
    """ setup command security for a command created in a GreedyGhostCog """
    def decorator(func):
        async def wrapper(self: gb.GreedyGhostCog, ctx: commands.Context, *args, **kwargs):
            secItem = None
            if isinstance(self, gb.GreedyGhostCog):
                secItem = security_item(self.bot, ctx, **security_options)
            elif isinstance(self, gb.GreedyGhost):
                secItem = security_item(self, ctx, **security_options)
            else:
                raise gb.BotException("Command security is supported only for commands defined in a GreedyGhostCog or GreedyGhost object")
            security_pass = await secItem.checkSecurity(*args, **kwargs)
            if security_pass:
                await func(self, ctx, *args, **kwargs)
            else:
                raise self.bot.getBotExceptionLang(ctx, "string_error_permission_denied")
        return wrapper
    return decorator
