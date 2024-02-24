import os, logging
import sys
from typing import Any

_log = logging.getLogger(__name__)

GAMESYSTEMS_LIST = ("GENERAL", "STORYTELLER_SYSTEM", "V20_VTM_HOMEBREW_00", "V20_VTM_VANILLA") #, "DND_5E")

# TYPES
ValidatedString = tuple #[bool, str]
ValidatedIntSeq = tuple #[int, int]

INFINITY = float("inf")

hurt_levels_vampire = [
    (0, "hurt_levels_vampire_unharmed"),
    (0, "hurt_levels_vampire_bruised"),
    (-1, "hurt_levels_vampire_hurt"),
    (-1, "hurt_levels_vampire_injured"),
    (-2, "hurt_levels_vampire_wounded"),
    (-2, "hurt_levels_vampire_mauled"),
    (-5, "hurt_levels_vampire_crippled"),
    (-INFINITY, "hurt_levels_vampire_incapacitated"),
]

def get_secret(secret_name: str, secret_path: str):
    with open(os.path.join(secret_path, secret_name), "r") as f:
        return f.read().strip()

def parseHealth(trait, levels_list = hurt_levels_vampire):
    if trait['cur_value'] <= 0:
        return levels_list[0], 'B' # 'Non hai ancora inizializzato la tua salute!'
    levels = len(levels_list) - 1 

    hs = trait['text_value']
    hs = hs + (" "*(trait['cur_value']-len(hs))) + ("B"*(max(0,levels-trait['cur_value'])))

    columns = len(hs) // levels 
    extra = len(hs) % levels
    width = columns + (extra > 0)
    cursor = 0
    hurt_level = 0
    health_lines = []
    for i in range(levels):
        if hs[cursor] != " ":
            hurt_level = i+1
        if i < extra:
            health_lines.append(hs[cursor:cursor+width])#prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], hs[cursor:cursor+width])))
            cursor += width
        else:
            health_lines.append(hs[cursor:cursor+columns]+"B"*(extra > 0)) #prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], hs[cursor:cursor+columns]+"B"*(extra > 0))))
            cursor += columns
    #return hurt_levels[hurt_level] +"\n"+ prettytext
    return levels_list[hurt_level], health_lines

def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)

def validateDiscordMention(mention : str) -> tuple:
    if not (mention.startswith("<@!") and mention.endswith(">")): 
        return False, ""
    return  True, mention[3:-1]

def merge(d1: dict, d2: dict, merge_fn=lambda x,y:y):
    """
    Merges two dictionaries, non-destructively, combining 
    values on duplicate keys as defined by the optional merge
    function.  The default behavior replaces the values in d1
    with corresponding values in d2.  (There is no other generally
    applicable merge strategy, but often you'll have homogeneous 
    types in your dicts, so specifying a merge technique can be 
    valuable.)

    Examples:

    >>> d1
    {'a': 1, 'c': 3, 'b': 2}
    >>> merge(d1, d1)
    {'a': 1, 'c': 3, 'b': 2}
    >>> merge(d1, d1, lambda x,y: x+y)
    {'a': 2, 'c': 6, 'b': 4}

    """
    result = dict(d1)
    for k,v in d2.items():
        if k in result:
            result[k] = merge_fn(result[k], v)
        else:
            result[k] = v
    return result

def validate_forbidden_chars(string: str, forbidden_chars: list) -> bool:
    return sum(map(lambda x: string.count(x), forbidden_chars)) == 0

def validate_id(string: str) -> bool:
    return validate_forbidden_chars(string, [" ", "+", "-"])

def prettyHighlightError(args: list, i: int, width : int = 3) -> str:
    return " ".join(list(args[max(0, i-width):i]) + ['**'+args[i]+'**'] + list(args[min(len(args), i+1):min(len(args), i+width)]))

def string_chunks(string: str, max_chunk_size: int) -> list[str]:
    # split into lines, if a line is larger than max_chunk_size, slice it
    lines = string.split('\n')
    processed_lines = []
    for line in lines:
        if len(line) > max_chunk_size:
            processed_lines.extend([line[i:i+max_chunk_size] for i in range(0, len(line), max_chunk_size)])
        else:
            processed_lines.append(line)

    chunks = [processed_lines[0]]
    for line in processed_lines[1:]:
        temp = chunks[-1]+"\n"+line
        if len(temp) > max_chunk_size:
            chunks.append(line)
        else:
            chunks[-1] = temp

    return chunks

