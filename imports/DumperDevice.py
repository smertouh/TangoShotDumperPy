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
                self.x = None
                return self.x
            try:
                self.x_attr = self.device.read_attribute(x_name)
                self.x = self.x_attr.value
                return self.x
            except:
                self.x = None
                return self.x

        def properties(self):
            # returns dictionary with attribute properties for channel attribute
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

        def save_log(self, log_file):
            properties = self.properties()
            # Signal label = default mark name
            label = properties.get('label', [''])[0]
            if '' == label:
                label = properties.get('name', [''])[0]
            if '' == label:
                label = self.name
            # Units
            unit = properties.get('unit', [''])[0]
            # coefficient for conversion to units
            coeff = float(properties.get('display_unit', ['1.0'])[0])
            # process marks
            marks = self.get_marks()
            # Find zero value
            zero = marks.get('zero', 0.0)
            # Convert all marks to mark_value = (mark - zero)*coeff
            for mark in marks:
                first_line = True
                # If it is not zero mark
                if not "zero" == mark:
                    mark_value = (marks[mark] - zero) * coeff
                    mark_name = mark
                    # Default mark renamed to label
                    if mark_name == "mark":
                        mark_name = label
                    # Print mark name = value
                    if first_line:
                        print("%10s " % self.name, end='')
                        first_line = False
                    else:
                        print("%10s " % "  ", end='')
                    # printed mark name
                    pmn = mark_name
                    if len(mark_name) > 14:
                        pmn = mark_name[:5] + '...' + mark_name[-6:]
                    # print mark vavue
                    if abs(mark_value) >= 1000.0:
                        print("%14s = %7.0f %s\r\n" % (pmn, mark_value, unit), end='')
                    elif abs(mark_value) >= 100.0:
                        print("%14s = %7.1f %s\r\n" % (pmn, mark_value, unit), end='')
                    elif abs(mark_value) >= 10.0:
                        print("%14s = %7.2f %s\r\n" % (pmn, mark_value, unit), end='')
                    else:
                        print("%14s = %7.3f %s\r\n" % (pmn, mark_value, unit), end='')
                    # output data format
                    format = properties.get('format', ['%6.2f'])[0]
                    out_str = "; %s = " % mark_name + format % mark_value + " %s" % unit
                    log_file.write(out_str)

        def save_properties(self, zip_file, folder, device_name):
            zip_entry = folder + "properties_" + self.name + ".txt"
            buf = "Signal_Name=%s/%s\r\n" % (device_name, self.name)
            properties = self.properties()
            for prop in properties:
                buf += '%s=%s\r\n' % (prop, properties[prop][0])
            zip_file.writestr(zip_entry, buf)

        def save_data(self, zip_file, folder):
            zip_entry = folder +  self.name + ".txt"
            avg = int(self.properties().get("save_avg", ['1'])[0])
            outbuf = ''
            if self.x is None:
                # save only y values
                fmt = '%f'
                fmtcrlf = fmt + '\r\n'
                n = len(self.y)
                ys = 0.0
                ns = 0.0
                for k in range(n):
                    ys += self.y[k]
                    ns += 1.0
                    if ns >= avg:
                        s = fmtcrlf % (ys / ns)
                        outbuf += s.replace(",", ".")
                        ys = 0.0
                        ns = 0.0
                if ns > 0:
                    s = fmt % (ys / ns)
                    outbuf += s.replace(",", ".")
            else:
                # save "x; y" pairs
                fmt = '%f; %f'
                fmtcrlf = fmt + '\r\n'
                n = min(len(self.x), len(self.x))
                xs = 0.0
                ys = 0.0
                ns = 0.0
                for k in range(n):
                    xs += self.x[k]
                    ys += self.y[k]
                    ns += 1.0
                    if ns >= avg:
                        s = fmtcrlf % (xs / ns, ys / ns)
                        outbuf += s.replace(",", ".")
                        xs = 0.0
                        ys = 0.0
                        ns = 0.0
                if ns > 0:
                    s = fmt % (xs / ns, ys / ns)
                    outbuf += s.replace(",", ".")
            zip_file.writestr(zip_entry, outbuf)

    def __init__(self, tango_device_name: str, folder='./'):
        self.logger = self.config_logger(name=__qualname__, level=logging.DEBUG)
        self.name = tango_device_name
        if not folder.endswith('/'):
            folder += '/'
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
