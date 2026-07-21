class Actor:
    def __init__(self, name="", role="", order=-1, thumbnail=""):
        self.name, self.role, self.order, self.thumbnail = name, role, order, thumbnail


def log(msg, level=0):
    pass


LOGDEBUG = 0
LOGINFO = 1
LOGWARNING = 2
LOGERROR = 3
