import time
import logging

import tango

from imports.DumperDevice import DumperDevice


class PicoLog1000(DumperDevice):
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
                LOGGER.info('Non Valid attr_proxy %s %s' % (elapsed.name, elapsed.quality))
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
        prop_list = ['%s=%s' % (k, chan.prop[k][0]) for k in chan.prop]
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
        coeff = chan.property_as_boolean("display_unit")
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
                outstr = "; %s = " % mark_name + format % mark_value + " %s" % unit
                log_file.write(outstr)
        outstr = "; SHOT_TIME = %f" % self.read_shot_time()
        log_file.write(outstr)
