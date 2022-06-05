#!/usr/bin/env python3

import sys, os

abspath = os.path.dirname(__file__)+"/"
sys.path.append(abspath)

import web, configparser
import subprocess, json, time, datetime
from requests_oauthlib import OAuth2Session

from pyresources.UtilsWebLib import *
import lang.lang as lng
import support.ghostDB as ghostDB

config = configparser.ConfigParser()
config.read("/var/www/greedy_ghost_web.ini")

# --- CONFIG ---

# stuff that gets passed to all templates
global_template_params = {
    }

urls = (
    #'', 'main_page',
    '/list', 'listIndex',
    '/doLogin', 'doLogin',
    '/doLogout', 'doLogout',
    '/discordCallback', 'discordCallback',
    '/session_info', 'session_info',
    '', 'redirectDash',
    '/', 'dashboard',
    '/getMyCharacters', 'getMyCharacters',
    '/getCharacterTraits', 'getCharacterTraits',
    '/getClanIcon', 'getClanIcon',
    '/getCharacterModLog', 'getCharacterModLog',
    '/getLanguageDictionary', 'getLanguageDictionary',
    '/editTranslations', 'editTranslations',
    '/editTranslation', 'editTranslation',
    "/editCharacterTraitNumber", "editCharacterTraitNumber",
    "/editCharacterTraitText", "editCharacterTraitText",
    "/editCharacterTraitNumberCurrent", "editCharacterTraitNumberCurrent",
    "/editCharacterTraitRemove", "editCharacterTraitRemove",
    "/traitList", "traitList",
    "/editCharacterTraitAdd", "editCharacterTraitAdd",
    "/canEditCharacter", "canEditCharacter",
    "/webFunctionVisibility", "webFunctionVisibility",
    "/getModal", "getModal",
    "/newCharacter", "newCharacter",
    "/userList", "userList",
    "/editCharacterReassign", "editCharacterReassign",
    '/getCharacterNote', 'getCharacterNote',
    '/saveCharacterNote', 'saveCharacterNote',
    '/newCharacterNote', 'newCharacterNote',
    '/getCharacterNotesList', 'getCharacterNotesList',
    '/characterNotesPage', 'characterNotesPage',
    '/deleteCharacterNote', 'deleteCharacterNote'
    )


web.config.session_parameters['samesite'] = 'Lax'
web.config.session_parameters['secure'] = True

app = web.application(urls, globals())#, autoreload=False) # the autoreload bit fucks with sessions
session = web.session.Session(app, web.session.DiskStore(config['WebApp']['sessions_path']), initializer={'access_level': 0})
render = web.template.render(abspath+'templates')
dbm = ghostDB.DBManager(config['Database'])

OAUTH2_CLIENT_ID = config['Discord']['OAUTH2_CLIENT_ID']
OAUTH2_CLIENT_SECRET = config['Discord']['OAUTH2_CLIENT_SECRET']
OAUTH2_REDIRECT_URI = config['Discord']['OAUTH2_REDIRECT_URI']

API_BASE_URL = 'https://discordapp.com/api'
AUTHORIZATION_BASE_URL = API_BASE_URL + '/oauth2/authorize'
TOKEN_URL = API_BASE_URL + '/oauth2/token'

default_language = config['WebApp']['default_language']
lp = lng.LanguageStringProvider(abspath+"lang")

# --- STUFF ---

def getLanguage(session: web.session.Session, dbm: ghostDB.DBManager) -> str:
    try:
        return dbm.getUserLanguage(session.discord_userid)
    except ghostDB.DBException:
        return default_language
    except AttributeError:
        return default_language

def token_updater(token: str):
    session.oauth2_token = token

def make_session(token: str =None, state: str =None, scope: list =None) -> OAuth2Session:
    return OAuth2Session(
        client_id=OAUTH2_CLIENT_ID,
        token=token,
        state=state,
        scope=scope,
        redirect_uri=OAUTH2_REDIRECT_URI,
        auto_refresh_kwargs={
            'client_id': OAUTH2_CLIENT_ID,
            'client_secret': OAUTH2_CLIENT_SECRET,
        },
        auto_refresh_url=TOKEN_URL,
        token_updater=token_updater)

def validator_character(data: str) -> str:
    string = validator_str_range(1, 20)(data)
    vl, _ = dbm.validators.getValidateCharacter(data).validate()
    if not vl:
        raise WebException("Invalid character", 400)
    else:
        return string

def validator_language(data: str) -> str:
    string = validator_str_range(1, 3)(data)
    vl, _ = dbm.validators.getValidateLanguage(string).validate()
    if not vl:
        raise WebException("Unsupported language", 400)
    else:
        return string

