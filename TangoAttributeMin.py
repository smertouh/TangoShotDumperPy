import numpy

from TangoAttributeHistory import TangoAttributeHistory


class TangoAttributeMin(TangoAttributeHistory):

    def read_attribute(self):
        super().read_attribute()
        if self.channel.y is not None:
            self.channel.y = numpy.min(self.channel.y)
