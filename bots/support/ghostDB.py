from typing import Type
from discord.ext import commands
import web

from lang.lang import LangSupportException
from .utils import *

LogType = enum("CUR_VALUE", "MAX_VALUE", "TEXT_VALUE", "PIMP_MAX", "ADD", "DELETE")

class DBException(LangSupportException):
    pass

class DBManager:
    def __init__(self, config):
        self.cfg = config
        self.db : web.db.DB = None
        self.reconnect()
    def reconnect(self):
        self.db = web.database(host=self.cfg['host'], port=int(self.cfg['port']),dbn=self.cfg['type'], user=self.cfg['user'], pw=self.cfg['pw'], db=self.cfg['database'])
        # fallback
        self.db.query("SET SESSION interactive_timeout=$timeout", vars=dict(timeout=int(self.cfg['session_timeout'])))
        self.db.query("SET SESSION wait_timeout=$timeout", vars=dict(timeout=int(self.cfg['session_timeout'])))
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
    "" as text_value,
    case 
    WHEN t.trackertype = 0 and (t.traittype ='fisico' or t.traittype = 'sociale' or t.traittype='mentale') THEN 6
    else 0
    end
    as pimp_max
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
    def getActiveChar(self, ctx: commands.Context): # dato un canale e un utente, trova il pg interpretato
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
        """ Attempts to remove an user but does not if the user is an admin or a storyteller with chronicles """
        ba, _ = GetValidateBotAdmin(self.db, userid).validate()
        st, _ = GetValidateBotStoryTeller(self.db, userid).validate()
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
        if GetValidateBotUser(self.db, userid).get()['name'] != name:
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
    def isAnySessionActiveForCharacter(self, charid): #
        """Is there a session anywhere that includes this character?"""
        result = self.db.query("""
SELECT cc.playerchar
FROM GameSession gs
join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
where cc.playerchar = $charid
""", vars=dict(charid=charid))
        return bool(len(result)), result[0] if len(result) else None
    
    def log(self, userid, charid, traitid, modtype, new_val, old_val = "", command = ""):
        self.db.insert("CharacterModLog", userid = userid, charid = charid, traitid = traitid, val_type = modtype, old_val = old_val, new_val = new_val, command = command)
    def unnameStoryTeller(self, userid):
        """ Remove storyteller status """
        return self.db.delete('Storyteller', where='userid=$userid', vars=dict(userid=userid)) #foreign key is set to cascade. this will also unlink from all chronicles
           
    ## Validators without an underlying Getter go here
    def isChronicleStoryteller(self, userid, chronicle):
        """Is this user a Storyteller for this chronicle?"""
        storytellers = self.db.select('StoryTellerChronicleRel', where='storyteller = $userid and chronicle=$chronicle' , vars=dict(userid=userid, chronicle = chronicle))
        return bool(len(storytellers)), (storytellers[0] if (len(storytellers)) else DBException("L'utente non è storyteller per questa cronaca"))

class GetValidateRecord:
    """ A Class that provides a standardized get/vallidate structure for database records """
    def __init__(self, db: web.db.DB, notfound_msg = 'string_error_record_not_found'):
        self.notfoundMsg = notfound_msg
        self.db = db
    def results(self) -> web.db.ResultSet:
        """ Performs the search with the parameters specified at object creation """
        raise NotImplementedError()
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
        """ Constructs and error that is goig to get thrown when no record is found"""
        return DBException(self.notfoundMsg) 

class GetValidateCharacterNote(GetValidateRecord):
    """ Handles validation of Character notes """
    def __init__(self, db: web.db.DB, charid: str, noteid: str, userid: str):
        super().__init__(db, 'string_error_invalid_note')
        self.charid = charid
        self.noteid = noteid
        self.userid = userid
    def results(self):
        return self.db.select('CharacterNotes', where='charid=$charId and userid=$userId and noteid=$noteId', vars=dict(charId=self.charid, noteId=self.noteid, userId=self.userid))

