"""
Logger
------
logging class for project

"""
from dataclasses import dataclass, field
from enum import Enum
from collections import UserList
from datetime import datetime
from pathlib import Path

MsgType = Enum('MsgType', [('debug', 0 ), ('info', 1), ('warn', 2), ('error', 3)])

ERROR = [MsgType.error]
WARN  = ERROR + [MsgType.warn]
INFO  = WARN  + [MsgType.info]
DEBUG = INFO  + [MsgType.debug] 




@dataclass
class LogMsg:
    text: str
    msg_type: MsgType
    time: datetime = field(default_factory=datetime.now)


class MalformedLogMsgError(Exception):
    pass

class Logger(UserList):
    def __init__(self, data: list = None, verbose_levels = [], write_to=None):
        if data is None:
            self.data = []
        else:
            self.data = data
        self.verbose_levels = verbose_levels
        self._suspended_levels = []
        self.write_to = Path(write_to) if write_to else None

    def __del__(self):
        if self.write_to:
            self.write(self.write_to)

    def suspend(self):
        self._suspended_levels = self.verbose_levels
        self.verbose_levels = []

    def resume(self):
        self.verbose_levels = self._suspended_levels
        self._suspended_levels = [] 

    def clear(self):
        self.data = []

    def write(self, path: Path, mode: str = 'w', clear: bool = True):
        print(mode)
        with path.open(mode=mode) as fd:
            for item in self:
                fd.write(f'{item.msg_type.name.upper():>7} [{item.time.strftime("%Y-%m-%d %H:%M:%S")}]: {item.text}\n')

        if clear: self.clear()

    def append(self, item):
        if not isinstance(item, LogMsg):
            raise MalformedLogMsgError('Only LogMsg Items may be appended')
        
        if item.msg_type in self.verbose_levels:
            print(f'{item.msg_type.name.upper():>5} [{item.time.strftime("%Y-%m-%d %H:%M:%S")}]: {item.text}')
        self.data.append(item)

    def log(self, text, msg_type=MsgType.info):
        self.append(LogMsg(text, msg_type))

    def debug(self, text):
        self.log(text, MsgType.debug)

    def info(self, text):
        self.log(text, MsgType.info)

    def warn(self, text):
        self.log(text, MsgType.warn)
    
    def error(self, text):
        self.log(text, MsgType.error)
