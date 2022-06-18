import configparser, os
from discord.ext import commands
import discord

import support.ghostDB as ghostDB
import lang.lang as lng
import support.utils as utils

class BotException(Exception): # use this for 'known' error situations
    def __init__(self, msg):
        super(BotException, self).__init__(msg)

class GreedyCommandError(commands.CommandError):
    def __init__(self, message: str, formats: tuple = ()):
        """ Base command exception with language support. """
        super(GreedyCommandError, self).__init__(message, formats)

class GreedyErrorGroup(commands.CommandError):
    def __init__(self, message: str, errors: list):
        """ Group of errors with language support. """
        super(GreedyErrorGroup, self).__init__(message, errors)

class GreedyLanguageStringProvider(lng.LanguageStringProvider):
    def __init__(self, configuration: configparser.ConfigParser, db_manager: ghostDB.DBManager,  lang_dir : str = os.path.abspath(__file__)):
        super(GreedyLanguageStringProvider, self).__init__(lang_dir)
        self.config = configuration
        self.dbm = db_manager
    def getUserLanguage(self, userid: str) -> str:
        try:
            return self.dbm.getUserLanguage(userid)
        except ghostDB.DBException:
            return self.config['BotOptions']['default_language']

class GreedyContext(commands.Context):
    def __init__(self, **attrs):
        """ Custom context class that handles (and caches) some extra info about the invocation context, like whether the user is Registered, or their preferred language """
        super().__init__(**attrs)
        assert isinstance(self.bot, GreedyBot)
        self.bot: GreedyBot = self.bot # here just for type checks

        self.registeredUser = None
        self.userData = None
        self.language_id = None
    def _loadUserInfo(self):
        self.registeredUser, self.userData = self.bot.dbm.validators.getValidateBotUser(self.message.author.id).validate()
        if self.registeredUser:
            self.language_id = self.userData['langId']
        else:
            self.language_id = self.bot.config['BotOptions']['default_language']
    def getLID(self):
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

class GreedyBot(commands.Bot):
    """ Base class for bots """
    def __init__(self, configuration: configparser.ConfigParser, db_manager: ghostDB.DBManager, *args, **options):
        super(GreedyBot, self).__init__(*args, **options)
        self.config = configuration
        self.dbm = db_manager
        self.languageProvider = self._initLanguageProvider(configuration['BotOptions']['language_files_path'])
    def _initLanguageProvider(self, language_file_path: str) -> GreedyLanguageStringProvider:
        return GreedyLanguageStringProvider(self.config, self.dbm, language_file_path)
    async def validateDiscordMentionOrID(self, inp: str) -> utils.ValidatedString:
        vm, userid = utils.validateDiscordMention(inp)
        if vm:
            return vm, userid
        try:
            uid = int(inp)
            _ = await self.fetch_user(uid)
            return True, inp
        except:
            return False, ""
    def getLID(self, issuer: int) -> str:
        """ returns the Language ID for the specified user (if present), and the default language if the user is not registered
        Used only for sending messages in the correct language to logging users """
        return self.languageProvider.getUserLanguage(issuer)
    def getStringForUser(self, ctx: GreedyContext, string: str, *args) -> str:
        lid = ctx.getLID()
        return self.languageProvider.get(lid, string, *args)
    def atSend(self, ctx: commands.Context, msg: str):
        return ctx.send(f'{ctx.message.author.mention} {msg}')
    def atSendLang(self, ctx: commands.Context, msg: str, *args):
        translated = self.getStringForUser(ctx, msg, *args)
        return self.atSend(ctx, translated)
    async def logToDebugUser(self, msg: str):
        """ Sends msg to the debug user """
        debug_user = await self.fetch_user(int(self.config['Discord']['debuguser']))
        if debug_user != "":
            await debug_user.send(msg)
        else:
            print(msg)
    def formatException(self, ctx: GreedyContext, exc: Exception) -> str:
        lid = ctx.getLID()
        formatted_error = ""
        if isinstance(exc, GreedyErrorGroup):
            formatted_error = "\n".join(list(map(lambda x: self.formatException(ctx, x), exc.args[1]))) # this is recursive because GreedyErrorGroup can be used to stack a bunch of exceptions nested on multiple layers
        else:
            formatted_error = self.languageProvider.formatException(lid, exc)
        return formatted_error
    # overrides
    async def get_context(self, message, *, cls=...):
        """ overrides context creation to calculate some extra info """
        return await super().get_context(message, cls=GreedyContext)

class GreedyGhost(GreedyBot):
    """ Functionality specific to Greedy Ghost """
    def getGuildActivationMap(self):
        authmap = {}
        for guild in self.guilds:
            ig, guild_db = self.dbm.validators.getValidateGuild(guild.id).validate()
            if ig:
                authmap[guild.id] = guild_db["authorized"]
        return authmap

    def isMemberAllowedInBot(self, member: discord.Member, guild_map: dict = None):
        """ Checks wether a member is allowed to stay tracked by the bot. 
        The guild_map parameter is the result of the GreedyGhost.getGuildActivationMap() method.
        It is built as a dict of {int -> bool}, mapping guild ids to activation status.
        If omitted, the permission map will be computed by this method, it can be passed externally to check multiple users without rebuilding the guild permission map every time """
        if member.id == self.user.id: # Bot is always allowed to be in the DB
            return True
        if guild_map is None:
            guild_map = self.getGuildActivationMap()
        allowed = False
        for guild in self.guilds:
            if guild.get_member(member.id):
                if guild_map[guild.id]:
                    allowed = True
                    break
        return allowed

    def checkAndRemoveUser(self, member: discord.Member, guild_map: dict = None):
        """ checks wether a member is allowed to stay tracked by the bot, and removes them if not.
        The guild_map parameter is the result of the GreedyGhost.getGuildActivationMap() method.
        It is built as a dict of {int -> bool}, mapping guild ids to activation status.
        If omitted, the permission map will be computed by this method, it can be passed externally to check multiple users without rebuilding the guild permission map every time """
        if not self.isMemberAllowedInBot(member, guild_map):
            self.dbm.tryRemoveUser(member.id, self.user.id)
    
    async def checkAndJoinGuild(self, guild: discord.Guild):
        ig, _ = self.dbm.validators.getValidateGuild(guild.id).validate()
        if not ig: # most of the time this is the case
            self.dbm.registerGuild(guild.id, guild.name, False)
            await self.logToDebugUser(f"joined guild '{guild.name}', id: {guild.id}")
            return True
        return False

class GreedyGhostCog(commands.Cog): 
    def __init__(self, bot: GreedyGhost):
        self.bot = bot