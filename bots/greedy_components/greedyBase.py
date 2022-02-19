import configparser, os
from distutils.log import error
from discord.ext import commands

import support.ghostDB as ghostDB
import lang.lang as lng
import support.utils as utils

class BotException(Exception): # use this for 'known' error situations
    def __init__(self, msg):
        super(BotException, self).__init__(msg)

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

class GreedyGhost(commands.Bot):
    def __init__(self, configuration: configparser.ConfigParser, db_manager: ghostDB.DBManager, *args, **options):
        super(GreedyGhost, self).__init__(*args, **options)
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
        """ returns the Language ID for the specified user (if present), and the default language if the user is not registered """
        return self.languageProvider.getUserLanguage(issuer)
    def getStringForUser(self, ctx: commands.Context, string: str, *args) -> str:
        issuer = ctx.message.author.id
        lid = self.getLID(issuer)
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
    def getBotExceptionLang(self, ctx: commands.Context, error_str: str, *args) -> BotException:
        """ Creates a BotException object that contains a translated error string """
        return BotException(self.getStringForUser(ctx, error_str, *args))

class GreedyGhostCog(commands.Cog): 
    def __init__(self, bot: GreedyGhost):
        self.bot = bot