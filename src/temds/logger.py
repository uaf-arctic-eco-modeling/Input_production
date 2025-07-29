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

MsgType = Enum('MsgType', [('none', 0), ('info', 1), ('warn', 2), ('error', 3)])

@dataclass
class LogMsg:
    text: str
    msg_type: MsgType
    time: datetime = field(default_factory=datetime.now)


class MalformedLogMsgError(Exception):
    pass

class Logger(UserList):
    def __init__(self, data: list = [], verbose_level = MsgType.none):
        self.data = data
        self.verbose_level = verbose_level


    def write(self, path: Path, mode: str = 'w', clear: bool = True):

        with path.open(mode) as fd:
            for item in self:
                fd.write(f'{item.msg_type.name.upper()} [{item.time}]: {item.text}\n')

        if clear:
            self.data = []

    def append(self, item):
        if not isinstance(item, LogMsg):
            raise MalformedLogMsgError('Only LogMsg Items may be appended')
        else:
            if item.msg_type.value <= self.verbose_level.value:
                print(f'{item.msg_type.name.upper()} [{item.time}]: {item.text}')
            super().append(item)

    def log(self, text, msg_type=MsgType.info):
        self.append(LogMsg(text, msg_type))

    def info(self, text):
        self.log(text, MsgType.info)

    def warn(self, text):
        self.log(text, MsgType.warn)
    
    def error(self, text):
        self.log(text, MsgType.error)