class GetValidateLanguage(GetValidateRecord):
    """ Handles validation of Language IDs """
    def __init__(self, db: web.db.DB, langId: str):
        super().__init__(db)
        self.langId = langId
    def results(self) -> web.db.ResultSet:
        return self.db.select('Languages', where='langId=$id', vars=dict(id=self.langId))
    def constructNotFoundError(self) -> DBException:
        return DBException("string_error_invalid_language_X", (self.langId,))
    
class GetValidateTraitType(GetValidateRecord):
    """ Handles validation of Trait Types """
    def __init__(self, db: web.db.DB, traittypeid: str):
        super().__init__(db)
        self.traittypeid = traittypeid
    def results(self) -> web.db.ResultSet:
        return self.db.select('TraitType', where='id=$id', vars=dict(id=self.traittypeid))
    def constructNotFoundError(self) -> DBException:
        return DBException("Il tipo di tratto '{}' non esiste!", (self.traittypeid,))

class GetValidateRunningSession(GetValidateRecord):
    """ Handles validation of game sessions running on Discord text channels """
    def __init__(self, db: web.db.DB, channelid: str):
        super().__init__(db, "Nessuna sessione attiva in questo canale!")
        self.channelid = channelid
    def results(self) -> web.db.ResultSet:
        return self.db.select('GameSession', where='channel=$channel', vars=dict(channel=self.channelid))

class GetValidateCharacter(GetValidateRecord):
    """ Handles validation of player characters by character id """
    def __init__(self, db: web.db.DB, charid: str):
        super().__init__(db)
        self.charid = charid
    def results(self) -> web.db.ResultSet:
        return self.db.select('PlayerCharacter', where='id=$id', vars=dict(id=self.charid))
    def constructNotFoundError(self) -> DBException:
        return DBException("Il personaggio '{}' non esiste!", (self.charid,))

class GetValidateChronicle(GetValidateRecord):
    """ Handles validation of chronicles by chronicle id """
    def __init__(self, db: web.db.DB, chronicleid: str):
        super().__init__(db)
        self.chronicleid = chronicleid
    def results(self) -> web.db.ResultSet:
        return self.db.select('Chronicle', where='id=$id', vars=dict(id=self.chronicleid))
    def constructNotFoundError(self) -> DBException:
        return DBException("La cronaca '{}' non esiste!", (self.chronicleid,))

class GetValidateBotUser(GetValidateRecord):
    """ Handles validation of Bot Users by discord id """
    def __init__(self, db: web.db.DB, userid: str):
        super().__init__(db, 'Utente non trovato')
        self.userid = userid
    def results(self) -> web.db.ResultSet:
        return self.db.select('People', where='userid=$userid', vars=dict(userid=self.userid))

class GetValidateBotAdmin(GetValidateRecord):
    """ Handles validation of Bot Admins by discord id """
    def __init__(self, db: web.db.DB, userid: str):
        super().__init__(db, "L'utente specificato non è un Bot Admin")
        self.userid = userid
    def results(self) -> web.db.ResultSet:
        return self.db.query("""SELECT p.*
FROM BotAdmin ba
join People p on (p.userid = ba.userid)
where ba.userid = $userid""", vars=dict(userid=self.userid))

class GetValidateBotStoryTeller(GetValidateRecord):
    """ Handles validation of Bot Storytellers by discord id """
    def __init__(self, db: web.db.DB, userid: str):
        super().__init__(db, "L'utente specificato non è uno storyteller")
        self.userid = userid
    def results(self) -> web.db.ResultSet:
        return self.db.query("""SELECT p.*
FROM Storyteller s
join People p on (p.userid = s.userid)
where s.userid = $userid""", vars=dict(userid=self.userid))

class GetValidateTrait(GetValidateRecord):
    """ Handles validation of untranslated Traits by raw id """
    def __init__(self, db: web.db.DB, traitid: str):
        super().__init__(db)
        self.traitid = traitid
    def results(self) -> web.db.ResultSet:
        return self.db.query("""SELECT
        t.*,
        tt.textbased as textbased,
        t.name as traitName
    FROM Trait t
    join TraitType tt on (t.traittype = tt.id)
    WHERE t.id = $trait""", vars=dict(trait=self.traitid))
    def constructNotFoundError(self) -> DBException:
        return DBException('string_TRAIT_does_not_exist', (self.traitid,))
