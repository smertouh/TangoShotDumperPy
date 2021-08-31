from PrototypeDumperDevice import *


class PicoLog1000(PrototypeDumperDevice):
    def __init__(self, tango_device_name: str, folder='PicoLog'):
        super().__init__(tango_device_name)
        self.folder = folder

    def save(self, log_file, zip_file, folder=None):
        # read data ready
        data_ready = self.device.read_attribute('data_ready').value
        if not data_ready:
            self.logger.warning("%s is not ready" % self.name)
            return
        # read channels list
        channels = self.device.read_attribute('channels').value
        channels_list = []
        try:
            channels_list = eval(channels)
        except:
            pass
        if len(channels_list) <= 0:
            self.logger.warning("%s empty channels list" % self.name)
            return
        # read other attributes
        trigger = self.device.read_attribute('trigger').value
        sampling = self.device.read_attribute('sampling').value
        points = self.device.read_attribute('points_per_channel').value
        # generate times array
        times = numpy.linspace(0, (points - 1) * sampling, points, dtype=numpy.float64)
        if trigger < points:
            trigger_offset = times[trigger]
            times -= trigger_offset
        # save channels data and properties
        for i, number in enumerate(channels_list):
            try:
                chan = PicoLog1000.Channel(self.device, number, format='%02i')
                properties = chan.read_properties()
                # read flags
                sdf = self.as_boolean(properties.get("save_data", ['False'])[0])
                slf = self.as_boolean(properties.get("save_log", ['False'])[0])
                # save signal properties and data
                if sdf or slf:
                    # read data
                    chan.read_y()
                    # generate times values
                    chan.x = times + (i * sampling / len(channels_list))
                    chan.save_properties(zip_file, self.folder)
                if slf:
                    chan.save_log(log_file)
                if sdf:
                    chan.save_data(zip_file, self.folder)
            except:
                self.logger.warning("%s save exception" % self.name)
                self.logger.debug('', exc_info=True)
