from configparser import ConfigParser
from support import ghostDB
import lang.lang as lng

class SecurityCheckException(lng.LangSupportException):
    pass

class MissingParameterException(lng.LangSupportException):
    pass

class SecuritySetupError(lng.LangSupportException):
    pass

class InputValidationError(lng.LangSupportException):
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
    def getDefaultLanguageId(self) -> str:
        raise NotImplementedError()
    def getAppConfig(self) -> ConfigParser:
        raise NotImplementedError()
    def getLanguageProvider(self) -> lng.LanguageStringProvider:
        raise NotImplementedError()
    def getMessageContents(self) -> str:
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

class InputValidator:
    def __init__(self, ctx: SecurityContext):
        self.ctx = ctx
    def validateInteger(self, param) -> int:
        try:
            return int(param)
        except ValueError:
            raise InputValidationError("string_error_not_an_integer", (param,))

class CommandSecurity:
    def __init__(self, ctx: SecurityContext, **kwargs):
        self.ctx = ctx
        self.options = kwargs
    def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        """ performs the security check """
        raise NotImplementedError("Base command security does not check anything!")

class NoCheck(CommandSecurity):
    """ Always passes """
    def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        return True, None

class IsUser(CommandSecurity):
    """ Passes if the command is issued by a tracked user """
    def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        return self.ctx.validateUserInfo()

class IsActiveOnGuild(CommandSecurity):
    """ Passes if the command is issued in an authorized Guild """
    def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
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
    def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        guildid = self.ctx.getGuildId()

        valid, comment = (False, SecurityCheckException("string_error_server_not_authorized"))

        if guildid is None:
            valid, comment =  self.ctx.validateUserInfo()
        
        return valid, comment 

class IsStoryteller(CommandSecurity):
    """ Passes if the command is issued by a Storyteller """
    def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer = str(self.ctx.getUserId())
        return self.ctx.getDBManager().validators.getValidateBotStoryTeller(issuer).validate()

class IsAdmin(CommandSecurity):
    """ Passes if the command is issued by a Bot Admin """
    def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
        issuer = str(self.ctx.getUserId())
        return self.ctx.getDBManager().validators.getValidateBotAdmin(issuer).validate()

class CanEditRunningSession(CommandSecurity): # this needs to exist separately from genIsAdminOrChronicleStoryteller because the chronicle is not available in the command parameters, but rather is a property of the current channel
    """ Passes if the command is issued by an owner of the currently running session of the channel """
    def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
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
    """ Abstract class that allows building CommandSecurity objects that can acces the command's parameters """
    def getParameter(self, param_idx, args, kwargs):
        try:
            return args[param_idx]
        except (IndexError, TypeError) as e: # TypeError gets issued when a string is used as an index for a tuple
            try:
                return kwargs[param_idx]
            except KeyError:
                raise MissingParameterException('string_error_security_option_required', (param_idx,))  
    def tryGetParameter(self, param_idx, args, kwargs, fallback):
        try:
            value = self.getParameter(param_idx, args, kwargs)
            if not value == None:
                return value
            else:
                return fallback
        except MissingParameterException:
            return fallback

def genIsChronicleStoryteller(target_chronicle):
    """ Passes if the command is issued by a Storyteller that can control target_chronicle """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
            issuer_id = str(self.ctx.getUserId())  
            chronicle = self.getParameter(target_chronicle, args, kwargs)
            chronid = chronicle['id']
            st, _ = self.ctx.getDBManager().isChronicleStoryteller(issuer_id, chronid)
            valid = st
            comment = None if valid else SecurityCheckException("L'Utente non è Storyteller della cronaca {}", (chronicle['name'],)) 
            return valid, comment
    return GeneratedCommandSecurity

def genIsSelf(optional_target_user):
    """ Passes if the command is issued by someone that is targeting themselves """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
            issuer_id = str(self.ctx.getUserId())  
            target_usr = self.tryGetParameter(optional_target_user, args, kwargs, issuer_id)
            target_usr_id = target_usr['userid']
            valid =  target_usr_id == issuer_id
            return valid, None if valid else SecurityCheckException("Non puoi indicare una persona diversa da te") 
    return GeneratedCommandSecurity

