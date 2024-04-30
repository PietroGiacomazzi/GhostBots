from discord.ext import commands
from dataclasses import dataclass
import os, web, logging

from lang.lang import LangSupportException
from .utils import *

_log = logging.getLogger(__name__)

LogType = enum("CUR_VALUE", "MAX_VALUE", "TEXT_VALUE", "PIMP_MAX_UNUSED", "ADD", "DELETE")

# ENVIRONMENT VARIABLE NAMES

ENV_DATABASE_DIALECT = 'DATABASE_DIALECT'
ENV_DATABASE_DRIVER = 'DATABASE_DRIVER'
ENV_DATABASE_HOST = 'DATABASE_HOST'
ENV_DATABASE_DBNAME = 'DATABASE_DBNAME'
ENV_DATABASE_USER = 'DATABASE_USER'
ENV_DATABASE_PW_FILE = 'DATABASE_PW_FILE'

#Table names:

TABLENAME_GUILD = "BotGuild"
TABLENAME_GAMESYSTEM = "Gamesystem"
TABLENAME_CHRONICLE = "Chronicle"
TABLENAME_CHANNELGAMESYSTEM = "ChannelGamesystem"
TABLENAME_CHARACTERMACRO = 'CharacterMacro'
TABLENAME_PLAYERCHARACTER = 'PlayerCharacter'
TABLENAME_CHRONICLECHARACTERREL = 'ChronicleCharacterRel'
TABLENAME_GAMESESSION = 'GameSession'
TABLENAME_TRAITSETTINGS = 'TraitSettings'
TABLENAME_TRAIT = 'Trait'

#Fieldnames

GAMESYSTEMID = "gamesystemid"
GENERICID =  'id'
CHRONICLE = 'chronicle'
CHANNEL = 'channel'
TRAITID = 'traitid'
GAMESTATEID = 'gamestateid'

FIELDNAME_GAMESYSTEM_GAMESYSTEMID = GAMESYSTEMID

FIELDNAME_CHRONICLE_CHRONICLEID = GENERICID
FIELDNAME_CHRONICLE_GAMESYSTEMID = GAMESYSTEMID

FIELDNAME_CHANNELGAMESYSTEM_CHANNELID = "channelid"
FIELDNAME_CHANNELGAMESYSTEM_GAMESYSTEMID = GAMESYSTEMID

FIELDNAME_CHARACTERMACRO_CHARID = 'characterid'
FIELDNAME_CHARACTERMACRO_MACROID = 'macroid'
FIELDNAME_CHARACTERMACRO_MACROCOMMANDS = 'macrocommands'

FIELDNAME_PLAYERCHARACTER_CHARACTERID = GENERICID

FIELDNAME_CHRONICLECHARACTERREL_PLAYERCHAR = 'playerchar'
FIELDNAME_CHRONICLECHARACTERREL_CHRONICLE = CHRONICLE

FIELDNAME_GAMESESSION_CHRONICLE = CHRONICLE
FIELDNAME_GAMESESSION_CHANNEL = CHANNEL
FIELDNAME_GAMESESSION_GAMESTATEID = GAMESTATEID

FIELDNAME_TRAITSETTINGS_TRAITID = TRAITID
FIELDNAME_TRAITSETTINGS_GAMESTATEID = GAMESTATEID
FIELDNAME_TRAITSETTINGS_ROLLPERMANENT = 'rollpermanent'
FIELDNAME_TRAITSETTINGS_AUTOPENALTY = 'autopenalty'

FIELDNAME_TRAIT_TRAITID = GENERICID
FIELDNAME_TRAIT_MAX_VALUE = 'max_value'
FIELDNAME_TRAIT_CUR_VALUE = 'cur_value'

# Queries

QUERY_UNTRANSLATED_TRAIT = """
    SELECT
        t.*,
        tt.textbased as textbased,
        t.name as traitName
    FROM Trait t
    join TraitType tt on (t.traittype = tt.id)
    WHERE t.id = $trait
"""

QUERY_CHARACTER_MACROS = f"""
SELECT t.characterid, t.macroid
FROM {TABLENAME_CHARACTERMACRO} t 
WHERE t.{FIELDNAME_CHARACTERMACRO_CHARID} = $charid
"""