def validator_trait(data: str) -> str:
    string = validator_str_range(1, 20)(data)
    vl, _ = dbm.validators.getValidateTrait(string).validate()
    if not vl:
        raise WebException("Invalid trait", 400)
    else:
        return string

def validator_trait_number(data: str) -> str:
    string = validator_str_range(1, 20)(data)
    try:
        trait = dbm.validators.getValidateTrait(string).get()
        if trait['textbased']:
            raise WebException("Invalid trait", 400)
        else:
            return string
    except ghostDB.DBException as e:
        raise WebException("Invalid trait", 400)
      

def validator_trait_textbased(data: str) -> str:
    string = validator_str_range(1, 20)(data)
    try:
        trait = dbm.validators.getValidateTrait(string).get()
        if not trait['textbased']:
            raise WebException("Invalid trait", 400)
        else:
            return string
    except ghostDB.DBException as e:
        raise WebException("Invalid trait", 400)

def validator_bot_user(data: str) -> str:
    iu, _ = dbm.validators.getValidateBotUser(data).validate()
    if not iu:
        raise WebException("Invalid user", 400)
    return data

class Log(WsgiLog): # this shit needs the config to be loaded so it can't be off this file :(
    def __init__(self, application):
        WsgiLog.__init__(
            self,
            application,
            logformat = '%(asctime)s %(levelname)s \t %(message)s',
            tofile = True,
            toprint = True,
            file = config['WebApp']['log_file'],
            interval = config['WebApp']['log_interval'],
            when = config['WebApp']['log_when'],
            backups = config['WebApp']['log_backups']
            )

class WebExceptionLang(WebException):
    def __init__(self, msg: str, langParams: tuple = (), errorcode: int = 0, lid: str = default_language):
        super(WebExceptionLang, self).__init__(lp.get(lid, msg, *langParams), errorcode)

def translate_dbexc(dbexc: ghostDB.DBException, lid: str, errorcode : int= 0) -> WebExceptionLang:
    return WebExceptionLang(dbexc.args[1], dbexc.args[2], errorcode = errorcode, lid = lid)

class WebPageResponseLang(WebPageResponse):
    def __init__(self, config, session, properties = {}, accepted_input = {}, min_access_level = 0):
        super(WebPageResponseLang, self).__init__(config, session, properties, accepted_input, min_access_level)
    def getLangId(self) -> str:
        try:
            return self.session.language
        except AttributeError:
            return getLanguage(self.session, dbm)
    def getString(self, string_id: str, *args):
        return lp.get(self.getLangId(), string_id, *args)
    def getLanguageDict(self):
        return lp.languages[self.getLangId()]
    def getLangException(self, errorcode, string_id, args = ()):
        return WebExceptionLang(string_id, args, errorcode = errorcode, lid = self.getLangId())
    def getLangExceptionFromBDExc(self, dbexc: ghostDB.DBException, errorcode : int = 0):
        return translate_dbexc(dbexc, self.getLangId(), errorcode)

class APIResponseLang(APIResponse):
    def __init__(self, config, session, properties = {}, accepted_input = {}, min_access_level = 0):
        super(APIResponseLang, self).__init__(config, session, properties, accepted_input, min_access_level)
    def getLangId(self) -> str:
        try:
            return self.session.language
        except AttributeError:
            return getLanguage(self.session, dbm)
    def getString(self, string_id: str , *args):
        return lp.get(self.getLangId(), string_id, *args)
    def getLanguageDict(self) -> dict[str, str]:
        return lp.languages[self.getLangId()]
    def getLangException(self, errorcode, string_id, args = ()):
        return WebExceptionLang(string_id, args, errorcode = errorcode, lid = self.getLangId())
    def getLangExceptionFromBDExc(self, dbexc: ghostDB.DBException, errorcode : int = 0):
        return translate_dbexc(dbexc, self.getLangId(), errorcode)
        
class main_page:
    def GET(self):
        web.header('Content-Type', 'text/html')
        return "\n<br/>".join(map(lambda x: "<a href="+web.ctx.home+x+" >"+x+"</a>",urls[::2]))

class doLogin(WebPageResponseLang):
    def __init__(self):
        super(doLogin, self).__init__(config, session)
    def mPOST(self):
        try:
            return render.simplemessage( self.getLanguageDict(),
                                         self.getString("web_already_logged_as", self.session.discord_username, self.session.discord_userdiscriminator)
                                        )
        except AttributeError as e:
            discord = make_session(scope=['identify'])
            authorization_url, state = discord.authorization_url(AUTHORIZATION_BASE_URL)
            self.session.oauth2_state = state
            web.seeother(authorization_url)


