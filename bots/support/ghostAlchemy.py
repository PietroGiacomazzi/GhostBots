from configparser import ConfigParser

import sqlalchemy
import sqlalchemy.orm

import lang.lang as lng
from .utils import *

## Errors ##

class DBException(lng.LangSupportException):
    pass

## Constants ##

# Table names

TABLENAME_USERS = 'People'

# Config

CONFIGKEY_DB_DIALECT  = 'type'
CONFIGKEY_DB_DRIVER   = 'dbdriver'
CONFIGKEY_DB_USERNAME = 'user'
CONFIGKEY_DB_PASSWORD = 'pw'
CONFIGKEY_DB_HOST     = 'host'
CONFIGKEY_DB_DATABASE = 'database'

## ORM Mapping  ##

class GhostBase(sqlalchemy.orm.DeclarativeBase):
    """ TODO DOCUMENTATION """

    @classmethod
    def getRecord(cls, session: sqlalchemy.orm.Session, *pk):
        """ Performs get logic for the Table with the specified primary key:

        If a record is found, it is returned, 
        If no record is found, a DBException is raised """
        result =  session.get(cls, *pk)
        if result is None:
            raise cls.constructNotFoundError(pk)
        return result
    
    @classmethod
    def validateRecord(cls, session: sqlalchemy.orm.Session, *pk):
        """ Performs validation logic for the Table with the specified primary key:

        If at least one record is found, this method returns (True, Table) 
        If no record is found, this method returns (False, DBException), where the exception is the one thrown by the get method """
        try:
            return True, cls.getRecord(session, *pk)
        except DBException as e:
            return False, e

    @classmethod
    def getNotFoundMsg(cls) -> str:
        return 'Entity record in {} not found: {}'

    @classmethod
    def getNotFoundMsgParameters(cls, pk) -> tuple:
        return cls.__tablename__,  ", ".join(pk)
        
    @classmethod
    def constructNotFoundError(cls, pk) -> DBException:
        """ Constructs an error that is going to get thrown when no record is found """
        return DBException(cls.getNotFoundMsg(), cls.getNotFoundMsgParameters(pk)) 

class User(GhostBase):
    """ TODO DOCUMENTATION """
    __tablename__ = TABLENAME_USERS

    userid: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(sqlalchemy.String(32), primary_key=True)
    name: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(sqlalchemy.String(50))
    langId: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(sqlalchemy.String(3))

    #addresses: sqlalchemy.orm.Mapped[List["Address"]] = sqlalchemy.orm.relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"User(userid={self.userid!r}, name={self.name!r}, langId={self.langId!r})"

    @classmethod
    def getNotFoundMsg(cls) -> str:
        return 'string_error_user_not_found'

# management

class AlchemyManager:
    """ TODO DOCUMENTATION """
    def __init__(self, config: ConfigParser) -> None:
        dbstring = f"{config[CONFIGKEY_DB_DIALECT]}+{config[CONFIGKEY_DB_DRIVER]}" if CONFIGKEY_DB_DRIVER in config else config[CONFIGKEY_DB_DIALECT]
        url_object = sqlalchemy.URL.create(
            dbstring,
            username=config[CONFIGKEY_DB_USERNAME],
            password=config[CONFIGKEY_DB_PASSWORD], 
            host=config[CONFIGKEY_DB_HOST],
            database=config[CONFIGKEY_DB_DATABASE],
        )
        self.engine = sqlalchemy.create_engine(url_object, echo=True)
        self.Session = sqlalchemy.orm.sessionmaker(self.engine)
    def getUsers(self, session: sqlalchemy.orm.Session):
        stmt = sqlalchemy.select(User)
        return session.scalars(stmt)

class ExecutionContext:
    """ TODO DOCUMENTATION """

    userData = None 
    language_id = None

    execution_session: sqlalchemy.orm.Session = None

    def getUserId(self) -> int:
        raise NotImplementedError()
    def getGuildId(self) -> int:
        raise NotImplementedError()
    def getChannelId(self) -> int:
        raise NotImplementedError
    def getDBManager(self):
        """ to be deprecated"""
        raise NotImplementedError()
    def getAlchemyManager(self) -> AlchemyManager:
        raise NotImplementedError()
    def getDefaultLanguageId(self) -> str:
        raise NotImplementedError()
    def getAppConfig(self) -> ConfigParser:
        raise NotImplementedError()
    def getLanguageProvider(self) -> lng.LanguageStringProvider:
        raise NotImplementedError()
    def getMessageContents(self) -> str:
        raise NotImplementedError()

    def getSession(self) -> sqlalchemy.orm.Session:
        if self.execution_session is None:
            self.execution_session = self.getAlchemyManager().Session()
        return self.execution_session
    def __del__(self):
        if not self.execution_session is None:
            self.execution_session.rollback()

    def _checkLoadUserInfo(self):
        if self.userData is None:
            _, self.userData = User.validateRecord(self.getSession(), self.getUserId())
            if isinstance(self.userData, User):
                self.language_id = self.userData.langId
            else:
                self.language_id = self.getDefaultLanguageId()
    def getLID(self) -> str:
        self._checkLoadUserInfo()
        return self.language_id
    def validateUserInfo(self):
        self._checkLoadUserInfo()
        return isinstance(self.userData, User), self.userData
    def getUserInfo(self):
        self._checkLoadUserInfo()

        if isinstance(self.userData, User):
            return self.userData
        else:
            raise self.userData