#!/usr/bin/env python3

import sys, os
abspath = os.path.dirname(__file__)+"/"
sys.path.append(abspath)

import web, configparser
import subprocess, json, time, datetime
from requests_oauthlib import OAuth2Session

from pyresources.UtilsWebLib import *
import pyresources.ghostDB as ghostDB

config = configparser.ConfigParser()
config.read("/var/www/greedy_ghost_web.ini")

# stuff that gets passed to all templates
global_template_params = {
    }

urls = (
    '', 'main_page',
    '/', 'listIndex',
    '/login', 'loginPage',
    '/doLogin', 'doLogin',
    '/discordCallback', 'discordCallback',
    '/session_info', 'session_info',
    '/dashboard', 'dashboard',
    '/getMyCharacters', 'getMyCharacters',
    '/getCharacterTraits', 'getCharacterTraits'
    )

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

class main_page:
    def GET(self):
        web.header('Content-Type', 'text/html')
        return "\n<br/>".join(map(lambda x: "<a href="+web.ctx.home+x+" >"+x+"</a>",urls[::2]))

class loginPage(WebPageResponse):
    def __init__(self):
        super(loginPage, self).__init__(config, session)
    def mGET(self):
        try:
            return render.simplemessage(f'already logged in as: {self.session.discord_username}#{self.session.discord_userdiscriminator}')
        except AttributeError as e:  
            return render.login("doLogin")

class doLogin(WebPageResponse):
    def __init__(self):
        super(doLogin, self).__init__(config, session)
    def mPOST(self):
        try:
            return render.simplemessage(f'already logged in as: {self.session.discord_username}#{self.session.discord_userdiscriminator}')
        except AttributeError as e:
            discord = make_session(scope=['identify'])
            authorization_url, state = discord.authorization_url(AUTHORIZATION_BASE_URL)
            self.session.oauth2_state = state
            raise web.seeother(authorization_url)

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
            raise web.seeother('/dashboard')


class listIndex(WebPageResponse):
    def __init__(self):
        super(listIndex, self).__init__(config, session)
    def mGET(self):
        return render.simpleListLinks(global_template_params,
                                      {"page_title": "Index Page",
                                       "page_container_title": "Available pages:"
                                       },
                                      map(lambda x: {'url': web.ctx.home+urls[x*2], 'text': urls[x*2+1]}, range(len(urls)//2))
                                      )

class session_info(WebPageResponse):
    def __init__(self):
        super(session_info, self).__init__(config, session)
    def mGET(self):
        return render.simpleList(global_template_params,
                                 {"page_title": "Session Information",
                                  "page_container_title": "Session Parameters:"
                                  },
                                 map(lambda k: {'header': k, 'data': self.session[k]}, self.session.keys())
                                 )

class dashboard(WebPageResponse):
    def __init__(self):
        super(dashboard, self).__init__(config, session)
    def mGET(self):
        return render.dashboard(global_template_params)

class getMyCharacters(APIResponse):
    def __init__(self):
        super(getMyCharacters, self).__init__(config, session)
    def mGET(self):
        try:
            ba, _ = dbm.isBotAdmin(self.session.discord_userid)
            if ba:
                return dbm.db.select('PlayerCharacter').list()
            st, _ = dbm.isStoryteller(self.session.discord_userid)
            if st:
                return dbm.db.select('PlayerCharacter').list() # todo solo i suoi
            characters = dbm.db.select('PlayerCharacter',  where='owner = $userid or player = $userid', vars=dict(userid=self.session.discord_userid))
            return characters.list()
        except AttributeError as e:  
            return []


class getCharacterTraits(APIResponse):
    def __init__(self):
        super(getCharacterTraits, self).__init__(config, session, accepted_input = {'charid': (MUST, validator_str_maxlen(20))})
    def mGET(self):
        try:
            ba, _ = dbm.isBotAdmin(self.session.discord_userid)
            st, _ = dbm.isStoryteller(self.session.discord_userid)
            co, _ = dbm.isCharacterOwner(self.session.discord_userid, self.input_data['charid'])
            if (ba or st or co):
                traits = dbm.db.query("""
    SELECT  ct.*, tr.*, tt.textbased
    From CharacterTrait ct
    join Trait tr on (ct.trait = tr.id)
    join TraitType tt on (tr.traittype = tt.id)
    where ct.playerchar = $charid
    order by tr.ordering asc, tr.standard desc, ct.trait asc
    """, vars=dict(charid=self.input_data['charid']))
                return traits.list()
            else:
                return []
        except AttributeError as e:  
            return []



if __name__ == "__main__":
    app.run(Log)
else:
    application = app.wsgifunc(Log)