class doLogout(WebPageResponse):
    def __init__(self):
        super(doLogout, self).__init__(config, session, min_access_level = 0)
    def mPOST(self):
        self.session.kill()
        web.seeother("/")

class discordCallback(APIResponse):
    def __init__(self):
        super(discordCallback, self).__init__(config, session, accepted_input = {'code': (MAY, validator_str_maxlen(512)),
                                                                                 'error': (MAY, validator_str_maxlen(512)),
                                                                                 'state': (MAY, validator_str_maxlen(512)),
                                                                                 'error_description': (MAY, validator_str_maxlen(512))
                                                                                 })
    def mGET(self):
        if self.input_data['error']:
            return self.input_data['error'] + self.input_data['error_description']
        else:
            # should validate state here?
            if self.session.oauth2_state != self.input_data['state']: # TODO: maybe have all validators in accepted_input be generators what then pass self to the validator -> we can do stuff like validate state directly in the validator and fill fields in the response obects
                raise WebException("Invalid state", 400)
            discord = make_session(state=self.session.oauth2_state)
            token = discord.fetch_token(
                TOKEN_URL,
                code = self.input_data['code'], # optional because we can use authorization_response instead for some reason
                client_secret=OAUTH2_CLIENT_SECRET,
                authorization_response=web.ctx.home + web.ctx.fullpath)
            self.session.oauth2_token = token 
            #---
            discord = make_session(token=self.session.oauth2_token)
            user = discord.get(API_BASE_URL + '/users/@me').json()
            self.session.discord_userid = user['id']
            self.session.discord_username = user['username']
            self.session.discord_userdiscriminator = user['discriminator']

            iu, _ = dbm.validators.getValidateBotUser(self.session.discord_userid).validate()
            #if not iu:
            #    dbm.registerUser(self.session.discord_userid, self.session.discord_username, default_language)

            self.session.language = getLanguage(self.session, dbm)
            
            ba, _ = dbm.validators.getValidateBotAdmin(self.session.discord_userid).validate()
            st, _ = dbm.validators.getValidateBotStoryTeller(self.session.discord_userid).validate()
            if st:
                self.session.access_level = 5
            elif ba:
                self.session.access_level = 10
            elif iu:
                self.session.access_level = 2
            else:
                self.session.access_level = 1
            web.seeother('/')


