
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

def parseHealth(trait, levels_list = hurt_levels_vampire):
    if trait['max_value'] <= 0:
        return 'Non hai ancora inizializzato la tua salute!'
    hs = trait['text_value']
    hs = hs + (" "*(trait['max_value']-len(hs)))
    levels = len(levels_list) - 1 
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

def validate_forbidden_chars(string: str, forbidden_chars: list) -> bool:
    return sum(map(lambda x: string.count(x), forbidden_chars)) == 0

def validate_id(string: str) -> bool:
    return validate_forbidden_chars(string, [" ", "+", "-"])

def prettyHighlightError(args: list, i: int, width : int = 3) -> str:
    return " ".join(list(args[max(0, i-width):i]) + ['**'+args[i]+'**'] + list(args[min(len(args), i+1):min(len(args), i+width)]))

#discord text formatting functions
def discord_text_format_mono(string: str, language = "") -> str:
    """ language can be empty, Markdown, Python... """
    return f'```{language}\n{string}\n```'