QUERY_GENERAL_MACROS = f"""
SELECT t.characterid, t.macroid
FROM {TABLENAME_CHARACTERMACRO} t 
WHERE t.{FIELDNAME_CHARACTERMACRO_CHARID} IS NULL
"""

QUERY_CHARACTER_GAMESYSTEMS = f"""
SELECT c.{FIELDNAME_CHRONICLE_GAMESYSTEMID}
FROM {TABLENAME_PLAYERCHARACTER} pc
join {TABLENAME_CHRONICLECHARACTERREL} ccr on (ccr.{FIELDNAME_CHRONICLECHARACTERREL_PLAYERCHAR} = pc.{FIELDNAME_PLAYERCHARACTER_CHARACTERID})
join {TABLENAME_CHRONICLE} c on (c.{FIELDNAME_CHRONICLE_CHRONICLEID} = ccr.{FIELDNAME_CHRONICLECHARACTERREL_CHRONICLE})
LEFT join {TABLENAME_GAMESESSION} gs on (gs.{FIELDNAME_GAMESESSION_CHRONICLE} = c.{FIELDNAME_CHRONICLE_CHRONICLEID})
WHERE pc.{FIELDNAME_PLAYERCHARACTER_CHARACTERID} = $charid
order by gs.{FIELDNAME_GAMESESSION_CHANNEL} desc
"""

# Objects

class DBException(LangSupportException):
    pass

@dataclass
class TraitSettings():
    traitid: str
    gamestateid: int
    rollpermanent: bool
    autopenalty: bool