class listIndex(WebPageResponseLang):
    def __init__(self):
        super(listIndex, self).__init__(config, session)
    def mGET(self):
        return render.simpleListLinks(global_template_params,
                                      {"page_title": self.getString("web_index_page_title"),
                                       "page_container_title": self.getString("web_index_page_container_title"),
                                       },
                                      map(lambda x: {'url': web.ctx.home+urls[x*2], 'text': urls[x*2+1]}, range(len(urls)//2))
                                      )

class session_info(WebPageResponseLang):
    def __init__(self):
        super(session_info, self).__init__(config, session)
    def mGET(self):
        return render.simpleList(global_template_params,
                                 {"page_title": self.getString("web_sessioninfo_page_title"),
                                  "page_container_title": self.getString("web_sessionInfo_page_container_title"),
                                  },
                                 map(lambda k: {'header': k, 'data': self.session[k]}, self.session.keys())
                                 )

class redirectDash(WebPageResponse):
    def __init__(self):
        super(redirectDash, self).__init__(config, session)
    def mGET(self):
        web.seeother("/")

class dashboard(WebPageResponseLang):
    def __init__(self):
        super(dashboard, self).__init__(config, session, accepted_input = {'character': (MAY, validator_character)
                                                                           })
    def mGET(self):
        try:
            return render.dashboard(global_template_params, self.getLanguageDict(), f'{self.session.discord_username}#{self.session.discord_userdiscriminator}', self.getString("web_label_logout"), "doLogout", self.getString("web_default_dashboard_msg_loggedin"))
        except AttributeError:
            return render.dashboard(global_template_params, self.getLanguageDict(), '', self.getString("web_label_login"), "doLogin",  self.getString("web_default_dashboard_msg_notlogged"))
            
my_chars_query_admin = """
select pc.*, cr.id as chronichleid, cr.name as chroniclename, po.name as ownername
from PlayerCharacter pc
join People po on (pc.owner = po.userid)
left join ChronicleCharacterRel ccr on (pc.id = ccr.playerchar)
left join Chronicle cr on (ccr.chronicle = cr.id)"""

my_chars_query_st = """
select distinct pc.*, cr.id as chronichleid, cr.name as chroniclename, po.name as ownername
from PlayerCharacter pc
join People po on (pc.owner = po.userid)
left join ChronicleCharacterRel ccr on (pc.id = ccr.playerchar)
left join Chronicle cr on (ccr.chronicle = cr.id)
left join StoryTellerChronicleRel stcr on (stcr.chronicle = cr.id)
where stcr.storyteller = $storyteller_id
or pc.owner = $userid or pc.player = $userid"""

my_chars_query_player = """
select pc.*, cr.id as chronichleid, cr.name as chroniclename, po.name as ownername
from PlayerCharacter pc
join People po on (pc.owner = po.userid)
left join ChronicleCharacterRel ccr on (pc.id = ccr.playerchar)
left join Chronicle cr on (ccr.chronicle = cr.id)
where pc.owner = $userid or pc.player = $userid"""

class getMyCharacters(APIResponse):
    def __init__(self):
        super(getMyCharacters, self).__init__(config, session)
    def mGET(self):
        try:
            ba, _ = dbm.validators.getValidateBotAdmin(self.session.discord_userid).validate()
            if ba:
                return dbm.db.query(my_chars_query_admin).list()
            st, _ = dbm.validators.getValidateBotStoryTeller(self.session.discord_userid).validate()
            if st:
                return dbm.db.query(my_chars_query_st, vars = dict(storyteller_id = self.session.discord_userid, userid=self.session.discord_userid)).list()
            characters = dbm.db.query(my_chars_query_player, vars=dict(userid=self.session.discord_userid))
            return characters.list()
        except AttributeError as e:
            self.logger.error(f"getMyCharacters error: {e}")
            return []

class getCharacterTraits(APIResponse):
    def __init__(self):
        super(getCharacterTraits, self).__init__(config, session, accepted_input = {'charid': (MUST, validator_character)})
    def mGET(self):
        try:
            ba, _ = dbm.validators.getValidateBotAdmin(self.session.discord_userid).validate()
            st, _ = dbm.validators.getValidateBotStoryTeller(self.session.discord_userid).validate()
            co, _ = dbm.isCharacterOwner(self.session.discord_userid, self.input_data['charid'])
            if (ba or st or co):
                traits = dbm.db.query("""
    SELECT 
        ct.*,
        tr.*, 
        tt.textbased,
        lt.traitName as traitName
    From CharacterTrait ct
    join Trait tr on (ct.trait = tr.id)
    join TraitType tt on (tr.traittype = tt.id)
    left join LangTrait lt on (tr.id = lt.traitid)
    where ct.playerchar = $charid
    and lt.langId = $langid
    order by tr.ordering asc, tr.standard desc, ct.trait asc
    """, vars=dict(charid=self.input_data['charid'], langid = getLanguage(self.session, dbm)))
                return traits.list()
            else:
                return []
        except AttributeError as e:
            self.logger.error(f"getCharacterTraits error: {e}")
            return []

class getClanIcon(APIResponse):
    def __init__(self):
        super(getClanIcon, self).__init__(config, session, accepted_input = {'clan': (MUST, validator_str_maxlen(50))})
    def mGET(self):
        ci = dbm.db.select('ClanInfo', where='clanid = $clanid', vars=dict(clanid = self.input_data['clan']))
        if len(ci):
            return {'clan_icon': f'../img_res/clan_icons/{ci[0]["clanimgurl"]}', 'icon_size': config['WebSite']['clanicon_width']}
        else:
            return {'clan_icon': ""}

class getCharacterModLog(WebPageResponseLang):
    def __init__(self):
        super(getCharacterModLog, self).__init__(config, session, accepted_input = {'charid': (MUST, validator_str_range(1, 20))})
    def mGET(self):
        try:
            ba, _ = dbm.validators.getValidateBotAdmin(self.session.discord_userid).validate()
            st, _ = dbm.validators.getValidateBotStoryTeller(self.session.discord_userid).validate()
            co, _ = dbm.isCharacterOwner(self.session.discord_userid, self.input_data['charid'])
            if (ba or st or co):
                log = dbm.db.query("""
    SELECT *
    From CharacterModLog cml
    join People pp on (cml.userid = pp.userid)
    where cml.charid = $charid
    order by cml.logtime desc
    """, vars=dict(charid=self.input_data['charid'])).list()
                for i in range(len(log)):
                    log[i]["val_type"] = f"web_label_valtype_{log[i]['val_type']}"
                return render.CharacterModLog(global_template_params, self.getLanguageDict(), log)
            else:
                self.logger.warning(f"Modlog was asked for {self.input_data['charid']} by {self.session.discord_userid}, who does not have access to it")
                return ""
        except AttributeError as e:
            self.logger.error(f"getCharacterModLog error: {e}")
            return ""

class getLanguageDictionary(APIResponse):
    def __init__(self):
        super(getLanguageDictionary, self).__init__(config, session)
    def mGET(self):
        return lp.languages[getLanguage(self.session, dbm)]

class editTranslations(WebPageResponseLang):
    def __init__(self):
        super(editTranslations, self).__init__(config, session, min_access_level=5)
    def mGET(self):
        #ba, _ = dbm.isBotAdmin(self.session.discord_userid)
        #st, _ = dbm.isStoryteller(self.session.discord_userid)
        query = """
        select tt.id, lt.langId, lt.traitShort, lt.traitName
        from Trait tt
        join LangTrait lt on (lt.traitId = tt.id and lt.langId = $langId)
        order by tt.standard desc, tt.traittype asc, tt.ordering asc
        """
        traitData = dbm.db.query(query, vars=dict(langId=self.getLangId()))
        return render.translationEdit(global_template_params, self.getLanguageDict(), f'{self.session.discord_username}#{self.session.discord_userdiscriminator}', self.getString("web_label_logout"), "doLogout", traitData)

class editTranslation(APIResponse):
    def __init__(self):
        super(editTranslation, self).__init__(config, session, min_access_level=5, accepted_input = {
            'traitId': (MUST, validator_trait),
            'type': (MUST, validator_set( ("short", "name") )),
            'langId': (MUST, validator_language),
            'value': (MUST, validator_str_range(1, 50)),     
        })
    def mGET(self):
        u = 0
        if self.input_data['type'] == "short":
            u = dbm.db.update("LangTrait", where = 'traitId = $traitId and langId = $langId', vars = dict(traitId=self.input_data['traitId'], langId = self.input_data['langId']), traitShort = self.input_data['value'])
        elif self.input_data['type'] == "name":
            u = dbm.db.update("LangTrait", where = 'traitId = $traitId and langId = $langId', vars = dict(traitId=self.input_data['traitId'], langId = self.input_data['langId']), traitName = self.input_data['value'])
        else: # does not ever happen
            raise WebException("Invalid input", 400)

        if u == 1:
            return self.input_data
        else:
            raise WebException(f"Update failed, {u} rows affected", 500)

#TODO: greedysecurity
def pgmodPermissionCheck_web(issuer_id, character):
    owner_id = character['owner']
    char_id = character['id']
    
    st, _ =  dbm.isStorytellerForCharacter(issuer_id, char_id)
    ba, _ = dbm.validators.getValidateBotAdmin(issuer_id).validate()
    co = False
    if owner_id == issuer_id and not (st or ba):
        #1: unlinked
        cl, _ = dbm.isCharacterLinked(char_id)
        #2 active session somewhere
        sa, _ = dbm.isAnySessionActiveForCharacter(char_id) # do we want this?
        co = co or (not cl) or sa            

    return (st or ba or co)

class editCharacterTraitNumber(APIResponse): # no textbased
    def __init__(self):
        super(editCharacterTraitNumber, self).__init__(config, session, min_access_level=2, accepted_input = {
            'traitId': (MUST, validator_trait_number),
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
            'newValue': (MUST, validator_positive_integer),   
        })
    def mGET(self):
        vl, character = dbm.validators.getValidateCharacter(self.input_data['charId']).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if can_edit:
            trait_id = self.input_data['traitId']
            new_val = self.input_data['newValue']
            charId = self.input_data['charId']
            
            trait = dbm.getTrait(charId, trait_id)
            
            dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=character['id']), cur_value = new_val, max_value = new_val)
            dbm.log(issuer, character['id'], trait_id, ghostDB.LogType.MAX_VALUE, new_val, trait['max_value'], "web")
            dbm.log(issuer, character['id'], trait_id, ghostDB.LogType.CUR_VALUE, new_val, trait['cur_value'], "web")
            return dbm.getTrait_LangSafe(charId, trait_id, getLanguage(self.session, dbm))

        else:
            raise WebException("Permission denied", 403)

