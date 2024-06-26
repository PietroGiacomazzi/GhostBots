import logging
from configparser import ConfigParser
from support import ghostDB
import lang.lang as lng

_log = logging.getLogger(__name__)

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
    def getActiveCharacter(self):
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
    
    def getRunningSession(self):
        channelid = self.getChannelId()
        if channelid != 0:
            return self.getDBManager().validators.getValidateRunningSession(self.getChannelId()).get()
        else: 
            return self.getDBManager().validators.getValidateAnyRunningSessionForCharacter(self.getActiveCharacter()[ghostDB.FIELDNAME_PLAYERCHARACTER_CHARACTERID]).get()


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

        if not (guildid is None or guildid == 0):
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

        if guildid is None or guildid == 0:
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
    class IsChronicleStoryteller(ParametrizedCommandSecurity):
        def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
            issuer_id = str(self.ctx.getUserId())  
            chronicle = self.getParameter(target_chronicle, args, kwargs)
            chronid = chronicle['id']
            st, _ = self.ctx.getDBManager().isChronicleStoryteller(issuer_id, chronid)
            valid = st
            comment = None if valid else SecurityCheckException("L'Utente non è Storyteller della cronaca {}", (chronicle['name'],)) 
            return valid, comment
    return IsChronicleStoryteller

def genIsSelf(optional_target_user):
    """ Passes if the command is issued by someone that is targeting themselves """
    class IsSelf(ParametrizedCommandSecurity):
        def checkSecurity(self, *args, **kwargs) -> tuple: #[bool, Any]:
            issuer_id = str(self.ctx.getUserId())  
            target_usr = self.tryGetParameter(optional_target_user, args, kwargs, issuer_id)
            target_usr_id = target_usr['userid']
            valid =  target_usr_id == issuer_id
            return valid, None if valid else SecurityCheckException("Non puoi indicare una persona diversa da te") 
    return IsSelf

def genIsCharacterStoryTeller(target_character):
    """ Passes if the command is issued by a Storyteller that is associated to a chronicle in which this character plays in """
    class IsCharacterStoryTeller(ParametrizedCommandSecurity):
        def checkSecurity(self, *command_args, **command_kwargs) -> tuple: #[bool, Any]:
            issuer = str(self.ctx.getUserId())  
            character = self.getParameter(target_character, command_args, command_kwargs)
            charid = character['id']

            st, _ = self.ctx.getDBManager().isStorytellerForCharacter(issuer, charid)
                   
            comment = None if st else SecurityCheckException("Non hai il ruolo di storyteller per questo personaggio") 
            return st, comment
    return IsCharacterStoryTeller

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

def genIsCharacterLinked(target_character):
    """ Passes if the the character is linked to any chronicle """
    class IsCharacterLinked(ParametrizedCommandSecurity):
        def checkSecurity(self, *command_args, **command_kwargs) -> tuple: #[bool, Any]:
            character = self.getParameter(target_character, command_args, command_kwargs)
            charid = character['id']

            cl, _ = self.ctx.getDBManager().isCharacterLinked(charid)
                    
            comment = None if cl else SecurityCheckException("Il personaggio non deve essere collegato ad una cronaca") 
            return cl, comment
    return IsCharacterLinked

def genIsAnySessionRunningForCharacter(target_character):
    """ Passes if the the character is linked to an active game session  """
    class IsSessionRunningforCharacter(ParametrizedCommandSecurity):
        def checkSecurity(self, *command_args, **command_kwargs) -> tuple: #[bool, Any]:
            character = self.getParameter(target_character, command_args, command_kwargs)
            charid = character['id']
            return self.ctx.getDBManager().validators.getValidateAnyRunningSessionForCharacter(charid).validate()
    return IsSessionRunningforCharacter

def genIsSessionRunningForCharacterHere(target_character):
    """ Passes if the the character is linked to an active game session in the current channel """
    class IsSessionRunningforCharacter(ParametrizedCommandSecurity):
        def checkSecurity(self, *command_args, **command_kwargs) -> tuple: #[bool, Any]:
            character = self.getParameter(target_character, command_args, command_kwargs)
            charid = character['id']

            sa, _ = self.ctx.getDBManager().isSessionActiveForCharacter(charid, self.ctx.getChannelId())
            
            comment = None if sa else SecurityCheckException("Il personaggio deve avere una sessione aperta in questo canale") 
            return sa, comment
    return IsSessionRunningforCharacter

def OR(*cs_sequence: type[CommandSecurity]) -> type[CommandSecurity]:
    """ returns a CommandSecurity type that performs an OR between the checkSecurity method results of all the argument CommandSecurity types """
    class CombinedCommandSecurityOR(CommandSecurity):
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

    return CombinedCommandSecurityOR

def AND(*cs_sequence: type[CommandSecurity]) -> type[CommandSecurity]:
    """ returns a CommandSecurity type that performs an AND between the checkSecurity method results of all the argument CommandSecurity types """
    class CombinedCommandSecurityAND(CommandSecurity):
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

    return CombinedCommandSecurityAND

def NOT(cs_to_negate: type[CommandSecurity]) -> type[CommandSecurity]:
    """ returns a CommandSecurity type that passes if the parameter does NOT paass its checkSecurity method """
    class CombinedCommandSecurityNOT(CommandSecurity):
        def checkSecurity(self, *args, **kwargs) -> tuple:
            assert issubclass(cs_to_negate, CommandSecurity)
            cs_item: CommandSecurity = cs_to_negate(self.ctx, **self.options)

            vt, _ = cs_item.checkSecurity(*args, **kwargs)

            valid = not vt
            comment = None
            if not valid:
                comment =  SecurityCheckException(f'Il controllo {cs_to_negate} non doveva passare') # TODO have some sort of string in each CommandSecurity that can be retireved
                
            return valid, comment

    return CombinedCommandSecurityNOT

# PREMADE BLOCKS:

genCanEditCharacterAnyChannel = lambda target_character:  OR(genIsCharacterStoryTeller(target_character), AND(genIsCharacterPlayer(target_character), OR(NOT(genIsCharacterLinked(target_character)), genIsAnySessionRunningForCharacter(target_character)) )) 
genCanEditCharacterThisChannel = lambda target_character:  OR(genIsCharacterStoryTeller(target_character), AND(genIsCharacterPlayer(target_character), OR(NOT(genIsCharacterLinked(target_character)), genIsSessionRunningForCharacterHere(target_character))))
genCanViewCharacter = lambda target_character:  OR(genIsCharacterStoryTeller(target_character), genIsCharacterPlayer(target_character))

# PREMADE FULL PERMISSIONS (BOT):

canEditCharacter_BOT = lambda target_character: OR(IsAdmin, AND( OR(IsActiveOnGuild, IsPrivateChannelWithRegisteredUser), genCanEditCharacterThisChannel(target_character)))

# PREMADE FULL PERMISSIONS (WEB):

canEditGeneralMacro = OR(IsAdmin, IsStoryteller)
canEditCharacter_WEB = lambda target_character: OR(IsAdmin, AND( IsUser, genCanEditCharacterAnyChannel(target_character)))