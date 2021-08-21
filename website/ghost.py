#!/usr/bin/env python3

import sys, os
abspath = os.path.dirname(__file__)+"/"
sys.path.append(abspath)

import web, configparser
import subprocess, json, time, datetime
from requests_oauthlib import OAuth2Session

from pyresources.UtilsWebLib import *
import pyresources.ghostDB as ghostDB
import pyresources.lang as lng

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
    "/editCharacterTraitText", "editCharacterTraitText"
    )


web.config.session_parameters['samesite'] = 'Lax'
web.config.session_parameters['secure'] = True

app = web.application(urls, globals())#, autoreload=False) # the autoreload bit fucks with sessions
session = web.session.Session(app, web.session.DiskStore(config['WebApp']['sessions_path']), initializer={'access_level': 0})
render = web.template.render(abspath+'templates')
#db = web.database(dbn=config['Database']['type'], user=config['Database']['user'], pw=config['Database']['pw'], db=config['Database']['database'])
dbm = ghostDB.DBManager(config['Database'])

OAUTH2_CLIENT_ID = config['Discord']['OAUTH2_CLIENT_ID']
OAUTH2_CLIENT_SECRET = config['Discord']['OAUTH2_CLIENT_SECRET']
OAUTH2_REDIRECT_URI = config['Discord']['OAUTH2_REDIRECT_URI']

API_BASE_URL = 'https://discordapp.com/api'
AUTHORIZATION_BASE_URL = API_BASE_URL + '/oauth2/authorize'
TOKEN_URL = API_BASE_URL + '/oauth2/token'

default_language = config['WebApp']['default_language']
lp = lng.LanguageStringProvider(abspath+"pyresources")

# --- STUFF ---

def getLanguage(session, dbm):
    try:
        return dbm.getUserLanguage(session.discord_userid)
    except ghostDB.DBException:
        return default_language
    except AttributeError:
        return default_language

def token_updater(token):
    session.oauth2_token = token

def make_session(token=None, state=None, scope=None):
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

def validator_character(data):
    string = validator_str_range(1, 20)(data)
    vl, _ = dbm.isValidCharacter(data)
    if not vl:
        raise WebException("Invalid character", 400)
    else:
        return string

def validator_language(data):
    string = validator_str_range(1, 3)(data)
    vl, _ = dbm.isValidLanguage(string)
    if not vl:
        raise WebException("Unsupported language", 400)
    else:
        return string

def validator_trait(data):
    string = validator_str_range(1, 20)(data)
    vl, _ = dbm.isValidTrait(string)
    if not vl:
        raise WebException("Invalid trait", 400)
    else:
        return string

def validator_trait_number(data):
    string = validator_str_range(1, 20)(data)
    try:
        trait = dbm.getTraitInfo(string)
        if trait['textbased']:
            raise WebException("Invalid trait", 400)
        else:
            return string
    except ghostDB.DBException as e:
        raise WebException("Invalid trait", 400)
      

def validator_trait_textbased(data):
    string = validator_str_range(1, 20)(data)
    try:
        trait = dbm.getTraitInfo(string)
        if not trait['textbased']:
            raise WebException("Invalid trait", 400)
        else:
            return string
    except ghostDB.DBException as e:
        raise WebException("Invalid trait", 400)

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

class WebPageResponseLang(WebPageResponse):
    def __init__(self, config, session, properties = {}, accepted_input = {}, min_access_level = 0):
        super(WebPageResponseLang, self).__init__(config, session, properties, accepted_input, min_access_level)
    def getLangId(self):
        try:
            return self.session.language
        except AttributeError:
            return getLanguage(self.session, dbm)
    def getString(self, string_id, *args):
        return lp.get(self.getLangId(), string_id, *args)
    def getLanguageDict(self):
        return lp.languages[self.getLangId()]
        
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
            raise web.seeother(authorization_url)


