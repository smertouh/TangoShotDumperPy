import logging

import tango


def config_logger(name: str = __name__, level: int = logging.DEBUG):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        logger.propagate = False
        logger.setLevel(level)
        f_str = '%(asctime)s,%(msecs)3d %(levelname)-7s %(filename)s %(funcName)s(%(lineno)s) %(message)s'
        log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        logger.addHandler(console_handler)
    return logger


class DumperDevice:
    def __init__(self, tango_device_name: str, folder=''):
        self.logger = config_logger(name=__qualname__, level=logging.DEBUG)
        self.name = tango_device_name
        self.folder = folder
        self.active = False
        self.tango_device = None
        self.tango_db = None
        self.activate()

    def get_name(self):
        return self.name

    def __str__(self):
        return self.get_name()

    def new_shot(self):
        return False

    def activate(self):
        if not self.active:
            try:
                self.tango_db = tango.Database()
                self.tango_device = tango.DeviceProxy(self.get_name())
                self.active = True
                self.logger.debug("%s has been activated", self.get_name())
            except:
                self.active = False
                self.logger.warning("%s activation error", self.get_name())
        return self.active

    def save(self, log_file, zip_file):
        raise NotImplemented()
        # if not self.active:
        #     self.logger.debug('Reading inactive device')
        #     return

