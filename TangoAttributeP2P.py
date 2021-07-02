import numpy

from TangoAttributeHistory import TangoAttributeHistory


class TangoAttributeP2P(TangoAttributeHistory):

    def read_attribute(self):
        super().read_attribute()
        self.channel.file_name = self.channel.name + '_p2p'
        self.channel.properties['history'] =['False']
        self.channel.properties['p2p'] =['True']
        if self.channel.y is not None:
            self.channel.y = numpy.max(self.channel.y) - numpy.min(self.channel.y)
