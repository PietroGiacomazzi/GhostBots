
from dataclasses import dataclass
from support import ghostDB
import lang.lang as lng
import web

class SecurityCheckException(lng.LangSupportException):
    pass

class MissingParameterException(lng.LangSupportException):
    pass

class SecuritySetupError(lng.LangSupportException):
    pass

class SecurityContext:

    registeredUser: bool = None
    userData = None #  web.utils.Storage | ghostDB.DBException # usupported type hint by 3.9
    language_id = None

    def getUserId(self) -> int:
        raise NotImplementedError()
    def getGuildId(self) -> int:
        raise NotImplementedError()
    def getChannelId(self) -> int:
        raise NotImplementedError
    def getDBManager(self) -> ghostDB.DBManager:
        raise NotImplementedError()
    def getDefaultLanguageId() -> str:
        raise NotImplementedError()

    def _loadUserInfo(self):
        self.registeredUser, self.userData = self.getDBManager().validators.getValidateBotUser(self.getUserId()).validate()
        if self.registeredUser:
            self.language_id = self.userData['langId']
        else:
            self.language_id = self.getDefaultLanguageId()
    def getLID(self) -> str:
        if self.registeredUser is None:
            self._loadUserInfo()

        return self.language_id
    def validateUserInfo(self):
        if self.registeredUser is None:
            self._loadUserInfo()

        return self.registeredUser, self.userData
    def getUserInfo(self):
        if self.registeredUser is None:
            self._loadUserInfo()

        if self.registeredUser:
            return self.userData
        else:
            raise self.userData

class CommandSecurity:
    def __init__(self, ctx: SecurityContext, **kwargs):
        self.ctx = ctx
        self.options = kwargs
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        """ performs the security check """
        raise NotImplementedError("Base command security does not check anything!")

class NoCheck(CommandSecurity):
    """ Always passes """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        return True, None

class IsUser(CommandSecurity):
    """ Passes if the command is issued by a tracked user """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        return self.ctx.validateUserInfo()

class IsActiveOnGuild(CommandSecurity):
    """ Passes if the command is issued in an authorized Guild """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        guildid = self.ctx.getGuildId()
        
        valid, comment = (False, SecurityCheckException("string_error_server_not_authorized"))

        if not guildid is None:
            ig, guild = self.ctx.getDBManager().validators.getValidateGuild(guildid).validate()
            active = False
            if ig:
                active = guild["authorized"]
            valid = (ig and active)
            comment = None if valid else SecurityCheckException("string_error_server_not_authorized")

        return valid, comment 

class IsPrivateChannelWithRegisteredUser(CommandSecurity):
    """ Passes if the command is issued in a private channel with an authorized user """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        guildid = self.ctx.getGuildId()

        valid, comment = (False, SecurityCheckException("string_error_server_not_authorized"))

        if guildid is None:
            valid, comment =  self.ctx.validateUserInfo()
        
        return valid, comment 

class IsStoryteller(CommandSecurity):
    """ Passes if the command is issued by a Storyteller """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer = str(self.ctx.getUserId())
        return self.ctx.getDBManager().validators.getValidateBotStoryTeller(issuer).validate()

class IsAdmin(CommandSecurity):
    """ Passes if the command is issued by a Bot Admin """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer = str(self.ctx.getUserId())
        return self.ctx.getDBManager().validators.getValidateBotAdmin(issuer).validate()

class CanEditRunningSession(CommandSecurity): # this needs to exist separately from genIsAdminOrChronicleStoryteller because the chronicle is not available in the command parameters, but rather is a property of the current channel
    """ Passes if the command is issued by an owner of the currently running session of the channel """
    async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer_id = str(self.ctx.getUserId())
        sr, session = self.ctx.getDBManager().validators.getValidateRunningSession(self.ctx.getChannelId()).validate()
        valid = sr
        comment = ''
        if valid:
            st, _ = self.ctx.getDBManager().isChronicleStoryteller(issuer_id, session['chronicle'])
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
            issuer_id = str(self.ctx.getUserId())  
            chronicle = await self.getParameter(target_chronicle, args)
            chronid = chronicle['id']
            st, _ = self.ctx.getDBManager().isChronicleStoryteller(issuer_id, chronid)
            valid = st
            comment = None if valid else SecurityCheckException("L'Utente non è Storyteller della cronaca {}", (chronicle['name'],)) 
            return valid, comment
    return GeneratedCommandSecurity

def genIsSelf(optional_target_user):
    """ Passes if the command is issued by someone that is targeting themselves """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
            issuer_id = str(self.ctx.getUserId())  
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
            issuer = str(self.ctx.getUserId())  
            character = await self.getParameter(target_character, command_args)
            charid = character['id']
            owner = character['owner']

            st, _ = self.ctx.getDBManager().isStorytellerForCharacter(issuer, charid)
            co = owner == issuer
            ce = st 
            if co and (not ce):
                #1: unlinked
                cl, _ = self.ctx.getDBManager().isCharacterLinked(charid)
                #2 active session
                sa, _ = self.ctx.getDBManager().isSessionActiveForCharacter(charid, self.ctx.getChannelId())
                ce = (not cl) or sa            

            valid =  (st or (co and ce))
            comment = None if valid else SecurityCheckException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Storyteller") 
            return valid, comment
    return GeneratedCommandSecurity

def OR(*cs_sequence: type[CommandSecurity]) -> type[CommandSecurity]:
    """ returns a CommandSecurity type that performs an OR between the checkSecurity method results of all the argument CommandSecurity types """
    class CombinedCommandSecurity(CommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple:
            valid = False
            errors = []
            for cs in cs_sequence:
                assert issubclass(cs, CommandSecurity)
                cs_item: CommandSecurity = cs(self.ctx, **self.options)
                vt, ct = await cs_item.checkSecurity(*args, **kwargs)
                valid = valid or vt
                if not vt:
                    errors.append(ct)
                if valid: # OR needs only one criteria to pass
                    break
            comment = None
            if not valid:
                comment = lng.LangSupportErrorGroup("MultiError", errors)
            return valid, comment

    return CombinedCommandSecurity

def AND(*cs_sequence: type[CommandSecurity]) -> type[CommandSecurity]:
    """ returns a CommandSecurity type that performs an AND between the checkSecurity method results of all the argument CommandSecurity types """
    class CombinedCommandSecurity(CommandSecurity):
        async def checkSecurity(self, *args, **kwargs) -> tuple:
            valid = True
            errors = []
            for cs in cs_sequence:
                assert issubclass(cs, CommandSecurity)
                cs_item: CommandSecurity = cs(self.ctx, **self.options)
                vt, ct = await cs_item.checkSecurity(*args, **kwargs)
                valid = valid and vt
                if not vt:
                    errors.append(ct)
                if not valid: # AND needs All criteria to pass
                    break
            comment = None
            if not valid:
                comment = lng.LangSupportErrorGroup("MultiError", errors)
            return valid, comment

    return CombinedCommandSecurity