import numpy

from TangoAttributeHistory import TangoAttributeHistory


class TangoAttributeIntegral(TangoAttributeHistory):

    def read_attribute(self):
        super().read_attribute()
        if self.channel.y is not None:
            self.channel.y = numpy.trapz(self.channel.y, self.channel.x)
