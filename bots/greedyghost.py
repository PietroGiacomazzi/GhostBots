#!/usr/bin/env python3

import os, sys, configparser, discord, logging

# init debugging
import debugpy
debugpy.listen(("0.0.0.0", 5678))

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

import support.ghostDB as ghostDB
import support.utils as utils
import lang.lang as lng

import greedy_components.greedyBase as gb

import greedy_components.cogAdmin as cogAdmin
import greedy_components.cogBasic as cogBasic
import greedy_components.cogGMadm as cogGMadm
import greedy_components.cogLang as cogLang
import greedy_components.cogMisc as cogMisc
import greedy_components.cogRoller as cogRoller
import greedy_components.cogSession as cogSession
import greedy_components.cogPCmgmt as cogPCmgmt
import greedy_components.cogPCmod as cogPCmod
import greedy_components.cogTasks as cogTasks
import greedy_components.cogSysRoller as cogSysRoller


if __name__ == "__main__":
    _log = utils.setup_logging(root = True)

    # load bot configuration
    if len(sys.argv) == 1:
        _log.error("Specify a configuration file!")
        sys.exit(1)

    print(f"Working directory: {dname}")
    if not os.path.exists(sys.argv[1]):
        _log.error(f"The configuration file {sys.argv[1]} does not exist!")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(sys.argv[1])

    # setup db
    database_manager = ghostDB.DBManager(config['Database'])

    # setup auth and permission stuff
    TOKEN = config['Discord']['token']

    # setup intents
    intents = discord.Intents.default()
    intents.members = True
    intents.messages = True
    intents.guilds = True

    botcmd_prefixes = ['.'] # all prefixes need to be length 1, some code relies on it (on_command_error for example)

    # create bot client
    bot = gb.GreedyGhost(config, database_manager, botcmd_prefixes, intents = intents)

    #add all cogs
    bot.add_cog(cogAdmin.GreedyGhostCog_Admin(bot))
    bot.add_cog(cogBasic.GreedyGhostCog_Basic(bot))
    bot.add_cog(cogGMadm.GreedyGhostCog_GMadm(bot)) 
    bot.add_cog(cogLang.GreedyGhostCog_Lang(bot))
    bot.add_cog(cogMisc.GreedyGhostCog_Misc(bot))
    bot.add_cog(cogRoller.GreedyGhostCog_Roller(bot))
    bot.add_cog(cogSysRoller.GreedyGhostCog_SysRoller(bot))
    bot.add_cog(cogSession.GreedyGhostCog_Session(bot))
    bot.add_cog(cogPCmgmt.GreedyGhostCog_PCmgmt(bot))
    bot.add_cog(cogPCmod.GreedyGhostCog_PCMod(bot))
    bot.add_cog(cogTasks.GreedyGhostCog_Tasks(bot))
    
    # run the bot (duh)
    bot.run(TOKEN)