class editCharacterTraitNumberCurrent(APIResponse): # no textbased
    def __init__(self):
        super(editCharacterTraitNumberCurrent, self).__init__(config, session, min_access_level=2, accepted_input = {
            'traitId': (MUST, validator_trait_number),
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
            'newValue': (MUST, validator_positive_integer),   
        })
    def mGET(self):
        lid = getLanguage(self.session, dbm)
        vl, character = dbm.validators.getValidateCharacter(self.input_data['charId']).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if can_edit:
            trait_id = self.input_data['traitId']
            new_val = self.input_data['newValue']
            charId = self.input_data['charId']

            trait = dbm.getTrait(charId, trait_id)

            if trait['pimp_max']==0 and trait['trackertype']==0:
                raise WebException(f"Current value cannot be modified")

            if new_val > trait['max_value'] and trait['trackertype'] != 3:
                raise WebException("Value too large", 400)
            
            dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=character['id']), cur_value = new_val)
            dbm.log(issuer, character['id'], trait_id, ghostDB.LogType.CUR_VALUE, new_val, trait['cur_value'], "web edit")
            return dbm.getTrait_LangSafe(charId, trait_id, lid)

        else:
            raise WebException("Permission denied", 403)


class editCharacterTraitText(APIResponse): #textbased
    def __init__(self):
        super(editCharacterTraitText, self).__init__(config, session, min_access_level=2, accepted_input = {
            'traitId': (MUST, validator_trait_textbased), 
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
            'newValue': (MUST, validator_str_range(1, 50)),   
        })
    def mGET(self):
        vl, character = dbm.validators.getValidateCharacter(self.input_data['charId']).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if can_edit:
            trait_id = self.input_data['traitId']
            new_val = self.input_data['newValue']
            charId = self.input_data['charId']
            
            trait = dbm.getTrait(charId, trait_id)
            
            dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=character['id']), text_value = new_val)
            dbm.log(issuer, character['id'], trait_id, ghostDB.LogType.TEXT_VALUE, new_val, trait['text_value'], "web edit")
            return dbm.getTrait_LangSafe(charId, trait_id, getLanguage(self.session, dbm))

        else:
            raise WebException("Permission denied", 403)