#discord text formatting functions
def discord_text_format_mono(string: str, language = "") -> str:
    """ language can be empty, Markdown, Python... """
    return f'```{language}\n{string}\n```'

# logging setup, courtesy of https://github.com/Rapptz/discord.py

def is_docker() -> bool:
    path = '/proc/self/cgroup'
    return os.path.exists('/.dockerenv') or (os.path.isfile(path) and any('docker' in line for line in open(path)))


def stream_supports_colour(stream: Any) -> bool:
    # Pycharm and Vscode support colour in their inbuilt editors
    if 'PYCHARM_HOSTED' in os.environ or os.environ.get('TERM_PROGRAM') == 'vscode':
        return True

    is_a_tty = hasattr(stream, 'isatty') and stream.isatty()
    if sys.platform != 'win32':
        # Docker does not consistently have a tty attached to it
        return is_a_tty or is_docker()

    # ANSICON checks for things like ConEmu
    # WT_SESSION checks if this is Windows Terminal
    return is_a_tty and ('ANSICON' in os.environ or 'WT_SESSION' in os.environ)

class _ColourFormatter(logging.Formatter):

    # ANSI codes are a bit weird to decipher if you're unfamiliar with them, so here's a refresher
    # It starts off with a format like \x1b[XXXm where XXX is a semicolon separated list of commands
    # The important ones here relate to colour.
    # 30-37 are black, red, green, yellow, blue, magenta, cyan and white in that order
    # 40-47 are the same except for the background
    # 90-97 are the same but "bright" foreground
    # 100-107 are the same as the bright ones but for the background.
    # 1 means bold, 2 means dim, 0 means reset, and 4 means underline.

    LEVEL_COLOURS = [
        (logging.DEBUG, '\x1b[40;1m'),
        (logging.INFO, '\x1b[34;1m'),
        (logging.WARNING, '\x1b[33;1m'),
        (logging.ERROR, '\x1b[31m'),
        (logging.CRITICAL, '\x1b[41m'),
    ]

    FORMATS = {
        level: logging.Formatter(
            f'\x1b[30;1m%(asctime)s\x1b[0m {colour}%(levelname)-8s\x1b[0m \x1b[35m%(name)s\x1b[0m %(message)s',
            '%Y-%m-%d %H:%M:%S',
        )
        for level, colour in LEVEL_COLOURS
    }

    def format(self, record):
        formatter = self.FORMATS.get(record.levelno)
        if formatter is None:
            formatter = self.FORMATS[logging.DEBUG]

        # Override the traceback to always print in red
        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f'\x1b[31m{text}\x1b[0m'

        output = formatter.format(record)

        # Remove the cache layer
        record.exc_text = None
        return output

def setup_logging(
    handler: logging.Handler = None,
    formatter: logging.Formatter = None,
    level: int = logging.INFO,
    root: bool = True,
) -> logging.Logger:
    """A helper function to setup logging.

    This is superficially similar to :func:`logging.basicConfig` but
    uses different defaults and a colour formatter if the stream can
    display colour.

    Parameters
    -----------
    handler: :class:`logging.Handler`
        The log handler to use for the library's logger.

        The default log handler if not provided is :class:`logging.StreamHandler`.
    formatter: :class:`logging.Formatter`
        The formatter to use with the given log handler. If not provided then it
        defaults to a colour based logging formatter (if available). If colour
        is not available then a simple logging formatter is provided.
    level: :class:`int`
        The default log level for the library's logger. Defaults to ``logging.INFO``.
    root: :class:`bool`
        Whether to set up the root logger rather than the library logger.
        Unlike the default for :class:`~discord.Client`, this defaults to ``True``.
    """


    if handler is None:
        handler = logging.StreamHandler()

    if formatter is None:
        if isinstance(handler, logging.StreamHandler) and stream_supports_colour(handler.stream):
            formatter = _ColourFormatter()
        else:
            dt_fmt = '%Y-%m-%d %H:%M:%S'
            formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')

    if root:
        logger = logging.getLogger()
    else:
        library, _, _ = __name__.partition('.')
        logger = logging.getLogger(library)

    handler.setFormatter(formatter)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger