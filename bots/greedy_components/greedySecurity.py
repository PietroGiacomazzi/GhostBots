from typing import Any, Callable

from greedy_components import greedyBase as gb
from discord.ext import commands
from lang.lang import LangSupportException
from support import ghostDB

class SecuritySetupError(Exception):
    pass

class SecurityCheckException(gb.GreedyCommandError):
    pass

class MissingParameterException(gb.GreedyCommandError):
    pass

#class ParameterValidationFailedException(gb.GreedyCommandError):
#    pass

class CommandSecurity:
    def __init__(self, bot: gb.GreedyGhost, ctx: commands.Context, **kwargs):
        self.bot = bot
        self.ctx = ctx
        self.options = kwargs
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        """ performs the security check """
        raise NotImplementedError("Base command security does not check anything!")

class NoCheck(CommandSecurity):
    """ Always passes """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        return True, None

class IsActiveOnGuild(CommandSecurity):
    """ Passes if the command is issued in an authorized Guild, or the issuer is a Bot Admin """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer = str(self.ctx.message.author.id)
        ba, _ = self.bot.dbm.validators.getValidateBotAdmin(issuer).validate()
        ig, guild = self.bot.dbm.validators.getValidateGuild(issuer).validate()
        active = False
        if ig:
            active = guild["authorized"]
        valid = ba or (ig and active)
        comment = None if valid else SecurityCheckException("string_error_server_not_authorized")
        return valid, comment 

class IsUser(CommandSecurity):
    """ Passes if the command is issued by a tracked user """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer = str(self.ctx.message.author.id)
        return self.bot.dbm.validators.getValidateBotUser(issuer).validate()

class IsStoryteller(CommandSecurity):
    """ Passes if the command is issued by a Storyteller """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer = str(self.ctx.message.author.id)
        return self.bot.dbm.validators.getValidateBotStoryTeller(issuer).validate()

class IsAdmin(CommandSecurity):
    """ Passes if the command is issued by a Bot Admin """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer = str(self.ctx.message.author.id)
        return self.bot.dbm.validators.getValidateBotAdmin(issuer).validate()

class IsAdminOrStoryteller(CommandSecurity):
    """ Passes if the command is issued by either an admin or a storyteller """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer = str(self.ctx.message.author.id)
        st, _ = self.bot.dbm.validators.getValidateBotStoryTeller( issuer).validate()
        ba, _ = self.bot.dbm.validators.getValidateBotAdmin(issuer).validate()
        valid = st or ba
        comment = None if valid else SecurityCheckException("L'Utente non è Admin o Storyteller") 
        return valid, comment

class CanEditRunningSession(CommandSecurity): # this needs to exist separately from genIsAdminOrChronicleStoryteller because the chronicle is not available in the command parameters, but rather is a property of the current channel
    """ Passes if the command is issued by an owner of the currently running session of the channel, or a Bot Admin """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer_id = str(self.ctx.message.author.id)
        sr, session = self.bot.dbm.validators.getValidateRunningSession(self.ctx.channel.id).validate()
        valid = sr
        comment = ''
        if valid:
            ba, _ = self.bot.dbm.validators.getValidateBotAdmin(issuer_id).validate()
            st, _ = self.bot.dbm.isChronicleStoryteller(issuer_id, session['chronicle'])
            valid = ba or st
            comment = comment if valid else SecurityCheckException("Non hai il ruolo di Storyteller per questa cronaca")
        else:
            comment = SecurityCheckException("Non c'è alcuna sessione attiva in questo canale") 
        return valid, comment

# secitems
class ParametrizedCommandSecurity(CommandSecurity):
    """ Abstract class tha allows building CommandSecurity objects that can acces the command's parameters """
    async def getParameter(self, param_idx: str, args: tuple):
        if param_idx >= len(args): # should almost never happen as we're moving to explicit parameters on command signatures
            raise MissingParameterException('string_error_security_option_required', (param_idx,))
        return args[param_idx]
    async def tryGetParameter(self, param_idx: str, args: tuple, fallback):
        try:
            value =  await self.getParameter(param_idx, args)
            if not value == None:
                return value
            else:
                return fallback
        except MissingParameterException:
            return fallback

def genIsAdminOrChronicleStoryteller(target_chronicle):
    """ Passes if the command is issued by a Storyteller that can control target_chronicle, or a Bot Admin """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
            issuer_id = str(self.ctx.message.author.id)  
            chronicle = await self.getParameter(target_chronicle, args)
            chronid = chronicle['id']
            st, _ = self.bot.dbm.isChronicleStoryteller(issuer_id, chronid)
            ba, _ = self.bot.dbm.validators.getValidateBotAdmin(issuer_id).validate()
            valid = st or ba
            comment = None if valid else SecurityCheckException("L'Utente non è Admin o Storyteller della cronaca {}", (chronicle['name'],)) 
            return valid, comment
    return GeneratedCommandSecurity

