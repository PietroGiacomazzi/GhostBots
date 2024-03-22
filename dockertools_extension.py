import dockertools.extensions as ex
import dockertools.tools as tl
import configparser, logging

_log = logging.getLogger(__name__)

@ex.extension_point(ex.ExtensionPoint.VOLUME_IDENTIFICATION_ISFILE)
def volume_isfile(config: configparser.ConfigParser) -> dict[str, bool]:
    return {
        '/db-backup': False,
        '/bots/config.ini': True,
        '/bots/possumconfig.ini': True,
        '/website/config.ini': True
    }