class editCharacterTraitRemove(APIResponse): #textbased
    def __init__(self):
        super(editCharacterTraitRemove, self).__init__(config, session, min_access_level=2, accepted_input = {
            'traitId': (MUST, validator_trait), 
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
        })
    def mGET(self):
        vl, character = dbm.validators.getValidateCharacter(self.input_data['charId']).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if can_edit:
            trait_id = self.input_data['traitId']
            charId = self.input_data['charId']
            
            trait = dbm.getTrait(charId, trait_id)

            updated_rows = dbm.db.delete("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']))
            if trait['textbased']:
                dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.DELETE, "", trait['text_value'], "web edit")
            else:
                dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.DELETE, "", f"{trait['cur_value']}/{trait['max_value']}", "web edit")
                
            return {"trait": trait_id}

        else:
            raise WebException("Permission denied", 403)

class traitList(APIResponse): 
    def __init__(self):
        super(traitList, self).__init__(config, session, min_access_level=2)
    def mGET(self):
        query = """
        select t.id as value, CONCAT(lt.traitName, " (", lt.traitShort, ", ", t.traittype, ")") as display
        from Trait t
        join LangTrait lt on (lt.traitId = t.id and lt.langId = $langId)
        order by t.standard desc, t.traittype asc, t.ordering asc
        """
        traitData = dbm.db.query(query, vars=dict(langId=getLanguage(session, dbm))).list()
        return traitData

class editCharacterTraitAdd(APIResponse): #textbased
    def __init__(self):
        super(editCharacterTraitAdd, self).__init__(config, session, min_access_level=2, accepted_input = {
            'traitId': (MUST, validator_str_range(1, 20)), # I'm validating the trait later because I also need trait data
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
        })
    def mGET(self):
        lid = getLanguage(self.session, dbm)
        vl, character = dbm.validators.getValidateCharacter(self.input_data['charId']).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if can_edit:
            trait_id = self.input_data['traitId']
            charId = self.input_data['charId']

            try:
                _ = dbm.getTrait(charId, trait_id)
                raise WebException("The character already has this trait", 400)
            except ghostDB.DBException as e:
                pass
            
            trait =  dbm.validators.getValidateTrait(trait_id).get()
            
            if trait['textbased']:
                textval = ""
                dbm.db.insert("CharacterTrait", trait=trait_id, playerchar=charId, cur_value = 0, max_value = 0, text_value = textval, pimp_max = 0)
                dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.TEXT_VALUE, textval, '', "web edit")
            else:
                numval = 0
                pimp = 6 if trait['traittype'] in ['fisico', 'sociale', 'mentale'] else 0
                dbm.db.insert("CharacterTrait", trait=trait_id, playerchar=charId, cur_value = numval, max_value = numval, text_value = "", pimp_max = pimp)
                dbm.log(issuer, character['id'], trait['id'], ghostDB.LogType.MAX_VALUE, numval, '',  "web edit")

            return dbm.getTrait_LangSafe(charId, trait_id, lid)

        else:
            raise WebException("Permission denied", 403)