def genCanUnlinkStorytellerFromChronicle(target_chronicle, optional_target_user):
    """ Passes if the command is issued by a someone that can unlink optional_target_user from target_chronicle: either the storyteller themselves or a bot admin """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
            issuer_id = str(self.ctx.message.author.id)
            chronicle = await self.getParameter(target_chronicle,  args)
            target_storyteller = await self.tryGetParameter(optional_target_user, args, issuer_id)
            target_st = target_storyteller['userid']
            chronid = chronicle['id']
            ba, _ = self.bot.dbm.validators.getValidateBotAdmin(issuer_id).validate()
            st, _ = self.bot.dbm.isChronicleStoryteller(target_st, chronid)
            if st and ba: # Bot admin can unlink anything
                return True, None
            elif st and issuer_id == target_st: # ST can unlink themselves
                return True, None
            else:
                msg = ''
                if ba: #  was not a storyteller  
                    msg = f"L'utente non è storyteller della cronaca {chronicle['name']}"
                elif st: # target was not self
                    msg =  "Solo gli admin possono disassociare un utente diverso da loro stessi da una cronaca"
                else:
                    msg = "string_error_permission_reason_generic"
                return False, SecurityCheckException(msg)
    return GeneratedCommandSecurity

def genCanCreateCharactertoSomeone(optional_target_user):
    """ Passes if the command is issued by a someone that can create a character for optional_target_user: either a regular user for themselves, or a storyteller, or a bot admin """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
            issuer_id = str(self.ctx.message.author.id)  
            target_usr = await self.tryGetParameter(optional_target_user, args, issuer_id)
            target_usr_id = target_usr['userid']
            valid = True
            comment = ''
            if target_usr_id != issuer_id:
                st, _ = self.bot.dbm.validators.getValidateBotStoryTeller(issuer_id).validate()
                ba, _ = self.bot.dbm.validators.getValidateBotAdmin(issuer_id).validate()
                valid = st or ba
                if not valid:
                    comment = SecurityCheckException("Per creare un pg ad un altra persona è necessario essere Admin o Storyteller") 
            return valid, comment
    return GeneratedCommandSecurity

def genCanEditCharacter(target_character):
    """ Passes if the command is issued by a someone that can edit target_character: either a bot admin, a storyteller for a chronicle that contains the character, or the character owner if a session is running """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        async def checkSecurity(self, *command_args, **command_kwargs) -> tuple: #[bool, Any]:
            issuer = str(self.ctx.message.author.id)  
            character = await self.getParameter(target_character, command_args)
            charid = character['id']
            owner = character['owner']

            st, _ = self.bot.dbm.isStorytellerForCharacter(issuer, charid)
            ba, _ = self.bot.dbm.validators.getValidateBotAdmin(issuer).validate()
            co = owner == issuer
            ce = st or ba 
            if co and (not ce):
                #1: unlinked
                cl, _ = self.bot.dbm.isCharacterLinked(charid)
                #2 active session
                sa, _ = self.bot.dbm.isSessionActiveForCharacter(charid, self.ctx.channel.id)
                ce = (not cl) or sa            

            valid =  (st or ba or (co and ce))
            comment = None if valid else SecurityCheckException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Admin o Storyteller") 
            return valid, comment
    return GeneratedCommandSecurity

def command_security(security_item: type[CommandSecurity] = NoCheck, *additional_security_items, **security_options):
    """ Add security checks to a command with before_invoke, needs CommandSecurity objects as parameters
    If all the CommandSecurity items pass their checks, then the command executes.
    
    Example
    ---------
    
    @commands.command(name = 'my_command')
    @commands.before_invoke(command_security(gs.isUser))
    async def my_command(self, ctx: commands.Context, *args):
        pass

    """
    async def before_invoke_command_security(instance : gb.GreedyGhostCog, ctx: commands.Context):
        command_security_list = [security_item] + list(additional_security_items)
        for command_security_item in command_security_list:
            if not issubclass(command_security_item, CommandSecurity):
                raise SecurityCheckException(f"Type {command_security_item} is not a {CommandSecurity} object")
            secItem = None
            if isinstance(instance, gb.GreedyGhostCog):
                secItem = command_security_item(instance.bot, ctx, **security_options)
            #elif isinstance(self, gb.GreedyGhost):
            #    secItem = command_security_item(self, ctx, **security_options)
            else:
                raise SecurityCheckException(f"Command security is supported only for commands defined in a GreedyGhostCog. Provided object type: {type(instance)}")
            security_pass, security_comment = await secItem.checkSecurity(*ctx.args, **ctx.kwargs)
            if not security_pass:
                raise SecurityCheckException("string_error_permission_denied", (secItem.bot.formatException(ctx, security_comment), ))
    return before_invoke_command_security
