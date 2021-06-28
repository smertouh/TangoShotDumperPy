import time
import logging

import numpy
import tango

from imports.DumperDevice import *


class PicoLog1000(DumperDevice):
    class Channel(DumperDevice.Channel):
        pass

    def __init__(self, tango_device_name: str, folder='PicoLog'):
        super().__init__(tango_device_name, folder)

    def save(self, log_file, zip_file):
        # read data ready
        data_ready = self.tango_device.read_attribute('data_teady').value
        if not data_ready:
            self.logger.warning("%s data is not ready" % self.name)
            return
        # read raw data
        raw_data = self.tango_device.read_attribute('raw_data').value
        # read other attributes
        trigger = self.tango_device.read_attribute('trigger').value
        sampling = self.tango_device.read_attribute('sampling').value
        points = self.tango_device.read_attribute('points_per_channel').value
        # read channels list
        channels = self.tango_device.read_attribute('channels').value
        channels_list = []
        try:
            channels_list = eval(channels)
        except:
            pass

        # generate times array
        t = numpy.linspace(0, (points - 1) * sampling, points, dtype=numpy.float32)
        times = numpy.empty(raw_data.shape, dtype=numpy.float32)
        for i in range(len(channels)):
            times[i, :] = t + (i * sampling / len(channels))
        if trigger < len(times[0, :]):
            trigger_offset = times[0, trigger]
            times -= trigger_offset
        #attr_list = self.tango_device.get_attribute_list()
        #prop_list = self.property_list()
        for chan in channels_list:
            try:
                name = "chanel_%03i" % chan
                prop = self.tango_device.get_property(name)[name]
                sdf = "save_data" in prop
                slf = "save_log" in prop
                # save signal properties
                if sdf or slf:
                    self.save_prop(zip_file, chan)
                    self.save_log(log_file, chan)
                    if sdf:
                        self.save_data(zip_file, chan)
            except:
                self.logger.warning("%s data save exception" % self.name)
                self.logger.debug('', exc_info=True)

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