def genIsCharacterStoryTeller(target_character):
    """ Passes if the command is issued by a Storyteller that is associated to a chronicle in which this character plays in """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        def checkSecurity(self, *command_args, **command_kwargs) -> tuple: #[bool, Any]:
            issuer = str(self.ctx.getUserId())  
            character = self.getParameter(target_character, command_args, command_kwargs)
            charid = character['id']

            st, _ = self.ctx.getDBManager().isStorytellerForCharacter(issuer, charid)
                   
            comment = None if st else SecurityCheckException("Non hai il ruolo di storyteller per questo personaggio") 
            return st, comment
    return GeneratedCommandSecurity

def genIsCharacterPlayer(target_character):
    """ Passes if the command is issued by the character's player/owner """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        def checkSecurity(self, *command_args, **command_kwargs) -> tuple: #[bool, Any]:
            issuer = str(self.ctx.getUserId())  
            character = self.getParameter(target_character, command_args, command_kwargs)
            owner = character['owner']

            co = owner == issuer          

            comment = None if co else SecurityCheckException("Questo personaggio non è assegnato a te") 
            return co, comment
    return GeneratedCommandSecurity

def genIsSessionRunningforCharacter(target_character):
    """ Passes if the the character is linked to an active game session OR the character is not linked to any chronicle """
    class GeneratedCommandSecurity(ParametrizedCommandSecurity):
        def checkSecurity(self, *command_args, **command_kwargs) -> tuple: #[bool, Any]:
            character = self.getParameter(target_character, command_args, command_kwargs)
            charid = character['id']

            #1: unlinked
            cl, _ = self.ctx.getDBManager().isCharacterLinked(charid)
            #2 active session
            sa, _ = self.ctx.getDBManager().isSessionActiveForCharacter(charid, self.ctx.getChannelId())
            
            ce = (not cl) or sa            

            comment = None if ce else SecurityCheckException("Il personaggio deve avere una sessione aperta oppure non essere collegato ad una cronaca") 
            return ce, comment
    return GeneratedCommandSecurity

def OR(*cs_sequence: type[CommandSecurity]) -> type[CommandSecurity]:
    """ returns a CommandSecurity type that performs an OR between the checkSecurity method results of all the argument CommandSecurity types """
    class CombinedCommandSecurity(CommandSecurity):
        def checkSecurity(self, *args, **kwargs) -> tuple:
            valid = False
            errors = []
            for cs in cs_sequence:
                assert issubclass(cs, CommandSecurity)
                cs_item: CommandSecurity = cs(self.ctx, **self.options)
                vt, ct = cs_item.checkSecurity(*args, **kwargs)
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
        def checkSecurity(self, *args, **kwargs) -> tuple:
            valid = True
            errors = []
            for cs in cs_sequence:
                assert issubclass(cs, CommandSecurity)
                cs_item: CommandSecurity = cs(self.ctx, **self.options)
                vt, ct = cs_item.checkSecurity(*args, **kwargs)
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

# PREMADE BLOCKS:

genCanEditCharacter = lambda target_character:  OR(genIsCharacterStoryTeller(target_character), AND(genIsCharacterPlayer(target_character), genIsSessionRunningforCharacter(target_character)))
genCanViewCharacter = lambda target_character:  OR(genIsCharacterStoryTeller(target_character), genIsCharacterPlayer(target_character))

# PREMADE FULL PERMISSIONS (BOT):

canEditCharacter_BOT = lambda target_character: OR(IsAdmin, AND( OR(IsActiveOnGuild, IsPrivateChannelWithRegisteredUser), genCanEditCharacter(target_character)))

# PREMADE FULL PERMISSIONS (WEB):

canEditGeneralMacro = OR(IsAdmin, IsStoryteller)