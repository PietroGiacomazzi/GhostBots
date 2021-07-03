import web
from .utils import *

LogType = enum("CUR_VALUE", "MAX_VALUE", "TEXT_VALUE", "PIMP_MAX", "ADD", "DELETE")

class DBException(Exception): # use this for 'known' error situations
    def __init__(self, msg):
        super(DBException, self).__init__(msg)

class DBManager:
    def __init__(self, config):
        self.cfg = config
        self.db = None
        self.reconnect()
    def reconnect(self):
        self.db = web.database(dbn=self.cfg['type'], user=self.cfg['user'], pw=self.cfg['pw'], db=self.cfg['database'])
        # fallback
        self.db.query("SET SESSION interactive_timeout=$timeout", vars=dict(timeout=int(self.cfg['session_timeout'])));
        self.db.query("SET SESSION wait_timeout=$timeout", vars=dict(timeout=int(self.cfg['session_timeout'])));
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
            raise DBException("Non stai interpretando nessun personaggio!")
        if len(playercharacters) > 1:
            raise DBException("Stai interpretando più di un personaggio in questa cronaca, non so a chi ti riferisci!")
        return playercharacters[0]
    def getTrait(self, pc_id, trait_id):
        """Get a character's trait"""
        traits = self.db.query("""
    SELECT
        ct.*,
        t.*,
        tt.textbased as textbased
    FROM CharacterTrait ct
    join Trait t on (t.id = ct.trait)
    join TraitType tt on (t.traittype = tt.id)
    where ct.trait = $trait and ct.playerchar = $pc
    """, vars=dict(trait=trait_id, pc=pc_id))
        if len(traits) == 0:
            raise DBException(f'{pc_id} non ha il tratto {trait_id}')
        return traits[0]
    def getChannelStoryTellers(self, channelid):
        """Get Storytellers for trhe active chronicle in this channel"""
        sts = self.db.query("""
    SELECT  *
    FROM GameSession gs
    join StoryTellerChronicleRel stcr on (gs.chronicle = stcr.chronicle)
    where gs.channel = $channel
    """, vars=dict(channel=channelid))
        if len(sts) == 0:
            raise DBException(f'Non ci sono sessioni attive in questo canale, oppure questa cronoca non ha un storyteller')
        return sts.list()
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
    def isSessionActiveForCharacter(self, charid, channelid): #
        """Is there a session on this channel that includes this character?"""
        result = self.db.query("""
SELECT cc.playerchar
FROM GameSession gs
join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
where gs.channel = $channel and cc.playerchar = $charid
""", vars=dict(channel=channelid, charid=charid))
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
    def log(self, userid, charid, traitid, modtype, new_val, old_val = "", command = ""):
        self.db.insert("CharacterModLog", userid = userid, charid = charid, traitid = traitid, val_type = modtype, old_val = old_val, new_val = new_val, command = command)
        