class DBManager:
    def __init__(self, config):
        self.cfg = config
        self.db : web.db.DB = None
        self.validators = None
        self.reconnect()
    def reconnect(self):
        #self.db = web.database(host=self.cfg['host'], port=int(self.cfg['port']),dbn=self.cfg['type'], user=self.cfg['user'], pw=self.cfg['pw'], db=self.cfg['database'])
        pw_file = os.environ.get(ENV_DATABASE_PW_FILE)
        self.db = web.database(
            host=os.environ.get(ENV_DATABASE_HOST),
            port=int(self.cfg['port']),
            dbn=os.environ.get(ENV_DATABASE_DIALECT),
            user=os.environ.get(ENV_DATABASE_USER),
            pw=None if pw_file is None else get_secret(pw_file, '/run/secrets'),
            db=os.environ.get(ENV_DATABASE_DBNAME))
        self.validators = ValidatorGenerator(self.db)
        # fallback
        self.db.query("SET SESSION interactive_timeout=$timeout", vars=dict(timeout=int(self.cfg['session_timeout'])))
        self.db.query("SET SESSION wait_timeout=$timeout", vars=dict(timeout=int(self.cfg['session_timeout'])))
    def buildTraitSettings(self, traitid: str, gamestateid: int):
        settings_db = self.validators.getValidateTraitSettings(traitid, gamestateid).get()
        return TraitSettings(traitid
                             , gamestateid
                             , settings_db[FIELDNAME_TRAITSETTINGS_ROLLPERMANENT] if settings_db[FIELDNAME_TRAITSETTINGS_ROLLPERMANENT] is not None else False
                             , settings_db[FIELDNAME_TRAITSETTINGS_AUTOPENALTY] if settings_db[FIELDNAME_TRAITSETTINGS_AUTOPENALTY] is not None else False
                            )
    def setGameState(self, channelid: str, gamestateid: int):
        return self.db.update(TABLENAME_GAMESESSION, where= f'{FIELDNAME_GAMESESSION_CHANNEL} = $channelid', vars=dict(channelid=channelid), gamestateid = gamestateid)
    def updateGameSystems(self):
        db_list = list(map(lambda x: x[FIELDNAME_GAMESYSTEM_GAMESYSTEMID], self.db.select(TABLENAME_GAMESYSTEM, what= FIELDNAME_GAMESYSTEM_GAMESYSTEMID).list()))
        bot_list = GAMESYSTEMS_LIST
        for db_item in db_list:
            if not db_item in bot_list:
                self.db.delete(TABLENAME_GAMESYSTEM, where=f'{FIELDNAME_GAMESYSTEM_GAMESYSTEMID} = $rs' ,vars=dict(rs = db_item))
        for bot_item in bot_list:
            if not bot_item in db_list:
                self.db.insert(TABLENAME_GAMESYSTEM, **{FIELDNAME_GAMESYSTEM_GAMESYSTEMID: bot_item})
    def getRollSystemByChannel(self, channelid: str) -> str:
        is_session, session = self.validators.getValidateRunningSession(channelid).validate()
        if is_session:
            chronicleid = session["chronicle"]
            chronicle = self.validators.getValidateChronicle(chronicleid).get()
            if not chronicle[FIELDNAME_CHRONICLE_GAMESYSTEMID] is None:
                return chronicle[FIELDNAME_CHRONICLE_GAMESYSTEMID]
        is_channel, channel = self.validators.getValidateChannelGameSystem(channelid).validate()
        if is_channel:
            return channel[FIELDNAME_CHANNELGAMESYSTEM_GAMESYSTEMID]
        return None
    def getGameSystemIdByCharacter(self, character, fallback) -> str:
        """ Get a game system from a character. Checks all chronicles the character is in, prioritizing ones with running sessions """
        r = self.db.query(QUERY_CHARACTER_GAMESYSTEMS, vars=dict(charid = character[FIELDNAME_PLAYERCHARACTER_CHARACTERID]))
        if len(r):
            return r[0][FIELDNAME_CHRONICLE_GAMESYSTEMID]
        return fallback
    def newCharacter(self, chid, fullname, owner, player = None):
        if player == None:
            player = owner
        t = self.db.transaction()
        try:
            self.db.insert('PlayerCharacter', id=chid, owner=owner, player=owner, fullname=fullname)
            self.db.query("""
insert into CharacterTrait
    select t.id as trait, 
    pc.id as playerchar, 
    0 as cur_value, 
    0 as max_value, 
    "" as text_value
    from Trait t, PlayerCharacter pc
    where t.standard = true
    and pc.id = $pcid;
""", vars = dict(pcid=chid))
        except:
            t.rollback()
            raise DBException("db_failed_inserting_character", (chid,))
        else:
            t.commit()
            return
    def reassignCharacter(self, charid: str, new_owner: str) -> bool:
        """ Reassing a character to anither player"""
        u = self.db.update("PlayerCharacter", where='id = $charid', vars=dict(charid=charid), owner = new_owner, player = new_owner)
        if u == 1 or u == 0:
            return True
        else:
            raise DBException('string_error_database_unexpected_update_rowcount', (u,))
    def getActiveChar(self, ctx: commands.Context):
        """ DISCORD SPECIFIC! given a channel, find the character that is being played by the user """
        playercharacters = self.db.query("""
    SELECT pc.*
    FROM GameSession gs
    join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
    join PlayerCharacter pc on (pc.id = cc.playerchar)
    where gs.channel = $channel and pc.player = $player
    """, vars=dict(channel=ctx.channel.id, player=ctx.message.author.id))
        if len(playercharacters) == 0:
            raise DBException("Non stai interpretando nessun personaggio!")
        if len(playercharacters) > 1:
            raise DBException("Stai interpretando più di un personaggio in questa cronaca, non so a chi ti riferisci!")
        return playercharacters[0]
    def getTrait(self, pc_id, trait_id):
        """Get a character's trait (input is raw id, output is raw)"""
        traits = self.db.query("""
    SELECT
        ct.*,
        t.*,
        tt.textbased as textbased,
        tt.dotvisualmax as dotvisualmax,
        t.name as traitName
    FROM CharacterTrait ct
    join Trait t on (t.id = ct.trait)
    join TraitType tt on (t.traittype = tt.id)
    WHERE ct.trait = $trait 
    and ct.playerchar = $pc
    """, vars=dict(trait=trait_id, pc=pc_id))
        if len(traits) == 0:
            raise DBException('string_PC_does_not_have_TRAIT', (pc_id, trait_id))
        return traits[0]
    def getTrait_Lang(self, pc_id, trait_id, lang_id):
        """Get a character's trait (input needs to be translated, output is translated)"""
        traits = self.db.query("""
    SELECT
        ct.*,
        t.*,
        tt.textbased as textbased,
        tt.dotvisualmax as dotvisualmax,
        lt.traitName as traitName
    FROM CharacterTrait ct
    join Trait t on (t.id = ct.trait)
    join TraitType tt on (t.traittype = tt.id)
    join LangTrait lt on(t.id = lt.traitId)
    WHERE lt.traitShort = $trait
    and ct.playerchar = $pc
    and lt.langId = $lid
    """, vars=dict(trait=trait_id, pc=pc_id, lid = lang_id))
        if len(traits) == 0:
            raise DBException('string_PC_does_not_have_TRAIT', (pc_id, trait_id))
        if len(traits) != 1:
            raise DBException('string_TRAIT_is_ambiguous_N_found', (trait_id, len(traits)))
        return traits[0]
    def getTrait_LangAndTranslate(self, pc_id, trait_id, lang_id):
        """Get a character's trait (input is raw id and output is translated)"""
        traits = self.db.query("""
    SELECT
        ct.*,
        t.*,
        tt.textbased as textbased,
        tt.dotvisualmax as dotvisualmax,
        lt.traitName as traitName
    FROM CharacterTrait ct
    join Trait t on (t.id = ct.trait)
    join TraitType tt on (t.traittype = tt.id)
    join LangTrait lt on(t.id = lt.traitId)
    WHERE ct.trait = $trait 
    and ct.playerchar = $pc
    and lt.langId = $lid
    """, vars=dict(trait=trait_id, pc=pc_id, lid = lang_id))
        if len(traits) == 0:
            raise DBException('string_PC_does_not_have_TRAIT', (pc_id, trait_id))
        if len(traits) != 1:
            raise DBException('string_TRAIT_is_ambiguous_N_found', (trait_id, len(traits)))
        return traits[0]
    def getTrait_LangSafe(self, pc_id, trait_id, lang_id):
        """Get a character's trait (input can be either translated or raw)"""
        try:
            return self.getTrait_Lang(pc_id, trait_id, lang_id) # can raise
        except DBException as e: # fallback to base trait id and translate it 
            try:
                return self.getTrait_LangAndTranslate(pc_id, trait_id, lang_id) 
            except DBException as e: # fallback to pure trait
                return self.getTrait(pc_id, trait_id) # can raise
    def getChannelStoryTellers(self, channelid):
        """Get Storytellers for the active chronicle in this channel"""
        sts = self.db.query("""
    SELECT  *
    FROM GameSession gs
    join StoryTellerChronicleRel stcr on (gs.chronicle = stcr.chronicle)
    where gs.channel = $channel
    """, vars=dict(channel=channelid))
        if len(sts) == 0:
            raise DBException(f'Non ci sono sessioni attive in questo canale, oppure questa cronoca non ha un storyteller')
        return sts.list()
    def getCharacterMacros(self, charid: str):
        return self.db.query(QUERY_CHARACTER_MACROS, vars=dict(charid=charid))
    def getGeneralMacros(self):
        return self.db.query(QUERY_GENERAL_MACROS)
    def newMacro(self, macroid: str, charid: str, text: str):
        self.db.insert(TABLENAME_CHARACTERMACRO, characterid=charid, macroid=macroid, macrocommands=text)
    def registerGuild(self, guildid: str, guildname: str, authorized: bool):
        """ Registers a guild """
        self.db.insert(TABLENAME_GUILD, guildid=guildid, guildname=guildname, authorized = authorized)
    def removeGuild(self, guildid: str):
        """ Removes a guild """
        self.db.delete(TABLENAME_GUILD, where='guildid=$guildid', vars=dict(guildid=guildid))
    def updateGuildName(self, guildid: str, guildname: str):
        """ Updates a guild name """
        self.db.update(TABLENAME_GUILD, where='guildid=$guildid', vars=dict(guildid=guildid), guildname = guildname)
    def updateGuildAuthorization(self, guildid: str, authorized: bool):
        """ Updates a guild authorization """
        self.db.update(TABLENAME_GUILD, where='guildid=$guildid', vars=dict(guildid=guildid), authorized = authorized)
    def getGuilds(self) -> list:
        """ Get all registered guilds """
        return self.db.select(TABLENAME_GUILD).list()
    def registerUser(self, userid, name, langId):
        """ Registers a user """
        self.db.insert('People', userid=userid, name=name, langId = langId)
    def _removeUser(self, userid, dummyuserid) -> None:
        """ Removes an user by moving all their characters to a dummy user and deleting the database record
        Will fail if the user is an Admin or a Storyteller due to data constraits """
        # TODO: tts?
        u = self.db.update("PlayerCharacter", where='owner = $userid or player = $userid', vars=dict(userid=userid), owner = dummyuserid, player = dummyuserid)
        u = self.db.update("CharacterModLog", where='userid = $userid', vars=dict(userid=userid), userid = dummyuserid)
        u = self.db.delete('People', where='userid=$userid', vars=dict(userid=userid))
    def tryRemoveUser(self, userid, dummyuserid) -> None:
        """ Attempts to remove an user but does not if the user is an admin or a storyteller with chronicles, or the dummy user """
        if userid == dummyuserid:
            raise DBException("string_error_cannot_remove_dummy_user")
        ba, _ = self.validators.getValidateBotAdmin(userid).validate()
        st, _ = self.validators.getValidateBotStoryTeller(userid).validate()
        st_hc = False
        if st:
            st_hc = self.hasSTAnyChronicles(userid)
        if not ba and (not st or (st and not st_hc)):
            if st:
                self.unnameStoryTeller(userid)
            self._removeUser(userid, dummyuserid)
            return True
        print(f"Cannot remove {userid}: admin: {ba} storyteller {st} has chronicles {st_hc}")
        return False
    def updateUser(self, userid, name) -> None:
        """ Updates a user's name """
        if self.validators.getValidateBotUser(userid).get()['name'] != name:
            u = self.db.update("People", where='userid = $userid', vars=dict(userid=userid), name = name)
    def getUsers(self) -> list:
        """ Get all registered users """
        return self.db.select('People').list()
    def getUserLanguage(self, userid):
        """Returns the language id of the selected user"""
        results = self.db.select('People', where='userid=$userid', vars=dict(userid=userid))
        if len(results):
            return results[0]['langId']
        else:
            raise DBException("Utente non trovato per la ricerca della lingua")
    def isStorytellerForCharacter(self, userid, charid):
        """Is this user a storyteller for this character?"""
        query = """
    SELECT *
    FROM StoryTellerChronicleRel stcr
    JOIN ChronicleCharacterRel ccr on (stcr.chronicle = ccr.chronicle)
    WHERE stcr.storyteller = $userid and ccr.playerchar = $charid  
"""
        result = self.db.query(query,vars=dict(userid=userid, charid=charid))
        return bool(len(result)), (result[0] if (len(result)) else None)
    def hasSTAnyChronicles(self, userid):
        """ Does the user own any chronicles? """
        return len(self.db.select("StoryTellerChronicleRel", where='storyteller = $userid', vars=dict(userid=userid))) != 0
    def isCharacterOwner(self, userid, character):
        """Does this user own this character?"""
        characters = self.db.select('PlayerCharacter',  where='owner = $owner and id=$character', vars=dict(owner=userid, character=character))
        return bool(len(characters)), (characters[0] if (len(characters)) else None)
    def isCharacterLinked(self, charid): #
        """Is this character linked to a chronicle? (can return the list of chronicles)"""
        result = self.db.select('ChronicleCharacterRel', where='playerchar=$id', vars=dict(id=charid))
        return bool(len(result)), result.list() if len(result) else None
    def isCharacterLinkedToChronicle(self, charid, chronicleid):
        """Is this character linked to a specific chronicle? """
        result = self.db.select('ChronicleCharacterRel', where='playerchar=$id and chronicle=$chronicleid', vars=dict(id=charid, chronicleid=chronicleid))
        return bool(len(result)), result.list()[0] if len(result) else None
    def isSessionActiveForCharacter(self, charid, channelid): #
        """Is there a session on this channel that includes this character?"""
        result = self.db.query("""
SELECT cc.playerchar
FROM GameSession gs
join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
where gs.channel = $channel and cc.playerchar = $charid
""", vars=dict(channel=channelid, charid=charid))
        return bool(len(result)), result[0] if len(result) else None
    
    def log(self, userid, charid, traitid, modtype, new_val, old_val = "", command = ""):
        self.db.insert("CharacterModLog", userid = userid, charid = charid, traitid = traitid, val_type = modtype, old_val = old_val, new_val = new_val, command = command)
    def unnameStoryTeller(self, userid):
        """ Remove storyteller status """
        return self.db.delete('Storyteller', where='userid=$userid', vars=dict(userid=userid)) #foreign key is set to cascade. this will also unlink from all chronicles
    def getLiveChroniclesString(self):
        """ Get a concatention of all currently running chronicles in sessions """
        query = "select group_concat(DISTINCT c.name SEPARATOR ', ') as activity_string from GameSession gs join Chronicle c on (gs.chronicle = c.id)"
        result = self.db.query(query)
        return result[0]['activity_string']
           
    ## Validators without an underlying Getter go here
    def isChronicleStoryteller(self, userid, chronicle):
        """Is this user a Storyteller for this chronicle?"""
        storytellers = self.db.select('StoryTellerChronicleRel', where='storyteller = $userid and chronicle=$chronicle' , vars=dict(userid=userid, chronicle = chronicle))
        return bool(len(storytellers)), (storytellers[0] if (len(storytellers)) else DBException("L'utente non è storyteller per questa cronaca"))

