import numpy

from TangoAttributeHistory import TangoAttributeHistory


class TangoAttributeIntegral(TangoAttributeHistory):

    def read_attribute(self):
        super().read_attribute()
        self.channel.file_name = self.channel.name + '_integral'
        self.channel.properties['history'] =['False']
        if self.channel.y is not None:
            self.channel.y = numpy.trapz(self.channel.y, self.channel.x)
