import web
from .utils import *

LogType = enum("CUR_VALUE", "MAX_VALUE", "TEXT_VALUE", "PIMP_MAX", "ADD", "DELETE")

class DBException(Exception): # use this for 'known' error situations
    def __init__(self, code: int, msg: str, formats: tuple = ()):
        super(DBException, self).__init__(code, msg, formats)

class DBManager:
    def __init__(self, config):
        self.cfg = config
        self.db = None
        self.reconnect()
    def reconnect(self):
        self.db = web.database(dbn=self.cfg['type'], user=self.cfg['user'], pw=self.cfg['pw'], db=self.cfg['database'])
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
            raise DBException(0, "db_failed_inserting_character", (chid,))
        else:
            t.commit()
            return
    def isValidCharacter(self, charid):
        characters = self.db.select('PlayerCharacter', where='id=$id', vars=dict(id=charid))
        return bool(len(characters)), (characters[0] if (len(characters)) else None)
    def getActiveChar(self, ctx): # dato un canale e un utente, trova il pg interpretato
        playercharacters = self.db.query("""
    SELECT pc.*
    FROM GameSession gs
    join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
    join PlayerCharacter pc on (pc.id = cc.playerchar)
    where gs.channel = $channel and pc.player = $player
    """, vars=dict(channel=ctx.channel.id, player=ctx.message.author.id))
        if len(playercharacters) == 0:
            raise DBException(0, "Non stai interpretando nessun personaggio!")
        if len(playercharacters) > 1:
            raise DBException(0, "Stai interpretando più di un personaggio in questa cronaca, non so a chi ti riferisci!")
        return playercharacters[0]
    def getTraitInfo(self, trait_id):
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
            raise DBException(0, 'string_TRAIT_does_not_exist', (trait_id,))
        return traits[0]
    def getTrait(self, pc_id, trait_id):
        """Get a character's trait"""
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
            raise DBException(0, 'string_PC_does_not_have_TRAIT', (pc_id, trait_id))
            #raise DBException(0, '{} non ha il tratto {}', (pc_id, trait_id))
        return traits[0]
    def getTrait_Lang(self, pc_id, trait_id, lang_id):
        """Get a character's trait (input needs to be translated)"""
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
            raise DBException(0, 'string_PC_does_not_have_TRAIT', (pc_id, trait_id))
        if len(traits) != 1:
            raise DBException(0, 'string_TRAIT_is_ambiguous_N_found', (trait_id, len(traits)))
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
            raise DBException(0, 'string_PC_does_not_have_TRAIT', (pc_id, trait_id))
        if len(traits) != 1:
            raise DBException(0, 'string_TRAIT_is_ambiguous_N_found', (trait_id, len(traits)))
        return traits[0]
    def getTrait_LangSafe(self, pc_id, trait_id, lang_id):
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
            raise DBException(0, f'Non ci sono sessioni attive in questo canale, oppure questa cronoca non ha un storyteller')
        return sts.list()
    def getUser(self, userid):
        """ Gets user info """
        results = self.db.select('People', where='userid=$userid', vars=dict(userid=userid))
        if len(results):
            return results[0]
        else:
            raise DBException(0, "Utente non trovato")
    def getUserLanguage(self, userid):
        """Returns the language id of the selected user"""
        results = self.db.select('People', where='userid=$userid', vars=dict(userid=userid))
        if len(results):
            return results[0]['langId']
        else:
            raise DBException(0, "Utente non trovato per la ricerca della lingua")
    def isBotAdmin(self, userid):
        """Is this user an admin?"""
        admins = self.db.select('BotAdmin',  where='userid = $userid', vars=dict(userid=userid))
        return bool(len(admins)), (admins[0] if (len(admins)) else None)
    def isStoryteller(self, userid):
        """Is this user a storyteller?"""
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
    def isValidChronicle(self, chronicleid):
        """Is this a valid chronicle?"""    
        chronicles = self.db.select('Chronicle', where='id=$id', vars=dict(id=chronicleid))
        return bool(len(chronicles)), chronicles.list()[0]
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
    def isChronicleStoryteller(self, userid, chronicle):
        """Is this user a Storyteller for this chronicle?"""
        storytellers = self.db.select('StoryTellerChronicleRel', where='storyteller = $userid and chronicle=$chronicle' , vars=dict(userid=userid, chronicle = chronicle))
        return bool(len(storytellers)), (storytellers[0] if (len(storytellers)) else None)
    def isValidTrait(self, traitid):
        """Does this trait exist?"""
        traits = self.db.select('Trait', where='id=$id', vars=dict(id=traitid))
        return bool(len(traits)), (traits[0] if (len(traits)) else None)
    def isValidTraitType(self, traittypeid):
        """Does this trait type exist?"""
        traittypes = self.db.select('TraitType', where='id=$id', vars=dict(id=traittypeid))
        return bool(len(traittypes)), (traittypes[0] if (len(traittypes)) else None)
    def isValidLanguage(self, langId):
        """ does this language exist? """
        langs = self.db.select('Languages', where='langId=$id', vars=dict(id=langId))
        return bool(len(langs)), (langs[0] if (len(langs)) else None)
    def log(self, userid, charid, traitid, modtype, new_val, old_val = "", command = ""):
        self.db.insert("CharacterModLog", userid = userid, charid = charid, traitid = traitid, val_type = modtype, old_val = old_val, new_val = new_val, command = command)
        


