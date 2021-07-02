import numpy
import tango

import TangoAttribute


class TangoAttributeIntegral(TangoAttribute):
    def __init__(self, device_name, attribute_name, zip_folder=None,
                 poll_range_min=100, poll_range_max=600):
        super().__init__(self, device_name, attribute_name, zip_folder, True)
        self.poll_range_min = poll_range_min
        self.poll_range_max = poll_range_max

    def read_attribute(self):
        self.channel.y = numpy.nan
        if not self.channel.y_attr.data_format == tango._tango.AttrDataFormat.SCALAR:
            self.logger.info("Integral of non SCALAR attribute %s" % self.channel.name)
            return
        history = self.device.attribute_history(self.channel.name, self.poll_range_max)
        y = numpy.zeros(len(history))
        t = numpy.zeros(len(history))
        for i, h in enumerate(history):
            if h.AttrQuality != tango._tango.AttrQuality.ATTR_VALID:
                y[i] = numpy.nan
            else:
                y[i] = h.value
                t[i] = h.time.totime()
        index = (y != numpy.nan)
        self.channel.y = numpy.trapz(y[index], t[index])