class GetValidateRecord:
    """ A Class that provides a standardized get/validate structure for database records """
    def __init__(self, db: web.db.DB, query: str, filters: dict, notfound_msg = None):
        self.notfoundMsg = notfound_msg
        self.db = db
        self.querystr = query
        self.queryfilters = filters
    def results(self) -> web.db.ResultSet:
        """ Performs the search with the parameters specified at object creation """
        return self.db.query(self.querystr, vars = self.queryfilters)
    def get(self) -> web.utils.Storage:
        """ Performs get logic with the parameters specified when the GetValidateRecord object was created:

        If at least one record is found, the first one is returned, 
        If no record is found, a DBException is raised  """
        results = self.results()
        if len(results):
            return results[0]
        else:
            raise self.constructNotFoundError()
    def validate(self):# -> tuple[bool, web.utils.Storage | DBException]:
        """ Performs validation logic with the parameters specified when the GetValidateRecord object was created:

        If at least one record is found, this method returns (True, Record) 
        If no record is found, this method returns (False, DBException), where the exception is the one thrown by the get method """
        try:
            return True, self.get()
        except DBException as e:
            return False, e
    def constructNotFoundError(self) -> DBException:
        """ Constructs an error that is going to get thrown when no record is found"""
        out_values = tuple(self.queryfilters.values())
        if self.notfoundMsg:
            return DBException(self.notfoundMsg, out_values) 
        else:
            return DBException('string_error_record_not_found', str(out_values))  

