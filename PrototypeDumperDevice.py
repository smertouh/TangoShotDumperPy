import sys
import time
import logging
import zipfile
from typing import IO

import numpy
import tango

from TangoUtils import config_logger, log_exception


class PrototypeDumperDevice:
    class Channel:
        def __init__(self, device: tango.DeviceProxy, channel, prefix='chany', format='%03i'):
            self.logger = config_logger()
            self.device = device
            if isinstance(int, channel):
                self.name = prefix + (format % channel)
            else:
                self.name = str(channel)
            self.file_name = self.name
            self.y = None
            self.y_attr = None
            self.x = None
            self.x_attr = None
            self.properties = None

        def read_y(self):
            self.y_attr = self.device.read_attribute(self.name)
            self.y = self.y_attr.value
            return self.y

        def read_x(self, x_name: str = None):
            if x_name is None:
                x_name = self.name.replace('y', 'x')
            if x_name == self.name:
                self.x_attr = None
                self.x = None
                return self.x
            try:
                self.x_attr = self.device.read_attribute(x_name)
                self.x = self.x_attr.value
                return self.x
            except:
                self.x_attr = None
                self.x = None
                return self.x

        def read_properties(self, force=False):
            # returns dictionary with attribute properties for channel attribute
            if self.properties is not None and not force:
                return self.properties
            try:
                db = self.device.get_device_db()
                self.properties = db.get_device_attribute_property(self.device.name(), self.name)[self.name]
            except:
                self.properties = {}
            return self.properties

        def property(self, property_name: str):
            self.read_properties()
            result = self.properties.get(property_name, [''])
            if len(result) == 1:
                result = result[0]
            return result

        def marks(self):
            properties = self.read_properties()
            result = {}
            for p_key in properties:
                if p_key.endswith("_start"):
                    try:
                        pv = float(properties[p_key][0])
                        pln = p_key.replace("_start", "_length")
                        pl = float(properties[pln][0])
                        mark_name = p_key.replace("_start", "")
                        if pl > 0.0:
                            result[mark_name] = (pv, pv + pl)
                    except:
                        pass
            return result

        def mark_values(self):
            result = {}
            mrk = self.marks()
            for key in mrk:
                try:
                    range = mrk[key]
                    index = numpy.logical_and(self.x >= range[0], self.x <= range[1])
                    if numpy.any(index):
                        result[key] = self.y[index].mean()
                    else:
                        result[key] = float('nan')
                except:
                    pass
            return result

        def save_log(self, log_file: IO, additional_marks=None):
            if additional_marks is None:
                additional_marks = {}
            self.read_properties()
            # Signal label = default mark name
            label = self.properties.get('label', [''])[0]
            if '' == label:
                label = self.properties.get('name', [''])[0]
            if '' == label:
                label = self.file_name
            # Units
            unit = self.properties.get('unit', [''])[0]
            # coefficient for conversion to units
            try:
                coeff = float(self.properties.get('display_unit', ['1.0'])[0])
            except:
                coeff = 1.0
            # output data format
            format = self.properties.get('format', ['%6.2f'])[0]
            # process marks
            marks = self.mark_values()
            # Find zero value
            zero = marks.get('zero', 0.0)
            # add additional marks
            for mark in additional_marks:
                marks[mark] = additional_marks[mark]
            # Convert all marks to mark_value = (mark - zero)*coeff
            scaled_marks = {}
            for mark in marks:
                # If it is not zero mark
                if not "zero" == mark:
                    mark_name = mark
                    # Default mark renamed to label
                    if mark_name == "mark":
                        mark_name = label
                    scaled_marks[mark_name] = (marks[mark] - zero) * coeff
            # print and save scaled_marks to log file
            np = 0
            for mark in scaled_marks:
                print("    ", end='')
                # printed mark name
                pmn = mark
                mark_value = scaled_marks[mark]
                # if len(mark) > 14:
                #     pmn = mark[:5] + '...' + mark[-6:]
                # print mark value
                if abs(mark_value) >= 1000.0:
                    print("%14s = %7.0f %s\r\n" % (pmn, mark_value, unit), end='')
                elif abs(mark_value) >= 100.0:
                    print("%14s = %7.1f %s\r\n" % (pmn, mark_value, unit), end='')
                elif abs(mark_value) >= 10.0:
                    print("%14s = %7.2f %s\r\n" % (pmn, mark_value, unit), end='')
                else:
                    print("%14s = %7.3f %s\r\n" % (pmn, mark_value, unit), end='')
                out_str = ("; %s = " % mark) + (format % mark_value)
                if unit != '':
                    out_str += (" %s" % unit)
                log_file.write(out_str)
                np += 1
            if np == 0:
                print('    ', label, '---- no marks')
            self.logger.debug('%s Log Saved', self.file_name)

        def save_properties(self, zip_file: zipfile.ZipFile, folder: str = ''):
            if not folder.endswith('/'):
                folder += '/'
            zip_entry = folder + "param" + self.file_name + ".txt"
            buf = "Signal_Name=%s/%s\r\n" % (self.device.name(), self.name)
            properties = self.read_properties()
            for prop in properties:
                buf += '%s=%s\r\n' % (prop, properties[prop][0])
            zip_file.writestr(zip_entry, buf)
            self.logger.debug('%s Properties saved to %s', self.file_name, zip_entry)

        def save_data(self, zip_file: zipfile.ZipFile, folder: str = ''):
            if self.y is None:
                self.logger.debug('%s No data to save', self.file_name)
                return
            if not folder.endswith('/'):
                folder += '/'
            zip_entry = folder + self.file_name + ".txt"
            avg = int(self.read_properties().get("save_avg", ['1'])[0])
            outbuf = ''
            if self.x is None:
                # save only y values
                fmt = '%f'
                fmtcrlf = fmt + '\r\n'
                try:
                    n = len(self.y)
                    ys = 0.0
                    ns = 0.0
                    for k in range(n - 1):
                        ys += self.y[k]
                        ns += 1.0
                        if ns >= avg:
                            s = fmtcrlf % (ys / ns)
                            outbuf += s.replace(",", ".")
                            ys = 0.0
                            ns = 0.0
                    ys += self.y[n - 1]
                    ns += 1.0
                    s = fmt % (ys / ns)
                    outbuf += s.replace(",", ".")
                except:
                    s = fmt % self.y
                    outbuf += s.replace(",", ".")
            else:
                # save "x; y" pairs
                fmt = '%f; %f'
                fmtcrlf = fmt + '\r\n'
                n = min(len(self.x), len(self.x))
                xs = 0.0
                ys = 0.0
                ns = 0.0
                for k in range(n - 1):
                    xs += self.x[k]
                    ys += self.y[k]
                    ns += 1.0
                    if ns >= avg:
                        s = fmtcrlf % (xs / ns, ys / ns)
                        outbuf += s.replace(",", ".")
                        xs = 0.0
                        ys = 0.0
                        ns = 0.0
                xs += self.x[n - 1]
                ys += self.y[n - 1]
                ns += 1.0
                s = fmt % (xs / ns, ys / ns)
                outbuf += s.replace(",", ".")
            zip_file.writestr(zip_entry, outbuf)
            self.logger.debug('%s Data saved to %s', self.file_name, zip_entry)

    def __init__(self, device_name: str, reactivate_if_not_defined: bool = True):
        self.logger = config_logger()
        self.name = device_name
        self.active = False
        self.device = None
        self.time = 0.0
        self.activation_timeout = 10.0
        self.defined_in_db = True
        self.reactivate_if_not_defined = reactivate_if_not_defined
        self.activate()

    def new_shot(self):
        return False

    def activate(self):
        if not self.active:
            if self.device is None and (time.time() - self.time) < self.activation_timeout:
                return False
            self.time = time.time()
            if self.defined_in_db:
                try:
                    self.device = tango.DeviceProxy(self.name)
                    self.active = True
                    self.logger.debug("%s has been activated", self.name)
                    return True
                except:
                    self.device = None
                    self.active = False
                    ex_type, ex_value, traceback = sys.exc_info()
                    if ex_value.args[0].reason == 'DB_DeviceNotDefined':
                        self.logger.error('Device %s is not defined in DB', self.name)
                        if not self.reactivate_if_not_defined:
                            self.defined_in_db = False
                            self.logger.error('Dumper restart required to activate device %s', self.name)
                    else:
                        log_exception("%s activation error: ", self.name)
            return False
        return self.active

    def save(self, log_file: IO, zip_file: zipfile.ZipFile, folder: str = None):
        raise NotImplemented()
        # if not self.active:
        #     self.logger.debug('Reading inactive device')
        #     return

    def property(self, prop_name: str):
        try:
            result = self.device.get_property(prop_name)[prop_name]
            if len(result) == 1:
                result = result[0]
            return result
            # return self.device.get_property(prop_name)[prop_name][0]
        except:
            return ''

    def properties(self, filter: str = '*'):
        # returns dictionary with device properties
        names = self.device.get_property_list(filter)
        return self.device.get_property(names)

    TRUE_VALUES = ('true', 'on', '1', 'y', 'yes')
    FALSE_VALUES = ('false', 'off', '0', 'n', 'no')

    @staticmethod
    def as_boolean(value):
        value = str(value)
        if value.lower() in PrototypeDumperDevice.TRUE_VALUES:
            return True
        if value.lower() in PrototypeDumperDevice.FALSE_VALUES:
            return False
        return None

    @staticmethod
    def as_int(value):
        if isinstance(int, value):
            return value
        try:
            return int(str(value))
        except:
            return None
