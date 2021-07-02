import time

import numpy
import tango

import TangoAttribute


class TangoAttributeHistory(TangoAttribute):
    def __init__(self, device_name, attribute_name, folder=None, delta_t=10.0):
        super().__init__(self, device_name, attribute_name, folder, True)
        self.delta_t = delta_t

    def read_attribute(self):
        self.channel.y = None
        self.channel.x = None
        if not self.channel.y_attr.data_format == tango._tango.AttrDataFormat.SCALAR:
            self.logger.info("Integral of non SCALAR attribute %s" % self.channel.name)
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
            if h.AttrQuality != tango._tango.AttrQuality.ATTR_VALID:
                y[i] = numpy.nan
            else:
                y[i] = h.value
                x[i] = h.time.totime()
        index = (y != numpy.nan)
        index = numpy.logical_and(index, x > (time.time() - self.delta_t))
        if len(y[index]) <= 0:
            self.logger.info("%s No values for %f seconds in history", self.channel.name, self.delta_t)
            return
        self.channel.y = y[index]
        self.channel.x = x[index]
# get_attribute_poll_period polling period in milliseconds
#
# polling_status(self) → sequence<str>
#
#         Return the device polling status.
#
#     Parameters
#
#         None
#     Return
#
#         (sequence<str>) One string for each polled command/attribute. Each string is multi-line string with:
#
#                 attribute/command name
#
#                 attribute/command polling period in milliseconds
#
#                 attribute/command polling ring buffer
#
#                 time needed for last attribute/command execution in milliseconds
#
#                 time since data in the ring buffer has not been updated
#
#                 delta time between the last records in the ring buffer
#
#                 exception parameters in case of the last execution failed
#
#
 # get_attr_poll_ring_depth(self, attr_name) → int
 #
 #    Returns the attribute poll ring depth.
 #
 #    Parameters
 #
 #        attr_name (str) – the attribute name
 #    Returns
 #
 #        the attribute poll ring depth
 #    Return type
 #
 #        int
