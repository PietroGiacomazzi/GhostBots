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
        self.db = web.database(dbn=self.cfg['type'], user=self.cfg['user'], pw=self.cfg['pw'], db=self.cfg['database']) # wait_timeout = 3153600# seconds
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
        admins = self.db.select('BotAdmin',  where='userid = $userid', vars=dict(userid=userid))
        return bool(len(admins)), (admins[0] if (len(admins)) else None)
    def isStoryteller(self, userid):
        storytellers = self.db.select('Storyteller',  where='userid = $userid', vars=dict(userid=userid))
        return bool(len(storytellers)), (storytellers[0] if (len(storytellers)) else None)
    def isCharacterOwner(self, userid, character):
        characters = self.db.select('PlayerCharacter',  where='owner = $owner and id=$character', vars=dict(owner=userid, character=character))
        return bool(len(characters)), (characters[0] if (len(characters)) else None)
    def isChronicleStoryteller(self, userid, chronicle):
        storytellers = self.db.select('StoryTellerChronicleRel', where='storyteller = $userid and chronicle=$chronicle' , vars=dict(userid=userid, chronicle = chronicle))
        return bool(len(storytellers)), (storytellers[0] if (len(storytellers)) else None)
    def isValidTrait(self, traitid):
        traits = self.db.select('Trait', where='id=$id', vars=dict(id=traitid))
        return bool(len(traits)), (traits[0] if (len(traits)) else None)
    def isValidTraitType(self, traittypeid):
        traittypes = self.db.select('TraitType', where='id=$id', vars=dict(id=traittypeid))
        return bool(len(traittypes)), (traittypes[0] if (len(traittypes)) else None)
    def log(self, userid, charid, traitid, modtype, new_val, old_val = "", command = ""):
        self.db.insert("CharacterModLog", userid = userid, charid = charid, traitid = traitid, val_type = modtype, old_val = old_val, new_val = new_val, command = command)
        


