from typing import AnyStr, Callable
from discord.ext import commands
import MySQLdb

from greedy_components import greedyBase as gb
from greedy_components import greedySecurity as gs

import lang.lang as lng
import support.utils as utils
import support.ghostDB as ghostDB

class GreedyGhostCog_Admin(gb.GreedyGhostCog):

    @commands.command(name = 'sql', brief='a bad idea.', help = "no.", hidden=True)
    @gs.command_security(gs.IsAdmin)
    async def sql(self, ctx: commands.Context, *args):
        query = " ".join(args)
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
            await self.bot.atSend(ctx, "```\n"+out+"```")        
        except MySQLdb.OperationalError as e:
            await self.bot.atSend(ctx, f"```Errore {e.args[0]}\n{e.args[1]}```")
        except MySQLdb.ProgrammingError as e:
            await self.bot.atSend(ctx, f"```Errore {e.args[0]}\n{e.args[1]}```")