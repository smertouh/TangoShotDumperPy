import time

import numpy
import tango

from TangoAttribute import TangoAttribute


class TangoAttributeHistory(TangoAttribute):
    def __init__(self, device_name, attribute_name, folder=None, delta_t=120.0):
        super().__init__(device_name, attribute_name, folder, True)
        self.delta_t = delta_t

    def read_attribute(self):
        self.channel.read_y()
        self.channel.y = None
        self.channel.x = None
        self.channel.file_name = self.channel.name + '_history'
        self.channel.properties['history'] =['True']
        if not self.channel.y_attr.data_format == tango._tango.AttrDataFormat.SCALAR:
            self.logger.info("History of non SCALAR attribute %s" % self.channel.name)
            return
        period = self.device.get_attribute_poll_period(self.channel.name)
        if period <= 0:
            self.logger.info("Attribute %s is not polled" % self.channel.name)
            return
        m = int(self.delta_t * 1000.0 / period + 10)
        history = self.device.attribute_history(self.channel.name, m)
        n = len(history)
        if n <= 0:
            self.logger.info("Empty history for %s" % self.channel.name)
            return
        y = numpy.zeros(n)
        x = numpy.zeros(n)
        for i, h in enumerate(history):
            if h.quality != tango._tango.AttrQuality.ATTR_VALID:
                y[i] = numpy.nan
            else:
                y[i] = h.value
                x[i] = h.time.totime()
        index = numpy.logical_and(y != numpy.nan, x > (time.time() - self.delta_t))
        if len(y[index]) <= 0:
            self.logger.info("%s No values for %f seconds in history", self.channel.name, self.delta_t)
            return
        self.channel.y = y[index]
        self.channel.x = x[index]
