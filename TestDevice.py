import time
from DumperDevice import *


class TestDevice(DumperDevice):
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

    def name(self):
        return "TestDevice_%d" % self.n

    def __str__(self):
        return self.name()

    def activate(self):
        if self.active:
            return True
        self.active = True
        self.time = time.time()
        self.logger.debug("TestDevice %d activated" % self.n)
        return True

    def new_shot(self):
        if 0.0 <= self.delta_t < (time.time() - self.time):
            self.shot += 1
            self.time = time.time()
            self.logger.debug("TestDevice %d - New shot %d" % (self.n, self.shot))
            return True
        return False

    def save(self, log_file, zip_file):
        self.logger.debug("TestDevice %d - Save" % self.n)
        log_file.write('; TestDev_%d=%f' % (self.n, self.time))
        if self.points > 0:
            buf = ""
            for k in range(self.points):
                s = '%f; %f' % (float(k), numpy.sin(time.time() + float(self.n) + float(k) / 100.0) + 0.1 * numpy.sin(
                    time.time() + float(k) / 5.0))
                buf += s.replace(",", ".")
                if k < self.points - 1:
                    buf += '\r\n'
            entry = "test_device/channel_%d.txt" % self.n
            zip_file.writestr(entry, buf)
            entry = "test_device/parameters_channel_%d.txt" % self.n
            zip_file.writestr(entry, "name=test_device_%d\r\nxlabel=Point number\r\n" % self.n)
            zip_file.writestr(entry, "units=a.u.")