class doLogout(WebPageResponse):
    def __init__(self):
        super(doLogout, self).__init__(config, session, min_access_level = 0)
    def mPOST(self):
        self.session.kill()
        raise web.seeother("/")

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
            discord = make_session(state=self.session.oauth2_state)
            token = discord.fetch_token(
                TOKEN_URL,
                client_secret=OAUTH2_CLIENT_SECRET,
                authorization_response=web.ctx.home + web.ctx.fullpath)
            self.session.oauth2_token = token
            #---
            discord = make_session(token=self.session.oauth2_token)
            user = discord.get(API_BASE_URL + '/users/@me').json()
            self.session.discord_userid = user['id']
            self.session.discord_username = user['username']
            self.session.discord_userdiscriminator = user['discriminator']
            self.session.language = getLanguage(self.session, dbm)
            
            ba, _ = dbm.isBotAdmin(self.session.discord_userid)
            st, _ = dbm.isStoryteller(self.session.discord_userid)
            if st:
                self.session.access_level = 5
            elif ba:
                self.session.access_level = 10
            else:
                self.session.access_level = 1
            raise web.seeother('/')


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
            ba, _ = dbm.isBotAdmin(self.session.discord_userid)
            if ba:
                return dbm.db.query(my_chars_query_admin).list()
            st, _ = dbm.isStoryteller(self.session.discord_userid)
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
            ba, _ = dbm.isBotAdmin(self.session.discord_userid)
            st, _ = dbm.isStoryteller(self.session.discord_userid)
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
            ba, _ = dbm.isBotAdmin(self.session.discord_userid)
            st, _ = dbm.isStoryteller(self.session.discord_userid)
            co, _ = dbm.isCharacterOwner(self.session.discord_userid, self.input_data['charid'])
            if (ba or st or co):
                log = dbm.db.query("""
    SELECT *
    From CharacterModLog cml
    join People pp on (cml.userid = pp.userid)
    where cml.charid = $charid
    order by cml.logtime desc
    """, vars=dict(charid=self.input_data['charid']))
                return render.CharacterModLog(global_template_params, self.getLanguageDict(), log.list())
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
            'value': (MUST, validator_str_maxlen(50)),     
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



def pgmodPermissionCheck_web(issuer_id, character):
    owner_id = character['owner']
    char_id = character['id']
    
    st, _ =  dbm.isStorytellerForCharacter(issuer_id, char_id)
    ba, _ = dbm.isBotAdmin(issuer_id)
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
        super(editCharacterTraitNumber, self).__init__(config, session, min_access_level=1, accepted_input = {
            'traitId': (MUST, validator_trait_number),
            'charId': (MUST, validator_str_maxlen(20)), # I'm validating the character later because I also need character data
            'newValue': (MUST, validator_positive_integer),   
        })
    def mGET(self):
        vl, character = dbm.isValidCharacter(self.input_data['charId'])
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if can_edit:
            trait_id = self.input_data['traitId']
            new_val = self.input_data['newValue']
            charId = self.input_data['charId']
            
            ptraits = dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=character['id'])).list()
            if not len(ptraits):
                raise WebException(f"{character['fullname']} does not have the {trait_id} trait", 500)
            
            else:
                dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=character['id']), cur_value = new_val, max_value = new_val)
                dbm.log(issuer, character['id'], trait_id, ghostDB.LogType.MAX_VALUE, new_val, ptraits[0]['max_value'], "web")
                dbm.log(issuer, character['id'], trait_id, ghostDB.LogType.CUR_VALUE, new_val, ptraits[0]['cur_value'], "web")
                return dbm.getTrait_LangSafe(charId, trait_id, getLanguage(self.session, dbm))

        else:
            raise WebException("Permission denied", 403)

class editCharacterTraitText(APIResponse): #textbased
    def __init__(self):
        super(editCharacterTraitText, self).__init__(config, session, min_access_level=1, accepted_input = {
            'traitId': (MUST, validator_trait_textbased), 
            'charId': (MUST, validator_str_maxlen(20)), # I'm validating the character later because I also need character data
            'newValue': (MUST, validator_str_maxlen(50)),   
        })
    def mGET(self):
        vl, character = dbm.isValidCharacter(self.input_data['charId'])
        if not vl:
            raise WebException("Invalid character", 400)

        issuer = self.session.discord_userid
        can_edit = pgmodPermissionCheck_web(issuer, character)

        if can_edit:
            trait_id = self.input_data['traitId']
            new_val = self.input_data['newValue']
            charId = self.input_data['charId']
            
            ptraits = dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=character['id'])).list()
            if not len(ptraits):
                raise WebException(f"{character['fullname']} does not have the {trait_id} trait", 500)
            
            else:
                dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=character['id']), text_value = new_val)
                dbm.log(issuer, character['id'], trait_id, ghostDB.LogType.TEXT_VALUE, new_val, ptraits[0]['text_value'], "web")
                return dbm.getTrait_LangSafe(charId, trait_id, getLanguage(self.session, dbm))

        else:
            raise WebException("Permission denied", 403)

if __name__ == "__main__":
    app.run(Log)
else:
    application = app.wsgifunc(Log)
