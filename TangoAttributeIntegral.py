import numpy

from TangoAttributeHistory import TangoAttributeHistory


class TangoAttributeIntegral(TangoAttributeHistory):

    def read_attribute(self):
        super().read_attribute()
        self.channel.file_name = self.channel.name + '_integral'
        self.channel.properties['history'] =['False']
        self.channel.properties['integral'] =['True']
        if self.channel.y is not None:
            self.channel.y = numpy.trapz(self.channel.y, self.channel.x)
            self.channel.properties['delta_t'] =[str(numpy.ptp(self.channel.x))]
            self.channel.x = None
