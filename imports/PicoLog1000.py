import time
import logging

import tango

class PicoLog1000:
    class Channel:
        def __init__(self, device, channel_name):
            self.dev = device
            if type(channel_name) is int:
                self.name = 'chany%02i' % channel_name
            else:
                self.name = str(channel_name)
            self.prop = None
            self.index = None

        def read_properties(self):
            # Read signal properties
            ap = self.dev.tango_db.get_device_attribute_property(self.dev.name, self.name)
            self.prop = ap[self.name]
            return self.prop

        def read_data(self):
            self.attr = self.dev.devProxy.read_attribute(self.name)
            return self.attr.value

        def read_x_data(self):
            if not self.name.startswith('chany'):
                if self.attr is None:
                    self.read_data()
                # Generate 1 increment array as x
                self.x_data = numpy.arange(len(self.attr.value))
            else:
                self.x_data = self.dev.devProxy.read_attribute(self.name.replace('y', 'x')).value
            return self.x_data

        def get_prop_as_boolean(self, propName):
            propVal = None
            try:
                propString = self.get_prop(propName).lower()
                if propString == "true":
                    propVal = True
                elif propString == "on":
                    propVal = True
                elif propString == "1":
                    propVal = True
                elif propString == "y":
                    propVal = True
                elif propString == "yes":
                    propVal = True
                else:
                    propVal = False
                return propVal
            except:
                return propVal

        def get_prop_as_int(self, propName):
            try:
                return int(self.get_prop(propName))
            except:
                return None

        def get_prop_as_float(self, propName):
            try:
                return float(self.get_prop(propName))
            except:
                return None

        def get_prop(self, propName):
            try:
                if self.prop is None:
                    self.read_properties()
                ps = self.prop[propName][0]
                return ps
            except:
                return None

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
                        n2 = int((pv +  pl - self.x_data[0]) / dx)
                        ml[pn] = self.attr.value[n1:n2].mean()
                    except:
                        ml[pn] = 0.0
            return ml

    def __init__(self, tango_device_name, avg=100, folder="PicoLog1000"):
        self.name = tango_device_name
        self.avg = avg
        self.folder = folder
        self.logger = logging.getLogger()
        self.active = False
        self.tango_device = None
        self.tango_db = None
        self.channels = []

    def get_name(self):
        return self.name

    def activate(self):
        if not self.active:
            try:
                self.tango_db = tango.Database()
                self.tango_device = tango.DeviceProxy(self.get_name())
                self.active = True
                self.logger.debug("PicoLog1000 %s has been activated", self.get_name())
            except:
                self.active = False
                self.logger.warning("PicoLoOg1000 %s activation error", self.get_name())
        return self.active

    def __str__(self):
        return self.get_name()

    def new_shot(self):
        return False

    def save(self, log_file, zip_file):
        if not self.active:
            self.logger.debug('Reading inactive device')
            return
        ready = self.tango_device.read_attribute("data_ready")
        if not ready:
            self.logger.debug('Data not ready')
            return
        channels_str = self.tango_device.read_attribute("channels")
        self.channels = []
        try:
            self.channels = eval(channels_str)
        except:
            pass
        if len(self.channels) <= 0:
            self.logger.debug('No data channels')
            return
        trigger = self.tango_device.read_attribute("trigger")
        raw_data = self.tango_device.read_attribute("raw_data")
        for c in self.channels:
            try:
                index = self.channels.index(c)
                y_name = 'chany%02i' % c

                chan = PicoLog1000.Channel(self, c)
                # Read save_data and save_log flags
                sdf = chan.get_prop_as_boolean("save_data")
                slf = chan.get_prop_as_boolean("save_log")
                # Save signal properties
                if sdf or slf:
                    self.save_prop(zip_file, chan)
                    chan.read_data()
                    self.save_log(log_file, chan)
                    if sdf:
                        self.save_data(zip_file, chan)
                break
            except:
                LOGGER.log(logging.WARNING, "Adlink %s data save exception" % self.get_name())
                print_exception_info()
                retry_count -= 1
            if retry_count > 0:
                LOGGER.log(logging.DEBUG, "Retry reading channel %s" % self.get_name())
            if retry_count == 0:
                LOGGER.log(logging.WARNING, "Error reading channel %s" % self.get_name())

    def read_shot(self):
        try:
            da = self.tango_device.read_attribute("Shot_id")
            shot = da.value
            return shot
        except:
            return -1

    def read_shot_time(self):
        try:
            elapsed = self.tango_device.read_attribute('Elapsed')
            self.shot_time = time.time()
            if elapsed.quality != tango._tango.AttrQuality.ATTR_VALID:
                LOGGER.info('Non Valid attribute %s %s' % (elapsed.name, elapsed.quality))
                return -self.shot_time
            self.shot_time = self.shot_time - elapsed.value
            return self.shot_time
        except:
            return -self.shot_time

    def save_data(self, zip_file, chan):
        entry = chan.dev.folder + "/" + chan.name + ".txt"
        avg = chan.get_prop_as_int("save_avg")
        if avg < 1:
            avg = 1
        if chan.x_data is None or len(chan.x_data) != len(chan.attr.value):
            chan.x_data = chan.read_x_data()
        buf = convert_to_buf(chan.x_data, chan.attr.value, avg)
        zip_file.writestr(entry, buf)

    def save_prop(self, zip_file, chan):
        entry = chan.dev.folder + "/" + "param" + chan.name + ".txt"
        buf = "Signal_Name=%s/%s\r\n" % (chan.dev.get_name(), chan.name)
        buf += "Shot=%d\r\n" % chan.dev.shot
        prop_list = ['%s=%s'%(k, chan.prop[k][0]) for k in chan.prop]
        for prop in prop_list:
            buf += "%s\r\n" % prop
        zip_file.writestr(entry, buf)

    def save_log(self, log_file, chan):
        # Signal label = default mark name
        label = chan.get_prop('label')
        if label is None or '' == label:
            label = chan.get_prop('name')
        if label is None or '' == label:
            label = chan.name
        # Units
        unit = chan.get_prop('unit')
        # Calibration coefficient for conversion to units
        coeff = chan.get_prop_as_float("display_unit")
        if coeff is None or coeff == 0.0:
            coeff = 1.0

        marks = chan.get_marks()

        # Find zero value
        zero = 0.0
        if "zero" in marks:
            zero = marks["zero"]
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
                    print("%10s " % chan.name, end='')
                    first_line = False
                else:
                    print("%10s " % "  ", end='')
                pmn = mark_name
                if len(mark_name) > 14:
                    pmn = mark_name[:5] + '...' + mark_name[-6:]
                if abs(mark_value) >= 1000.0:
                    print("%14s = %7.0f %s\r\n" % (pmn, mark_value, unit), end='')
                elif abs(mark_value) >= 100.0:
                    print("%14s = %7.1f %s\r\n" % (pmn, mark_value, unit), end='')
                elif abs(mark_value) >= 10.0:
                    print("%14s = %7.2f %s\r\n" % (pmn, mark_value, unit), end='')
                else:
                    print("%14s = %7.3f %s\r\n" % (pmn, mark_value, unit), end='')

                format = chan.get_prop('format')
                if format is None or '' == format:
                    format = '%6.2f'
                outstr = "; %s = "%mark_name + format%mark_value + " %s"%unit
                log_file.write(outstr)
        outstr = "; SHOT_TIME = %f" % self.read_shot_time()
        log_file.write(outstr)
