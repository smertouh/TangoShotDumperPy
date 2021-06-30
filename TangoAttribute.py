from DumperItem import *


class TangoAttribute(DumperItem):
    def __init__(self, device_name, attribute_name, folder=None, force=True, ahead=None):
        super().__init__(device_name)
        self.attribute_name = attribute_name
        self.folder = folder
        self.force = force
        self.ahead = ahead
        self.retry_count = 3

    def activate(self):
        super().activate()
        return self.active

    def get_property(self, prop):
        try:
            if self.prop is None:
                self.read_all_properties()
            ps = self.prop[prop][0]
            return ps
        except:
            return None

    def get_prop_as_boolean(self, prop):
        val = None
        try:
            prop_str = self.get_property(prop).lower()
            if prop_str == "true":
                val = True
            elif prop_str == "on":
                val = True
            elif prop_str == "1":
                val = True
            elif prop_str == "y":
                val = True
            elif prop_str == "yes":
                val = True
            else:
                val = False
            return val
        except:
            return None

    def get_prop_as_int(self, prop):
        try:
            return int(self.get_property(prop))
        except:
            return None

    def get_prop_as_float(self, prop):
        try:
            return float(self.get_property(prop))
        except:
            return None

    def read_all_properties(self):
        # read all properties
        ap = self.db.get_device_attribute_property(self.dev, self.name)
        self.prop = ap[self.name]
        return self.prop

    def read_attribute(self):
        self.attr = self.devProxy.read_attribute(self.name)
        self.time = time.time()
        try:
            if self.ahead is not None and self.devProxy.is_attribute_polled(self.name):
                period = self.devProxy.get_attribute_poll_period(self.name)
                n = self.ahead / period + 1
                history = self.devProxy.attribute_history(self.name, n)
                t = history[0].time.tv_sec + (1.0e-6 * history[0].time.tv_usec) + (1.0e-9 * history[0].time.tv_nsec)
                if time.time() - t >= (self.ahead - 0.1):
                    self.attr = history[0]
                    LOGGER.debug('Read from ahead buffer successful')
                else:
                    LOGGER.debug('Can not read from ahead buffer')
        except:
            LOGGER.debug('Exception in read_attribute', exc_info=True)

    def get_name(self):
        return "%s/%s" % (self.dev, self.name)

    def __str__(self):
        return self.get_name()

    def activate(self):
        if self.active:
            return True
        try:
            self.db = tango.Database()
            self.devProxy = tango.DeviceProxy(self.dev)
            self.time = time.time()
            self.active = True
            LOGGER.log(logging.DEBUG, "Device %s activated" % self.dev)
        except:
            self.active = False
            self.time = time.time()
            LOGGER.log(logging.ERROR, "Device %s activation error" % self.dev)
            print_exception_info()
        return self.active

    def new_shot(self):
        return False

    def convert_to_buf(self, avgc, y=None, x=None):
        outbuf = ''
        if avgc < 1:
            avgc = 1

        if x is None:
            # save only y values
            fmt = '%f'
            if y is None:
                y = self.attr.value
            n = len(y)
            ys = 0.0
            ns = 0.0
            for k in range(n):
                ys += y[k]
                ns += 1.0
                if ns >= avgc:
                    if k >= avgc:
                        outbuf += '\r\n'
                    s = fmt % (ys / ns)
                    outbuf += s.replace(",", ".")
                    ys = 0.0
                    ns = 0.0
            if ns > 0:
                outbuf += '\r\n'
                s = fmt % (ys / ns)
                outbuf += s.replace(",", ".")
        else:
            # save "x; y" pairs
            fmt = '%f; %f'
            if y is None:
                y = self.attr.value
            if y is None:
                return ''
            if len(y) <= 0 or len(x) <= 0:
                return ''
            n = len(y)
            if len(x) < n:
                n = len(x)
                LOGGER.log(logging.WARNING, "X and Y arrays of different length, truncated to %d" % n)
            xs = 0.0
            ys = 0.0
            ns = 0.0
            for k in range(n):
                xs += x[k]
                ys += y[k]
                ns += 1.0
                if ns >= avgc:
                    if k >= avgc:
                        outbuf += '\r\n'
                    s = fmt % (xs / ns, ys / ns)
                    outbuf += s.replace(",", ".")
                    xs = 0.0
                    ys = 0.0
                    ns = 0.0
            if ns > 0:
                outbuf += '\r\n'
                s = fmt % (xs / ns, ys / ns)
                outbuf += s.replace(",", ".")
        return outbuf

    def get_marks(self):
        if self.prop is None:
            self.read_all_properties()
        if self.attr is None:
            self.read_attribute()
        ml = {}
        for pk in self.prop:
            if pk.endswith("_start"):
                pn = pk.replace("_start", "")
                try:
                    pv = int(self.prop[pk][0])
                    pln = pk.replace("_start", "_length")
                    if pln in self.prop:
                        pl = int(self.prop[pln][0])
                    else:
                        pl = 1
                    ml[pn] = self.attr.value[pv:pv + pl].mean()
                except:
                    ml[pn] = 0.0
        return ml

    def save_log(self, log_file):
        try:
            if self.attr.data_format == tango._tango.AttrDataFormat.SCALAR:
                v = self.attr.value
                if isinstance(v, (int, float, complex)) and not isinstance(v, bool):
                    v = self.fmt % (v * self.coeff)
                else:
                    v = str(v)
                outstr = ('; %s = ' + v + ' %s') % (self.label, self.unit)
                log_file.write(outstr)
                print(outstr[1:])
            elif self.attr.data_format == tango._tango.AttrDataFormat.SPECTRUM:
                self.marks = self.get_marks()
                # find zero value
                zero = 0.0
                if "zero" in self.marks:
                    zero = self.marks["zero"]
                # convert all marks to mark_value = (mark - zero)*coeff
                for mark in self.marks:
                    first_line = True
                    # if it is not zero mark
                    if not "zero" == mark:
                        mark_value = (self.marks[mark] - zero) * self.coeff
                        mark_name = mark
                        # default mark renamed to label
                        if mark_name == "mark":
                            mark_name = self.label
                        # print mark name = value
                        if first_line:
                            print("%10s " % self.name, end='')
                            first_line = False
                        else:
                            print("%10s " % "  ", end='')
                        pmn = mark_name
                        if len(mark_name) > 14:
                            pmn = mark_name[:5] + '...' + mark_name[-6:]
                        if abs(mark_value) >= 1000.0:
                            print("%14s = %7.0f %s\r\n" % (pmn, mark_value, self.unit), end='')
                        elif abs(mark_value) >= 100.0:
                            print("%14s = %7.1f %s\r\n" % (pmn, mark_value, self.unit), end='')
                        elif abs(mark_value) >= 10.0:
                            print("%14s = %7.2f %s\r\n" % (pmn, mark_value, self.unit), end='')
                        else:
                            print("%14s = %7.3f %s\r\n" % (pmn, mark_value, self.unit), end='')

                        outstr = ('; %s = ' + self.fmt + ' %s') % (mark_name, mark_value * self.coeff, self.unit)
                        log_file.write(outstr)
                if len(self.marks) <= 0:
                    v = (float(self.attr.value[0]) - zero) * self.coeff
                    outstr = ('; %s = ' + self.fmt + ' %s') % (self.label, v, self.unit)
                    log_file.write(outstr)
            else:
                return
        except:
            LOGGER.log(logging.WARNING, "Log save error for %s" % self.get_name())

    def save_data(self, zip_file:zipfile.ZipFile):
        entry = self.folder + "/" + self.label + ".txt"
        try:
            if self.attr.data_format == tango._tango.AttrDataFormat.SCALAR:
                buf = str(self.attr.value)
            elif self.attr.data_format == tango._tango.AttrDataFormat.SPECTRUM:
                avg = self.get_prop_as_int("save_avg")
                if avg < 1:
                    avg = 1
                buf = self.convert_to_buf(avg)
            else:
                LOGGER.log(logging.WARNING, "Unsupported attribute format for %s" % self.get_name())
                return
            try:
                info = zip_file.getinfo(entry)
                self.folder += ("_" + self.dev + '_' + str(time.time()))
                self.folder = self.folder.replace('/', '_')
                self.folder = self.folder.replace('.', '_')
                LOGGER.log(logging.WARNING, "Duplicate entry %s in zip file. Folder is changed to %s" % (entry, self.folder))
                entry = self.folder + "/" + self.label + ".txt"
            except:
                pass
            zip_file.writestr(entry, buf)
        except:
            LOGGER.log(logging.WARNING, "Attribute y save error for %s" % self.get_name())

    def save_prop(self, zip_file):
        entry = self.folder + "/" + "param" + self.label + ".txt"
        buf = "attribute=%s\r\n" % self.get_name()
        for pr in self.prop:
            buf += '%s=%s\r\n' % (pr, self.prop[pr][0])
        try:
            info = zip_file.getinfo(entry)
            self.folder += ("_" + self.dev + '_' + str(time.time()))
            self.folder = self.folder.replace('/', '_')
            self.folder = self.folder.replace('.', '_')
            LOGGER.log(logging.WARNING,
                       "Duplicate entry %s in zip file. Folder is changed to %s." % (entry, self.folder))
            entry = self.folder + "/" + "param" + self.label + ".txt"
        except:
            pass
        zip_file.writestr(entry, buf)

    def save(self, log_file, zip_file):
        self.read_all_properties()
        # label
        self.label = self.get_property('label')
        if self.label is None or '' == self.label:
            self.label = self.get_property('name')
        if self.label is None or '' == self.label:
            self.label = self.name
        # save_data and save_log flags
        self.sdf = self.get_prop_as_boolean("save_data")
        self.slf = self.get_prop_as_boolean("save_log")
        # force save if requested during attribute creation
        if self.force:
            self.sdf = True
            self.slf = True
        # do not save if both flags are False
        if not (self.sdf or self.slf):
            return
        # read attribute with retries
        rc = self.retry_count
        while rc > 0:
            try:
                self.read_attribute()
                self.time = time.time()
                break
            except:
                LOGGER.log(logging.DEBUG, "Attribute %s read exception" % self.get_name())
                print_exception_info()
                rc -= 1
        if rc == 0:
            LOGGER.log(logging.WARNING, "Retry count exceeded reading attribute %s" % self.get_name())
            self.active = False
            self.time = time.time()
            return

        if self.attr.data_format == tango._tango.AttrDataFormat.SCALAR:
            LOGGER.log(logging.DEBUG, "Scalar attribute %s" % self.name)
        elif self.attr.data_format == tango._tango.AttrDataFormat.SPECTRUM:
            LOGGER.log(logging.DEBUG, "SPECRUM attribute %s" % self.name)
        else:
            LOGGER.log(logging.WARNING, "Unsupported attribute format for %s" % self.name)
            raise ValueError

        # determine required attribute properties
        # attribute label
        self.label = self.get_property('label')
        if self.label is None or '' == self.label:
            self.label = self.get_property('name')
        if self.label is None or '' == self.label:
            self.label = self.name
        # units
        self.unit = self.get_property('unit')
        # calibration coefficient for conversion to units
        try:
            cf = self.get_property('display_unit')
            self.coeff = float(cf)
        except:
            self.coeff = 1.0
        # format string
        self.fmt = self.get_property('format')
        if self.fmt is None or '' == self.fmt:
            self.fmt = '%6.2f'

        if self.sdf or self.slf:
            self.save_prop(zip_file)
        if self.slf:
            self.save_log(log_file)
        if self.sdf:
            self.save_data(zip_file)

