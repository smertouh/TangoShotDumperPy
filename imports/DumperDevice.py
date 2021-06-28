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
    class Channel:
        def __init__(self, device, channel, prefix='chan'):
            self.dev = device
            if type(channel) is int:
                self.y_name = prefix + ('%02i' % channel)
            else:
                self.y_name = str(channel)
            self.attr_proxy = tango.AttributeProxy(device.name + '/' + self.y_name)
            self.y = None
            self.x_name = self.y_name.replace('y', 'x')
            self.index = None

        def read_y(self):
            self.y = self.attr_proxy.read()
            return self.y.value

        def read_x(self):
            if not self.name.startswith('chany'):
                if self.attr is None:
                    self.read_data()
                # Generate 1 increment array as x
                self.x_data = numpy.arange(len(self.attr.value))
            else:
                self.x_data = self.dev.devProxy.read_attribute(self.name.replace('y', 'x')).value
            return self.x_data

        def property(self, property_name):
            try:
                return self.attr_proxy.get_propery(property_name)[property_name][0]
            except:
                return ''

        def get_marks(self):
            if self.prop is None:
                self.read_properties()
            if self.attr is None:
                self.read_data()
            if self.x_data is None:
                self.read_x_data()
            ml = {}
            for pk in self.prop:
                if pk.endswith("_start"):
                    pn = pk.replace("_start", "")
                    try:
                        pv = int(self.prop[pk][0])
                        pln = pn + "_length"
                        if pln in self.prop:
                            pl = int(self.prop[pln][0])
                        else:
                            pl = 1
                        dx = self.x_data[1] - self.x_data[0]
                        n1 = int((pv - self.x_data[0]) / dx)
                        n2 = int((pv + pl - self.x_data[0]) / dx)
                        ml[pn] = self.attr.value[n1:n2].mean()
                    except:
                        ml[pn] = 0.0
            return ml

    def __init__(self, tango_device_name: str, folder=''):
        self.logger = config_logger(name=__qualname__, level=logging.DEBUG)
        self.name = tango_device_name
        self.folder = folder
        self.active = False
        self.tango_device = None
        self.activate()

    def __str__(self):
        return self.get_name()

    def new_shot(self):
        return False

    def activate(self):
        if not self.active:
            try:
                self.tango_device = tango.DeviceProxy(self.get_name())
                self.active = True
                self.logger.debug("%s has been activated", self.get_name())
            except:
                self.tango_device = None
                self.active = False
                self.logger.warning("%s activation error", self.get_name())
        return self.active

    def save(self, log_file, zip_file):
        raise NotImplemented()
        # if not self.active:
        #     self.logger.debug('Reading inactive device')
        #     return


def get_device_property(device_proxy, prop_name):
    try:
        return device_proxy.get_property(prop_name)[prop_name][0]
    except:
        return ''


def get_device_property_list(device_proxy, fltr='*'):
    return device_proxy.get_property_list(fltr)


TRUE_VALUES = ('true', 'on', '1', 'y', 'yes')
FALSE_VALUES = ('false', 'off', '0', 'n', 'no')


def as_boolean(value):
    if value.lower() in TRUE_VALUES:
        return True
    if value.lower() in FALSE_VALUES:
        return False
    return None


def as_int(value):
    try:
        return int(value)
    except:
        return None
