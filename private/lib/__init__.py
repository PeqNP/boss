#
# Provides general library facilities
#

import inspect
import logging
import logging.config
import os
import platform
import sys

from enum import Enum, unique
from json import dumps, loads
from logging.handlers import SMTPHandler, RotatingFileHandler
from typing import Union

from yaml import load, dump, safe_load
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except:
    from yaml import Loader, Dumper

CHARS = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

CONFIG = False

class LibraryError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

@unique
class Environment(Enum):
    DEV = "dev"
    PROD = "prod"

class Config(object):
    def __init__(
        self,
        path,
        env,
        db_path,
        boss_path,
        sandbox_path,
        hmac_key,
        host,
        media_path,
        log_path,
        login_enabled,
        jira_url
    ):
        # Path to config file e.g. `~/.boss/config`
        self.path = path
        self.env = Environment(env)
        self.db_path = db_path
        self.boss_path = boss_path
        self.sandbox_path = sandbox_path
        self.hmac_key = hmac_key
        self.host = host
        self.media_path = media_path
        self.log_path = log_path
        self.login_enabled = login_enabled
        self.jira_url = jira_url

def get_config_dir():
    home_path = os.path.expanduser("~")
    config_dir = os.path.join(home_path, ".boss")
    return config_dir

def get_config_path():
    config_path = os.path.join(get_config_dir(), "config")
    return config_path

def get_log_path():
    # home_path = os.path.expanduser("~")
    # config_dir = os.path.join(home_path, "log")
    config = get_config()
    return config.log_path

def get_raw_config():
    config_path = get_config_path()
    if not os.path.isfile(config_path):
        raise LibraryError(f"The configuration file was not found at path ({config_path})")
    with open(config_path, "r") as fh:
        data = read_yaml(fh)
    return data

def get_config():
    global CONFIG
    if CONFIG:
        return CONFIG
    cfg = get_raw_config()

    def get(key):
        val = cfg.get(key, None)
        if val is None:
            raise LibraryError(f"Config file is missing value for ({key}). Please add to `~/boss/config`")
        return val

    config = Config(
        get_config_dir(),
        get("env"),
        get("db_path"),
        get("boss_path"),
        get("sandbox_path"),
        get("hmac_key"),
        get("host"),
        get("media_path"),
        get("log_path"),
        get("login_enabled"),
        get("jira_url"),
    )
    CONFIG = config
    return config

def check_dir(path, name):
    path = path.strip().rstrip("/")
    if not os.path.isdir(path):
        raise LibraryError(f"The {name} directory does not exist at path ({path})")
    return path

class HostnameFilter(logging.Filter):
    hostname = platform.node()

    def filter(self, record):
        record.hostname = HostnameFilter.hostname
        return True

class BOSSSMTPHandler(SMTPHandler):
    def getSubject(self, record):
        if "lib/" in record.pathname:
            filename = f"lib/{record.pathname.split('lib/')[1]}"
        elif "public/" in record.pathname:
            filename = f"public/{record.pathname.split('public/')[1]}"
        elif "private/" in record.pathname:
            filename = f"private/{record.pathname.split('private/')[1]}"
        else:
            filename = f"unknown/{os.path.basename(record.pathname)}"
        return f"Server Error @ ({record.hostname}) ({filename})"

def filter_info_below(level):
    level = getattr(logging, level)

    def filter(record):
        return record.levelno <= level

    return filter

LOG_CONFIG = '''
{
    "version": 1,
    "disable_existing_loggers": false,
    "formatters": {
        "simple": {
            "format": "%(asctime)s.%(msecs)03d %(levelname)s %(module)s:%(funcName)s:%(lineno)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "filters": {
        "info_below": {
            "()" : "lib.filter_info_below",
            "level": "INFO"
        }
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "stream": "ext://sys.stdout",
            "filters": ["info_below"]
        },
        "stderr": {
            "class": "logging.StreamHandler",
            "level": "WARNING",
            "formatter": "simple",
            "stream": "ext://sys.stderr"
        }
    },
    "root": {
        "level": "DEBUG",
        "handlers": [
            "stderr",
            "stdout"
        ]
    }
}
'''