class canEditCharacter(APIResponse): #textbased
    def __init__(self):
        super(canEditCharacter, self).__init__(config, session, min_access_level=2, accepted_input = {
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
        })
    def mGET(self):
        lid = getLanguage(self.session, dbm)
        vl, character = dbm.validators.getValidateCharacter(self.input_data['charId']).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if can_edit:
            return 1
        else:
            return 0

class webFunctionVisibility(APIResponse):
    # This call tells the website what functions the user can see, but can easily be circumvented
    # The actual enforcing of these permissions is done on the server side calls of the individual functions
    def __init__(self):
        super(webFunctionVisibility, self).__init__(config, session)
    def mGET(self):
        lid = getLanguage(self.session, dbm)
        ba = False
        st = False
        if "discord_userid" in self.session:
            ba, _ = dbm.validators.getValidateBotAdmin(self.session.discord_userid).validate()
            st, _ = dbm.validators.getValidateBotStoryTeller( self.session.discord_userid).validate()

        return {
            "side_menu": self.session.access_level >= 1, # any logged user
            "new_character": self.session.access_level >= 2, # any logged registered user
            "translate_traits": ba or st, # storytellers or admins
        }

class getModal(WebPageResponseLang):
    def __init__(self):
        super(getModal, self).__init__(config, session, accepted_input = {
            'modalId': (MUST, validator_str_range(1, 30)),
        })
    def mGET(self):
        if self.input_data['modalId'] == 'new_char_modal':
            modal_params = {
                "modal_id": self.input_data['modalId']
            }
            return render.newCharModal(global_template_params, self.getLanguageDict(), modal_params)
        
        raise WebException("Invalid modal id", 400)

class newCharacter(APIResponseLang):
    def __init__(self):
        super(newCharacter, self).__init__(config, session, min_access_level=2, accepted_input = {
            'charId': (MUST, validator_str_range(1, 20)),
            'charName': (MUST, validator_str_range(1, 50)),
        })
    def mGET(self):
        lid = getLanguage(self.session, dbm)

        iu, _ = dbm.validators.getValidateBotUser(self.session.discord_userid).validate()
        if not iu:
            raise WebException("Only registered users can create new characters!", 400)

        vl, character = dbm.validators.getValidateCharacter(self.input_data['charId']).validate()
        if vl:
            raise self.getLangException(400, "string_error_character_already_exists")
        
        chid = self.input_data['charId']
        owner = self.session.discord_userid
        fullname = self.input_data['charName']

        if " " in chid: # todo: validator
            raise self.getLangException(400, "string_error_char_not_allowed")
        
        # todo: create chars for other people
        try:
            dbm.newCharacter(chid, fullname, owner)
            return self.input_data # idk
        except ghostDB.DBException as e:
            raise self.getLangExceptionFromBDExc(e, 400)

class userList(APIResponse): # TODO: maybe a standardized autocomplete list response class for input modals?
    def __init__(self):
        super(userList, self).__init__(config, session, min_access_level=2) 
    def mGET(self):
        query = """
        select p.userid  as value, p.name as display
        from People p
        """
        # only storytellers and admins can see the list of registered users, but we can still reassign if we know the discordid (as you would on the bot)
        issuer_id = self.session.discord_userid
        st, _ = dbm.validators.getValidateBotStoryTeller(issuer_id).validate()
        ba, _ = dbm.validators.getValidateBotAdmin(issuer_id).validate()
        data  = []
        if st or ba:
            data = dbm.db.query(query, vars=dict(langId=getLanguage(session, dbm))).list()
        return data

