#coding=utf-8

import logging
import logging.handlers
import os

from logging import info, warning, error, debug, critical
from logging import INFO, WARN, ERROR, DEBUG, CRITICAL

warn = warning

__all__ = [
    "info",
    "warn",
    "error",
    "debug",
    "critical",
    "warn",
    "INFO",
    "WARN",
    "ERROR",
    "DEBUG",
    "CRITICAL",
    "FATAL",
    "basicConfig",
]


def basicConfig(**kwargs):
    logging._acquireLock()
    root = logging.root
    try:
        handlers = kwargs.pop("handlers", None)
        if handlers is None:
            if "stream" in kwargs and "filename" in kwargs:
                raise ValueError(
                    "'stream' and 'filename' should not be " "specified together"
                )
        else:
            if "stream" in kwargs or "filename" in kwargs:
                raise ValueError(
                    "'stream' or 'filename' should not be "
                    "specified together with 'handlers'"
                )
        if handlers is None:
            filename = kwargs.pop("filename", None)
            mode = kwargs.pop("filemode", "a")
            if filename:
                h = logging.FileHandler(filename, mode)
            else:
                stream = kwargs.pop("stream", None)
                h = logging.StreamHandler(stream)
            handlers = [h]
        dfs = kwargs.pop("datefmt", None)
        style = kwargs.pop("style", "%")
        if style not in logging._STYLES:
            raise ValueError(
                "Style must be one of: %s" % ",".join(logging._STYLES.keys())
            )
        fs = kwargs.pop("format", logging._STYLES[style][1])
        fmt = logging.Formatter(fs, dfs, style)
        for h in root.handlers:
            root.removeHandler(h)
        for h in handlers:
            if h.formatter is None:
                h.setFormatter(fmt)
            root.addHandler(h)
        level = kwargs.pop("level", None)
        if level is not None:
            root.setLevel(level)
        if kwargs:
            keys = ", ".join(kwargs.keys())
            raise ValueError("Unrecognised argument(s): %s" % keys)
    finally:
        logging._releaseLock()


basicConfig(
    format="{levelname:1.1s}{asctime}.{msecs:03.0f} {module}:{lineno}] {message}",
    datefmt="%m%d %H:%M:%S",
    level=INFO,
    style="{",
)

class Logger(object):

    def __init__(self, logName, logDir=None, logFile=None, level=None,remove = False):
        if logFile is None:
            logFile = logName.split(os.path.sep)[-1].split('.')[0] + '.log'

        self.logger = logging.getLogger(logName)
        if level is None:
            self.logger.setLevel(logging.INFO)
        elif level == 'debug':
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        # create a file handler
        if logDir is None:
            # logDir = os.environ['HOMEPATH']
            logDir = "G:\csim\LOG"
        self.log_dir = os.path.join(logDir, 'logs')
        
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        if os.path.exists(os.path.join(self.log_dir, logFile)):
            if remove:
                os.remove(os.path.join(self.log_dir, logFile))
        file_handler = logging.handlers.RotatingFileHandler(os.path.join(self.log_dir, logFile),
                                                            maxBytes=10*1024*1024, backupCount=2,
                                                            encoding='utf-8')
        file_handler.setLevel(self.logger.level)

        # create a logging format

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(lineno)d - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        # create a console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.logger.level)
        console_handler.setFormatter(formatter)

        # add the handlers to the logger

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)