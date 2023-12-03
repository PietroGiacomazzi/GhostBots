from typing import Any
from greedy_components import greedyBase as gb
from discord.ext.commands import Converter, Context, UserConverter, UserNotFound
import logging

from support.utils import GAMESYSTEMS_LIST
from support.utils import validate_id

_log = logging.getLogger(__name__)

class CharacterConverter(Converter):
    """Convert the given character id into a character object."""

    async def convert(self, ctx: Context, argument: str) -> Any:
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.validators.getValidateCharacter(argument).get()

class ChronicleConverter(Converter):
    """Convert the given character id into a character object."""

    async def convert(self, ctx: Context, argument: str) -> Any:
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.validators.getValidateChronicle(argument).get()

class RegisteredUserConverter(UserConverter):
    """Convert the given user into a registered bot user"""

    async def convert(self, ctx: gb.GreedyContext, argument: str) -> Any:
        try:
            user = await super().convert(ctx, argument)
        except UserNotFound:
            raise gb.GreedyCommandError('string_error_usernotfound_discord', (argument,))
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.validators.getValidateBotUser(user.id).get()

class StorytellerConverter(RegisteredUserConverter):
    """Convert the given user into a storyteller"""

    async def convert(self, ctx: Context, argument: str) -> Any:
        user = await super().convert(ctx, argument)
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.validators.getValidateBotStoryTeller(user['userid']).get()

class GreedyShortIdConverter(Converter):
    """ Validates the input string as having no spaces """

    async def convert(self, ctx: Context, argument: str) -> Any:
        if validate_id(argument):
            return argument.lower()
        else:
            raise gb.GreedyCommandError('string_error_invalid_shortid', (argument,))

class TraitTypeConverter(Converter):
    """ Converts string into a traitType object """

    async def convert(self, ctx: Context, argument: str) -> Any:
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.validators.getValidateTraitType(argument.lower()).get()

class NoYesConverter(Converter):
    """ Converts all accepted true/false inputs to a boolean """

    async def convert(self, ctx: Context, argument: str) -> bool:
        stdarg = argument.lower()
        std = stdarg in ['y', 's', '1', 'true']
        if not std and not stdarg in ['n', '0', 'false']:
            raise gb.GreedyCommandError("'{}' non è un'opzione valida", (stdarg,))
        return std

class LanguageConverter(Converter):
    """ Validates a language id """

    async def convert(self, ctx: Context, argument: str) -> bool:
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.validators.getValidateLanguage(argument.upper()).get()

class TraitConverter(Converter):
    """ Validates a trait id NOTE: LANGUAGE NOT YET SUPPORTED"""
    #TODO language support!
    async def convert(self, ctx: Context, argument: str) -> bool:
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.validators.getValidateTrait(argument.lower()).get()

class GameSystemConverter(Converter):
    """ Validates a gamesystem identifier """
    async def convert(self, ctx: Context, argument):
        if not argument in GAMESYSTEMS_LIST:
            raise gb.GreedyCommandError("string_error_invalid_rollsystem", (argument,))
        #return getRollSystem(argument)
        return argument

# numeric stuff

class TrackerTypeConverter(Converter):
    """ Validates a tracker type """

    async def convert(self, ctx: Context, argument: str) -> int:
        error = gb.GreedyCommandError("'{}' non è tracker valido!", (argument,))
        tracktype = 0
        try:
            tracktype = int(argument)
            if not tracktype in [0, 1, 2, 3]: # TODO dehardcode
                raise error
        except ValueError:
            raise error
        return tracktype