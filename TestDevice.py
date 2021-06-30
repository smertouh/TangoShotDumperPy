import time
from DumperItem import *


class TestDevice(DumperItem):
    n = 0

    def __init__(self, delta_t=-1.0, points=0):
        super().__init__('', 'test_device')
        self.n = TestDevice.n
        self.name = 'test_device_%d' % self.n
        self.time = time.time()
        self.shot = 0
        self.active = False
        self.delta_t = delta_t
        self.points = points
        TestDevice.n += 1

    def __str__(self):
        return self.name

    def activate(self):
        if self.active:
            return True
        self.active = True
        self.time = time.time()
        self.logger.debug("TestDevice %d activated" % self.n)
        return True

    def new_shot(self):
        if 0.0 < self.delta_t < (time.time() - self.time):
            self.shot += 1
            self.time = time.time()
            self.logger.debug("TestDevice %d - New shot %d" % (self.n, self.shot))
            return True
        return False

    def save(self, log_file, zip_file, zip_folder='test_device'):
        self.logger.debug("TestDevice %d - Save" % self.n)
        log_file.write('; %s=%f' % (self.name, self.time))
        if self.points > 0:
            buf = ""
            for k in range(self.points):
                w = 2.0 * numpy.pi * float(k) / (self.points -1)
                s = '%f; %f' % (float(k), numpy.sin(w + float(self.n)) + 0.1 * numpy.sin(4.0 * w))
                buf += s.replace(",", ".")
                if k < self.points - 1:
                    buf += '\r\n'
            entry = zip_folder + "/channel_%d.txt" % self.n
            zip_file.writestr(entry, buf)
            entry = zip_folder + "/paramchannel_%d.txt" % self.n
            zip_file.writestr(entry, "name=test_device_%d\r\nxlabel=Point number\r\nunit=a.u." % self.n)
