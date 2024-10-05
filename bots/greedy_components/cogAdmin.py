from typing import AnyStr, Callable
from discord.ext import commands
import MySQLdb, logging

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB
import support.security as sec

_log = logging.getLogger(__name__)

class GreedyGhostCog_Admin(gb.GreedyGhostCog):

    @commands.command(name = 'sql', brief='a bad idea.', help = "no.", hidden=True)
    @commands.before_invoke(gs.command_security(sec.IsAdmin))
    async def sql(self, ctx: commands.Context, *args):
        query = " ".join(args)
        _log.info(f"SQL QUERY FROM USER {ctx.message.author}: {query}")
        try:
            query_result_raw = self.bot.dbm.db.query(query)
            # check for integer -> delete statements return an int (and update statements aswell?)
            if isinstance(query_result_raw, int):
                await self.bot.atSend(ctx, f"righe interessate: {query_result_raw}")
                return
            
            query_result = query_result_raw.list()
            if len(query_result) == 0:
                await self.bot.atSend(ctx, "nessun risultato")
                return
            
            column_names = list(query_result[0].keys())
            col_widths = list(map(len, column_names))
            for r in query_result:
                for i in range(len(column_names)):
                    length = len(str(r[column_names[i]]))
                    if col_widths[i] < length:
                        col_widths[i] = length
            table_delim = '+' + '+'.join(map(lambda x: '-'*(x+2), col_widths)) + '+'
            out = table_delim+"\n|"
            for i in range(len(column_names)):
                out += " "+column_names[i]+" "*(col_widths[i]-len(column_names[i]))+" |"
            out += "\n"+table_delim+"\n"
            for r in query_result:
                out += "|"
                for i in range(len(column_names)):
                    data = str(r[column_names[i]])
                    out += " "+data+" "*(col_widths[i]-len(data))+" |"
                out += "\n"
            out += table_delim

            if len(out) > int(self.bot.config['Discord']['max_message_length_bot']):
                raise gb.GreedyCommandError(f'Result too long! ({len(out)})')
            
            for chunk in utils.string_chunks(out, int(self.bot.config['Discord']['max_message_length_discord'])-100):
                await ctx.send(utils.discord_text_format_mono(chunk))
       
        except MySQLdb.OperationalError as e:
            _log.warning(f"SQL QUERY FROM USER {ctx.message.author}: Error {e.args[0]} -  {e.args[1]}")
            await self.bot.atSend(ctx, f"```Error {e.args[0]}\n{e.args[1]}```")
        except MySQLdb.ProgrammingError as e:
            _log.warning(f"SQL QUERY FROM USER {ctx.message.author}: Error {e.args[0]} -  {e.args[1]}")
            await self.bot.atSend(ctx, f"```Error {e.args[0]}\n{e.args[1]}```")