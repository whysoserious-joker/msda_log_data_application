
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler



def daily_logger(logPath):
    p = Path(logPath)
    logDir = p.parent  
    Path(logDir).mkdir(exist_ok=True,parents=True)
    logFile = p.name
    logPath = os.path.join(logDir,logFile)
    handler = TimedRotatingFileHandler(logPath, when="midnight", backupCount=365*10)
    handler.suffix = "%Y%m%d"
    data_log = logging.getLogger('dl')
    data_log.setLevel(logging.INFO)
    data_log.addHandler(handler)
    return data_log
def filesize_logger(logPath):
    p = Path(logPath)
    logDir = p.parent  
    Path(logDir).mkdir(exist_ok=True,parents=True)
    logFile = p.name
    logPath = os.path.join(logDir,logFile)
    my_handler = RotatingFileHandler(logPath, mode='a', maxBytes=5*1024*1024, 
                                    backupCount=10, encoding=None, delay=0)
    log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
    my_handler.setFormatter(log_formatter)
    my_handler.setLevel(logging.INFO)
    app_log = logging.getLogger('fs')
    app_log.setLevel(logging.INFO)
    app_log.addHandler(my_handler)
    return app_log