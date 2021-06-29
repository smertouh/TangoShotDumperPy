import time
from DumperDevice import *


class TangoAttribute(DumperDevice):
    def __init__(self, attribute_name, folder=None, force=True, ahead=None):
        super().__init__(attribute_name, folder)
        self.force = force
        self.ahead = ahead
        self.retry_count = 3

    def activate(self):
        if self.active:
            return True
        self.time = time.time()
        super().activate()
        return self.active
