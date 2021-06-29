import logging

import numpy
import tango


class DumperDevice:
    class Channel:
        def __init__(self, device: tango.DeviceProxy, channel, prefix='channel_', format='%03i'):
            self.device = device
            if type(channel) is int:
                self.name = prefix + (format % channel)
            else:
                self.name = str(channel)
            self.y = None
            self.y_attr = None
            self.x = None
            self.x_attr = None

        def read_y(self):
            self.y_attr = self.device.read_attribute(self.name)
            self.y = self.y_attr.value
            return self.y

        def read_x(self):
            if self.y is None:
                length = 1
            else:
                length = len(self.y)
            x_name = self.name.replace('y', 'x')
            if x_name == self.name:
                self.x = numpy.linspace(0, length, length, dtype=numpy.float32)
                return self.x
            try:
                self.x_attr = self.device.read_attribute(x_name)
                self.x = self.x_attr.value
                return self.x
            except:
                self.x = numpy.linspace(0, length, length, dtype=numpy.float32)
                return self.x

        def properties(self):
            try:
                db = self.device.get_device_db()
                return db.get_device_attribute_property(self.device.name(), self.name)[self.name]
            except:
                return {}

        def property(self, name):
            return self.properties().get(name, [''])

        def get_marks(self):
            properties = self.properties()
            marks = {}
            for p_key in properties:
                if p_key.endswith("_start"):
                    try:
                        pv = float(properties[p_key][0])
                        pln = p_key.replace("_start", "_length")
                        pl = float(properties[pln][0])
                        index = numpy.logical_and(self.x >= pv, self.x <= (pv + pl))
                        mark_name = p_key.replace("_start", "")
                        marks[mark_name] = self.y[index].mean()
                    except:
                        pass
            return marks

    def __init__(self, tango_device_name: str, folder=''):
        self.logger = self.config_logger(name=__qualname__, level=logging.DEBUG)
        self.name = tango_device_name
        self.folder = folder
        self.active = False
        self.tango_device = None
        self.activate()

    def new_shot(self):
        return False

    def activate(self):
        if not self.active:
            try:
                self.tango_device = tango.DeviceProxy(self.name)
                self.active = True
                self.logger.debug("%s has been activated", self.name)
            except:
                self.tango_device = None
                self.active = False
                self.logger.warning("%s activation error", self.name)
        return self.active

    def save(self, log_file, zip_file):
        raise NotImplemented()
        # if not self.active:
        #     self.logger.debug('Reading inactive device')
        #     return

    def property(self, prop_name):
        try:
            return self.tango_device.get_property(prop_name)[prop_name][0]
        except:
            return ''

    def property_list(self, filter='*'):
        return self.tango_device.get_property_list(filter)

    @staticmethod
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

    TRUE_VALUES = ('true', 'on', '1', 'y', 'yes')
    FALSE_VALUES = ('false', 'off', '0', 'n', 'no')

    @staticmethod
    def as_boolean(value):
        if value.lower() in DumperDevice.TRUE_VALUES:
            return True
        if value.lower() in DumperDevice.FALSE_VALUES:
            return False
        return None

    @staticmethod
    def as_int(value):
        try:
            return int(value)
        except:
            return None
