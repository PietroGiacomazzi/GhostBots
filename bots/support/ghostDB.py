from discord.ext import commands
import web
from deprecation import deprecated

from lang.lang import LangSupportException
from .utils import *

LogType = enum("CUR_VALUE", "MAX_VALUE", "TEXT_VALUE", "PIMP_MAX", "ADD", "DELETE")

class DBException(LangSupportException):
    pass

class DBManager:
    def __init__(self, config):
        self.cfg = config
        self.db = None
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
    @deprecated()
    def isUser(self, userid):
        """ Gets user info if present. DEPRECATED, USE isValidUser"""
        results = self.db.select('People', where='userid=$userid', vars=dict(userid=userid))
        if len(results):
            return True, results[0]
        else:
            return False, None
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
        ba, _ = self.isValidBotAdmin(userid)
        st, _ = self.isValidStoryteller(userid)
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
        if self.getUser(userid)['name'] != name:
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
    @deprecated()
    def isBotAdmin(self, userid): # TODO remove
        """Is this user an admin?"""
        admins = self.db.select('BotAdmin',  where='userid = $userid', vars=dict(userid=userid))
        return bool(len(admins)), (admins[0] if (len(admins)) else None)
    @deprecated()
    def isStoryteller(self, userid): # TODO remove
        """Is this user a storyteller? DEPRECATED, USE isValidStoryTeller!"""
        storytellers = self.db.select('Storyteller',  where='userid = $userid', vars=dict(userid=userid))
        return bool(len(storytellers)), (storytellers[0] if (len(storytellers)) else None)
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
    ## New style validators here
    # the idea is: getter throws exception and returns only data
    # Setter returns a "validated" object with a bool and either the object OR the exception
    # TODO: maybe do classes for these?
    def getTraitInfo(self, trait_id: str):
        """Get trait info"""
        traits = self.db.query("""
    SELECT
        t.*,
        tt.textbased as textbased,
        t.name as traitName
    FROM Trait t
    join TraitType tt on (t.traittype = tt.id)
    WHERE t.id = $trait 
    """, vars=dict(trait=trait_id))
        if len(traits) == 0:
            raise DBException('string_TRAIT_does_not_exist', (trait_id,))
        return traits[0]
    def isValidTrait(self, traitid: str): # TODO lang Version
        """Does this trait exist?"""
        try:
            traitinfo = self.getTraitInfo(traitid)
            return True, traitinfo
        except DBException as e:
            return False, e
    def getUser(self, userid):
        """ Gets user info """
        results = self.db.select('People', where='userid=$userid', vars=dict(userid=userid))
        if len(results):
            return results[0]
        else:
            raise DBException("Utente non trovato")
    def isValidUser(self, userid):
        """ Is this a valid User?  """
        try:
            userdata = self.getUser(userid)
            return True, userdata
        except DBException as e:
            return False, e
    def getStoryTeller(self, userid):
        """ Gets storyteller info """
        results = self.db.query("""
SELECT p.*
FROM Storyteller s
join People p on (p.userid = s.userid)
where s.userid = $userid
""", vars=dict(userid=userid))
        if len(results):
            return results[0]
        else:
            raise DBException("L'utente specificato non è uno storyteller")
    def isValidStoryteller(self, userid):
        """ Is this a valid Storyteller?  """
        try:
            userdata = self.getStoryTeller(userid)
            return True, userdata
        except DBException as e:
            return False, e
    def getBotAdmin(self, userid):
        """ Gets storyteller info """
        results = self.db.query("""
SELECT p.*
FROM BotAdmin ba
join People p on (p.userid = ba.userid)
where ba.userid = $userid
""", vars=dict(userid=userid))
        if len(results):
            return results[0]
        else:
            raise DBException("L'utente specificato non è un Bot Admin")
    def isValidBotAdmin(self, userid):
        """ Is this a valid BotAdmin?  """
        try:
            userdata = self.getBotAdmin(userid)
            return True, userdata
        except DBException as e:
            return False, e
    def getChronicle(self, chronicleid):
        """ Gets chronicle info """
        results = self.db.select('Chronicle', where='id=$id', vars=dict(id=chronicleid))
        if len(results):
            return results[0]
        else:
            raise DBException("La cronaca '{}' non esiste!", (chronicleid,))
    def isValidChronicle(self, chronicleid: str):
        """Is this a valid chronicle? """   
        try:
            chronicle = self.getChronicle(chronicleid)
            return True, chronicle
        except DBException as e:
            return False, e
    def getCharacter(self, charid: str):
        """ validates charid and returns the relevant character """
        results = self.db.select('PlayerCharacter', where='id=$id', vars=dict(id=charid))
        if len(results):
            return results[0]
        else:
            raise DBException("Il personaggio '{}' non esiste!", (charid,))
    def isValidCharacter(self, charid: str):
        """Is this a valid character? """   
        try:
            character = self.getCharacter(charid)
            return True, character
        except DBException as e:
            return False, e
    def getGameSession(self, channelid: str):
        """ Gets the session running in channelid """
        results = self.db.select('GameSession', where='channel=$channel', vars=dict(channel=channelid))
        if len(results):
            return results[0]
        else:
            raise DBException("Nessuna sessione attiva in questo canale!")
    def isSessionRunning(self, channelid: str):
        """Is there a session running in channelid? """   
        try:
            result = self.getGameSession(channelid)
            return True, result
        except DBException as e:
            return False, e
    def isValidTraitType(self, traittypeid):
        """Does this trait type exist?"""
        try:
            character = self.getTraitType(traittypeid)
            return True, character
        except DBException as e:
            return False, e
    def getTraitType(self, traittypeid):
        """ validates traittypeid and returns the relevant trait type """
        results =  self.db.select('TraitType', where='id=$id', vars=dict(id=traittypeid))
        if len(results):
            return results[0]
        else:
            raise DBException("Il tipo di tratto '{}' non esiste!", (traittypeid,))
    def isValidLanguage(self, langId: str):
        """Does this language exist in the db?"""
        try:
            language = self.getLanguage(langId)
            return True, language
        except DBException as e:
            return False, e
    def getLanguage(self, langId: str):
        """ Validates langId and returns the relevant Language """
        results =  self.db.select('Languages', where='langId=$id', vars=dict(id=langId))
        if len(results):
            return results[0]
        else:
            raise DBException("string_error_invalid_language_X", (langId,))
    def isValidCharacterNote(self, charid: str, noteid: str, userid: str):
        """Does this character note exist in the db?"""
        try:
            note = self.getCharacterNote(charid, noteid, userid)
            return True, note
        except DBException as e:
            return False, e
    def getCharacterNote(self,  charid: str, noteid: str, userid: str):
        """ Validates character note and returns it """
        results = self.db.select('CharacterNotes', where='charid=$charId and userid=$userId and noteid=$noteId', vars=dict(charId=charid, noteId=noteid, userId=userid))
        if len(results):
            return results[0]
        else:
            raise DBException("string_error_invalid_note")
        
    ## Validators without an underlying Getter go here
    def isChronicleStoryteller(self, userid, chronicle):
        """Is this user a Storyteller for this chronicle?"""
        storytellers = self.db.select('StoryTellerChronicleRel', where='storyteller = $userid and chronicle=$chronicle' , vars=dict(userid=userid, chronicle = chronicle))
        return bool(len(storytellers)), (storytellers[0] if (len(storytellers)) else DBException("L'utente non è storyteller per questa cronaca"))


