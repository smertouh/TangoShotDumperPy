import numpy

from TangoAttributeHistory import TangoAttributeHistory


class TangoAttributeMax(TangoAttributeHistory):

    def read_attribute(self):
        super().read_attribute()
        if self.channel.y is not None:
            self.channel.y = numpy.max(self.channel.y)
