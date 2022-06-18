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
    def __init__(self, bot: gb.GreedyGhost, ctx: gb.GreedyContext, **kwargs):
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
    """ Passes if the command is issued in an authorized Guild """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        guild = self.ctx.guild
        
        valid, comment = (False, SecurityCheckException("string_error_server_not_authorized"))

        if not guild is None:
            ig, guild = self.bot.dbm.validators.getValidateGuild(guild.id).validate()
            active = False
            if ig:
                active = guild["authorized"]
            valid = (ig and active)
            comment = None if valid else SecurityCheckException("string_error_server_not_authorized")

        return valid, comment 

class IsPrivateChannelWithRegisteredUser(CommandSecurity):
    """ Passes if the command is issued in a private channel with an authorized user """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        guild = self.ctx.guild

        valid, comment = (False, SecurityCheckException("string_error_server_not_authorized"))

        if guild is None:
            valid, comment =  self.ctx.validateUserInfo()
        
        return valid, comment 

class IsUser(CommandSecurity):
    """ Passes if the command is issued by a tracked user """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        return self.ctx.validateUserInfo()

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

class CanEditRunningSession(CommandSecurity): # this needs to exist separately from genIsAdminOrChronicleStoryteller because the chronicle is not available in the command parameters, but rather is a property of the current channel
    """ Passes if the command is issued by an owner of the currently running session of the channel """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer_id = str(self.ctx.message.author.id)
        sr, session = self.bot.dbm.validators.getValidateRunningSession(self.ctx.channel.id).validate()
        valid = sr
        comment = ''
        if valid:
            st, _ = self.bot.dbm.isChronicleStoryteller(issuer_id, session['chronicle'])
            valid = st
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

def genIsChronicleStoryteller(target_chronicle):
    """ Passes if the command is issued by a Storyteller that can control target_chronicle """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
            issuer_id = str(self.ctx.message.author.id)  
            chronicle = await self.getParameter(target_chronicle, args)
            chronid = chronicle['id']
            st, _ = self.bot.dbm.isChronicleStoryteller(issuer_id, chronid)
            valid = st
            comment = None if valid else SecurityCheckException("L'Utente non è Storyteller della cronaca {}", (chronicle['name'],)) 
            return valid, comment
    return GeneratedCommandSecurity

def genIsSelf(optional_target_user):
    """ Passes if the command is issued by someone that is targeting themselves """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
            issuer_id = str(self.ctx.message.author.id)  
            target_usr = await self.tryGetParameter(optional_target_user, args, issuer_id)
            target_usr_id = target_usr['userid']
            valid =  target_usr_id == issuer_id
            return valid, None if valid else SecurityCheckException("Non puoi indicare una persona diversa da te") 
    return GeneratedCommandSecurity

#TODO: split into multiple items: genIsCharacterStoryTeller, genIsCharacterPlayer, genIsSessionRunningforCharacter
def genCanEditCharacter(target_character):
    """ Passes if the command is issued by a someone that can edit target_character: either a storyteller for a chronicle that contains the character, or the character owner if a session is running """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        async def checkSecurity(self, *command_args, **command_kwargs) -> tuple: #[bool, Any]:
            issuer = str(self.ctx.message.author.id)  
            character = await self.getParameter(target_character, command_args)
            charid = character['id']
            owner = character['owner']

            st, _ = self.bot.dbm.isStorytellerForCharacter(issuer, charid)
            co = owner == issuer
            ce = st 
            if co and (not ce):
                #1: unlinked
                cl, _ = self.bot.dbm.isCharacterLinked(charid)
                #2 active session
                sa, _ = self.bot.dbm.isSessionActiveForCharacter(charid, self.ctx.channel.id)
                ce = (not cl) or sa            

            valid =  (st or (co and ce))
            comment = None if valid else SecurityCheckException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Storyteller") 
            return valid, comment
    return GeneratedCommandSecurity

def OR(*cs_sequence: type[CommandSecurity]) -> CommandSecurity:
    """ returns a CommandSecurity type that performs an OR between the checkSecurity method results of all the argument CommandSecurity types """
    class CombinedCommandSecurity(CommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple:
            valid = False
            errors = []
            for cs in cs_sequence:
                assert issubclass(cs, CommandSecurity)
                cs_item: CommandSecurity = cs(self.bot, self.ctx, **self.options)
                vt, ct = await cs_item.checkSecurity(*args, **kwargs)
                valid = valid or vt
                if not vt:
                    errors.append(ct)
                if valid: # OR needs only one criteria to pass
                    break
            comment = None
            if not valid:
                comment = gb.GreedyErrorGroup("MultiError", errors)
            return valid, comment

    return CombinedCommandSecurity

def AND(*cs_sequence: type[CommandSecurity]) -> CommandSecurity:
    """ returns a CommandSecurity type that performs an AND between the checkSecurity method results of all the argument CommandSecurity types """
    class CombinedCommandSecurity(CommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple:
            valid = True
            errors = []
            for cs in cs_sequence:
                assert issubclass(cs, CommandSecurity)
                cs_item: CommandSecurity = cs(self.bot, self.ctx, **self.options)
                vt, ct = await cs_item.checkSecurity(*args, **kwargs)
                valid = valid and vt
                if not vt:
                    errors.append(ct)
                if not valid: # AND needs All criteria to pass
                    break
            comment = None
            if not valid:
                comment = gb.GreedyErrorGroup("MultiError", errors)
            return valid, comment

    return CombinedCommandSecurity

def command_security(security_item: type[CommandSecurity] = NoCheck, *additional_security_items: type[CommandSecurity], **security_options):
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
            security_check_class = AND(security_item, *additional_security_items)

        if not issubclass(security_check_class, CommandSecurity):
            raise SecurityCheckException(f"Type {security_check_class} is not a {CommandSecurity} object")
        security_check_instance = None
        if isinstance(instance, gb.GreedyGhostCog):
            security_check_instance = security_check_class(instance.bot, ctx, **security_options)
        elif isinstance(instance, gb.GreedyGhost): # should never happen but will save us if we define a command in the main bot instead of cogs
            security_check_instance = security_check_class(instance, ctx, **security_options)
        else:
            raise SecurityCheckException(f"Command security is supported only for commands defined in a GreedyGhostCog. Provided object type: {type(instance)}")
        security_pass, security_comment = await security_check_instance.checkSecurity(*ctx.args, **ctx.kwargs)
        if not security_pass:
            raise SecurityCheckException("string_error_permission_denied", (security_check_instance.bot.formatException(ctx, security_comment), ))
    return before_invoke_command_security