def configure_logging(level: int, service_name: str=None, backup_count: int=None, enable_smtp: bool=None, ignore_init: bool=None, log_to_console: bool=None):
    """ Configure logging for a service or script.

    @param level - The min logging level to emit. Any level below configured
    level is ignored.
    @param service_name - name of service emitting logs
    @param backup_count - the number of rolling logs to create
    @param enable_smtp - will send logs to email if `True`
    @param ignore_init - will not emit initialization logs w/ config info
    """
    if log_to_console is None:
        log_to_console = True
    # If service name is not provided, use the name of the file that initiated
    # the script.
    if not service_name:
        service_name = inspect.stack()[-1].filename
    if not backup_count:
        backup_count = 5
    logger = logging.getLogger()
    # This must be set to the lowest level, or they will be filtered out before
    # the log gets to the handlers. The handlers are responsible for emitting
    # the respective log levels.
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)s %(module)s:%(funcName)s:%(lineno)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    log_path = os.path.join(get_log_path(), os.path.basename(service_name).replace(".py", ".log"))
    if not ignore_init:
        logging.info(f"Rotating log @ ({log_path})")
    # Add console logger if in dev
    cfg = get_config()
    if cfg.env == Environment.DEV and log_to_console:
        logging.config.dictConfig(loads(LOG_CONFIG))
    else:
        logger.handlers = []
    logger.setLevel(level)
    rotate_handler = RotatingFileHandler(
        log_path,
        # 1024 B = 1 KB
        # 1024 KB = 1 MB
        # 16 MB
        maxBytes=1024 * 1024 * 16,
        backupCount=backup_count
    )
    rotate_handler.setLevel(level)
    rotate_handler.setFormatter(formatter)
    logger.addHandler(rotate_handler)
    # For now, ignore mail as it is not tested
    if True:
        return
    # Regardless of environment, if this is `False`, disable it. Default is `None`.
    # Therefore, `enable_smtp` will be ignored if it's not set.
    if enable_smtp is False:
        return
    # Disable sending logs to dev SMTP server, unless `enable_smtp` is `True`
    if cfg.env == Environment.DEV and not enable_smtp:
        return
    logger.info("Logging to SMTP server on WARNING level")
    smtp_handler = BOSSSMTPHandler(
        mailhost="localhost", # Can cfg.host be used?
        fromaddr=cfg.fromaddr,
        toaddrs=[cfg.toaddr],
        subject="@ys service error",
        secure=None
    )
    smtp_handler.setLevel(logging.WARNING)
    smtp_handler.addFilter(HostnameFilter())
    smtp_handler.setFormatter(formatter)
    logger.addHandler(smtp_handler)

# YAML

def load_yaml(data: str) -> dict:
    """ Create Python dict from YAML string. """
    return safe_load(data)

def make_yaml(dictionary: dict) -> str:
    """ Returns a YAML string given a Python dict. """
    return dump(dictionary)

def make_protobuf_yaml(proto: any) -> str:
    """ Returns a YAML string given a protocol buffer. """
    return make_yaml(protobuf_to_dict(proto))

def read_yaml(fh):
    return load(fh, Loader=Loader)

def write_yaml(fh, obj: dict):
    dump(obj, fh)

# Misc

def pretty_json(j: dict):
    """ Returns prettified JSON. Make sure to `print` the return in order
    for formatting to work. """
    return dumps(j, indent=4)

def print_exc(msg: Union[str, None]=None) -> None:
    if msg:
        logging.error(msg)
    err = traceback.format_exc()
    logging.error(err)

def get_bool(value: any) -> bool:
    t = type(value)
    if t is bool:
        return value
    elif t is int or t is float:
        return value != 0
    elif t is str:
        return value.lower() in ["true", "1", "yes"]
    else:
        return bool(value) # Not sure what to do