class GetValidateRecordNoFormat(GetValidateRecord):
    """ This subclass of GetValidateRecord does not pass any of the input values to the exception that is raised by the get behaviour """
    def constructNotFoundError(self) -> DBException:
        return DBException(self.notfoundMsg)

class ValidatorGenerator:
    def __init__(self, db: web.db.DB):
        self.db = db
    def getValidateCharacterNote(self, charid: str, noteid: str, userid: str) -> GetValidateRecord:
        """ Handles validation of Character notes """
        return GetValidateRecordNoFormat(self.db, "select * from CharacterNotes  where charid=$charId and userid=$userId and noteid=$noteId", dict(charId=charid, noteId=noteid, userId=userid), "string_error_invalid_note")
    def getValidateLanguage(self, langId: str) -> GetValidateRecord:
        """ Handles validation of Language IDs """
        return GetValidateRecord(self.db, "select * from Languages where langId=$id", dict(id=langId), "string_error_invalid_language_X")
    def getValidateTraitType(self, traittypeid: str) -> GetValidateRecord:
        """ Handles validation of Trait Types """
        return GetValidateRecord(self.db, "select * from TraitType where id=$id", dict(id=traittypeid), "Il tipo di tratto '{}' non esiste!")
    def getValidateRunningSession(self, channelid: str) -> GetValidateRecord:
        """ Handles validation of game sessions running on Discord text channels, retrieves chronicle data too. """
        return GetValidateRecordNoFormat(self.db, f"SELECT * from {TABLENAME_GAMESESSION} gs JOIN {TABLENAME_CHRONICLE} c ON (c.{FIELDNAME_CHRONICLE_CHRONICLEID} = gs.{FIELDNAME_GAMESESSION_CHRONICLE}) where channel=$channel", dict(channel=channelid), "Nessuna sessione attiva in questo canale!")
    def getValidateAnyRunningSessionForCharacter(self, charid: str):
        """ Handles validation of any running session for a given character """
        query = f"""
        SELECT gs.* 
        FROM {TABLENAME_GAMESESSION} gs 
        join {TABLENAME_CHRONICLECHARACTERREL} cc on (gs.{FIELDNAME_GAMESESSION_CHRONICLE} = cc.{FIELDNAME_CHRONICLECHARACTERREL_CHRONICLE}) 
        where cc.playerchar = $charid"""
        return GetValidateRecord(self.db, query, dict(charid=charid), "string_error_no_session_for_character")
    def getValidateCharacter(self, charid: str) -> GetValidateRecord:
        """ Handles validation of player characters by character id """
        return GetValidateRecord(self.db, "select * from PlayerCharacter where id=$id", dict(id=charid), "Il personaggio '{}' non esiste!")
    def getValidateChronicle(self, chronicleid: str) -> GetValidateRecord:
        """ Handles validation of chronicles by chronicle id """
        return GetValidateRecord(self.db, "select * from Chronicle where id=$id", dict(id=chronicleid), "La cronaca '{}' non esiste!")
    def getValidateBotUser(self, userid: str) -> GetValidateRecord:
        """ Handles validation of Bot Users by discord id """
        return GetValidateRecordNoFormat(self.db, "select * from People where userid=$userid", dict(userid=userid), "string_error_user_not_found")
    def getValidateBotAdmin(self, userid: str) -> GetValidateRecord:
        """ Handles validation of Bot Admins by discord id """
        return GetValidateRecordNoFormat(self.db, """SELECT p.* FROM BotAdmin ba join People p on (p.userid = ba.userid) where ba.userid = $userid""", dict(userid=userid), "L'utente specificato non è un Bot Admin")
    def getValidateBotStoryTeller(self, userid: str) -> GetValidateRecord:
        """ Handles validation of Bot Storytellers by discord id """
        return GetValidateRecordNoFormat(self.db, """SELECT p.* FROM Storyteller s join People p on (p.userid = s.userid) where s.userid = $userid""", dict(userid=userid), "L'utente specificato non è uno storyteller")
    def getValidateTrait(self, traitid: str) -> GetValidateRecord:
        """ Handles validation of untranslated Traits by raw id """
        return GetValidateRecord(self.db, QUERY_UNTRANSLATED_TRAIT, dict(trait=traitid), "string_TRAIT_does_not_exist")
    def getValidateGuild(self, guildid: str) -> GetValidateRecord:
        """ Handles validation of a Discord Guild """
        return GetValidateRecordNoFormat(self.db, f"select * from {TABLENAME_GUILD} where guildid=$guildid", dict(guildid=guildid), "string_error_invalid_guild")
    def getValidateChannelGameSystem(self, channelid: str) -> GetValidateRecord:
        """ Handles validation of saved channel gamesystems """
        return GetValidateRecordNoFormat(self.db, f'SELECT t.* FROM {TABLENAME_CHANNELGAMESYSTEM} t where t.{FIELDNAME_CHANNELGAMESYSTEM_CHANNELID} = $key', dict(key=channelid), "Il canale non ha un sistema di gioco impostato!")
    def getValidateCharacterMacro(self, charid: str, macroid: str):
        """ Handles validation of character macros """
        return GetValidateRecord(self.db, f'SELECT t.* FROM {TABLENAME_CHARACTERMACRO} t where (t.{FIELDNAME_CHARACTERMACRO_CHARID} = $charid or t.{FIELDNAME_CHARACTERMACRO_CHARID} IS NULL) and t.{FIELDNAME_CHARACTERMACRO_MACROID} = $macroid', dict(charid=charid, macroid=macroid), "string_error_macro_not_found_for_char")
    def getValidateMacro(self, macroid: str):
        """ Handles validation of macros """
        return GetValidateRecord(self.db, f'SELECT t.* FROM {TABLENAME_CHARACTERMACRO} t where t.{FIELDNAME_CHARACTERMACRO_MACROID} = $macroid', dict(macroid=macroid), "string_error_macro_not_found")
    def getValidateTraitSettings(self, traitid: str, gamestateid: int):
        """ Handles validation of trait settings. will fail only if the trait does not exist """
        return GetValidateRecord(self.db, f"SELECT t.id, ts.* FROM {TABLENAME_TRAIT} t LEFT JOIN {TABLENAME_TRAITSETTINGS} ts ON (ts.{FIELDNAME_TRAITSETTINGS_TRAITID} = t.{FIELDNAME_TRAIT_TRAITID} AND ts.{FIELDNAME_TRAITSETTINGS_GAMESTATEID} = $gamestateid) WHERE t.{FIELDNAME_TRAIT_TRAITID} = $traitid ", dict(traitid = traitid, gamestateid = gamestateid), "string_TRAIT_does_not_exist")