class editCharacterReassign(APIResponse): #textbased
    def __init__(self):
        super(editCharacterReassign, self).__init__(config, session, min_access_level=2, accepted_input = {
            'userId': (MUST, validator_str_range(1, 32)), 
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
        })
    def mGET(self):
        charId = self.input_data['charId']
        userId = self.input_data['userId']

        vl, character = dbm.validators.getValidateCharacter(self.input_data['charId']).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        vu, user = dbm.validators.getValidateBotUser(userId).validate()
        if not vu:
            raise WebException("Invalid user", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if can_edit:
            dbm.reassignCharacter(charId, userId)
            return user
        else:
            raise WebException("Permission denied", 403)

class getCharacterNote(APIResponse):
    def __init__(self):
        super(getCharacterNote, self).__init__(config, session, min_access_level=2, accepted_input = {
            'noteId': (MUST, validator_str_range(1, 50)), 
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
        })
    def mGET(self):
        charId = self.input_data['charId']
        noteId = self.input_data['noteId']
        issuer = self.session.discord_userid

        vl, character = dbm.validators.getValidateCharacter(charId).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if not can_edit:
            raise WebException("Permission denied", 403)
        
        vn, note = dbm.validators.getValidateCharacterNote(charId, noteId, issuer).validate()
        if not vn:
            raise WebException("No such note", 404)
            
        return note

class getCharacterNotesList(APIResponse):
    def __init__(self):
        super(getCharacterNotesList, self).__init__(config, session, min_access_level=2, accepted_input = {
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
        })
    def mGET(self):
        charId = self.input_data['charId']
        issuer = self.session.discord_userid

        vl, character = dbm.validators.getValidateCharacter(charId).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if not can_edit:
            raise WebException("Permission denied", 403)
        
        results = dbm.db.select('CharacterNotes', where='charid=$charId and userid=$userId', vars=dict(charId=charId, userId=issuer), what='noteid')
        return results.list()

class saveCharacterNote(APIResponse):
    def __init__(self):
        super(saveCharacterNote, self).__init__(config, session, min_access_level=2, accepted_input = {
            'noteId': (MUST, validator_str_range(1, 50)), 
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
            'noteText':  (MUST, validator_str_range(0, 65535)),
        })
    def mPOST(self):
        charId = self.input_data['charId']
        noteId = self.input_data['noteId']
        noteText = self.input_data['noteText']
        issuer = self.session.discord_userid

        vl, character = dbm.validators.getValidateCharacter(charId).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if not can_edit:
            raise WebException("Permission denied", 403)

        vn, _ =  dbm.validators.getValidateCharacterNote(charId, noteId, issuer).validate()
        if not vn:
            raise WebException("No such note", 404)
        
        updated_rows = dbm.db.update("CharacterNotes", where='charid=$charId and userid=$userId and noteid=$noteId', vars=dict(charId=charId, noteId=noteId, userId=issuer), notetext = noteText)
            
        return [updated_rows]

class deleteCharacterNote(APIResponse):
    def __init__(self):
        super(deleteCharacterNote, self).__init__(config, session, min_access_level=2, accepted_input = {
            'noteId': (MUST, validator_str_range(1, 50)), 
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
        })
    def mPOST(self):
        charId = self.input_data['charId']
        noteId = self.input_data['noteId']
        issuer = self.session.discord_userid

        vl, character = dbm.validators.getValidateCharacter(charId).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if not can_edit:
            raise WebException("Permission denied", 403)

        vn, _ =  dbm.validators.getValidateCharacterNote(charId, noteId, issuer).validate()
        if not vn:
            raise WebException("No such note", 404)
        
        updated_rows = dbm.db.delete("CharacterNotes", where='charid=$charId and userid=$userId and noteid=$noteId', vars=dict(charId=charId, noteId=noteId, userId=issuer))
            
        return [updated_rows]

class newCharacterNote(APIResponse):
    def __init__(self):
        super(newCharacterNote, self).__init__(config, session, min_access_level=2, accepted_input = {
            'noteId': (MUST, validator_str_range(1, 50)), 
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
        })
    def mPOST(self):
        charId = self.input_data['charId']
        noteId = self.input_data['noteId']
        issuer = self.session.discord_userid

        vl, character = dbm.validators.getValidateCharacter(charId).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if not can_edit:
            raise WebException("Permission denied", 403)
        
        dbm.db.insert("CharacterNotes", charid=charId, noteid=noteId, userid=issuer)
            
        return [noteId]

class characterNotesPage(WebPageResponseLang):
    def __init__(self):
        super(characterNotesPage, self).__init__(config, session, min_access_level=2, accepted_input = {
            'charId': (MUST, validator_str_range(1, 20)), # I'm validating the character later because I also need character data
        })
    def mGET(self):
        charId = self.input_data['charId']
        issuer = self.session.discord_userid

        vl, character = dbm.validators.getValidateCharacter(charId).validate()
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if not can_edit:
            raise WebException("Permission denied", 403)
        
        return render.characterNotes(global_template_params, self.getLanguageDict())

if __name__ == "__main__":
    app.run(Log)
else:
    application = app.wsgifunc(Log)
