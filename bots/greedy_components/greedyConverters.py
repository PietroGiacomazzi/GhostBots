
from typing import Any
from greedy_components import greedyBase as gb
from discord.ext.commands import Converter, Context, UserConverter, UserNotFound

from support.utils import validate_id

class CharacterConverter(Converter):
    """Convert the given character id into a character object."""

    async def convert(self, ctx: Context, argument: str) -> Any:
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.getCharacter(argument)

class ChronicleConverter(Converter):
    """Convert the given character id into a character object."""

    async def convert(self, ctx: Context, argument: str) -> Any:
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.getChronicle(argument)

class RegisteredUserConverter(UserConverter):
    """Convert the given user into a registered bot user"""

    async def convert(self, ctx: Context, argument: str) -> Any:
        try:
            user = await super().convert(ctx, argument)
        except UserNotFound:
            raise gb.GreedyCommandError('string_error_usernotfound_discord', (argument,))
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.getUser(user.id)

class StorytellerConverter(RegisteredUserConverter):
    """Convert the given user into a storyteller"""

    async def convert(self, ctx: Context, argument: str) -> Any:
        user = await super().convert(ctx, argument)
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.getStoryTeller(user['userid'])

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
        return bot.dbm.getTraitType(argument.lower())

class NoYesConverter(Converter):
    """ Converts all accepted true/false inputs to a boolean """

    async def convert(self, ctx: Context, argument: str) -> bool:
        stdarg = argument.lower()
        std = stdarg in ['y', 's', '1', 'true']
        if not std and not stdarg in ['n', '0', 'false']:
            raise gb.GreedyCommandError("{} non è un'opzione valida", (stdarg,))
        return std

class LanguageConverter(Converter):
    """ Validates a language id """

    async def convert(self, ctx: Context, argument: str) -> bool:
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.getLanguage(argument.upper())

class TraitConverter(Converter):
    """ Validates a language id """

    async def convert(self, ctx: Context, argument: str) -> bool:
        bot: gb.GreedyGhost = ctx.bot
        return bot.dbm.getTraitInfo(argument.lower())


# numeric stuff

class TrackerTypeConverter(Converter):
    """ Validates string a tracker type """

    async def convert(self, ctx: Context, argument: str) -> int:
        error = gb.GreedyCommandError("{} non è tracker valido!", (argument,))
        tracktype = 0
        try:
            tracktype = int(argument)
            if not tracktype in [0, 1, 2, 3]: # TODO dehardcode
                raise error
        except ValueError:
            raise error
        return tracktype