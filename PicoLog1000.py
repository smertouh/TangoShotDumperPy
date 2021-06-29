from DumperDevice import *


class PicoLog1000(DumperDevice):
    def __init__(self, tango_device_name: str, folder='PicoLog'):
        super().__init__(tango_device_name, folder)

    def save(self, log_file, zip_file):
        # read data ready
        data_ready = self.tango_device.read_attribute('data_ready').value
        if not data_ready:
            self.logger.warning("%s y is not ready" % self.name)
            return
        # read channels list
        channels = self.tango_device.read_attribute('channels').value
        channels_list = []
        try:
            channels_list = eval(channels)
        except:
            pass
        if len(channels_list) <= 0:
            self.logger.warning("%s empty channels list" % self.name)
            return
        # read other attributes
        trigger = self.tango_device.read_attribute('trigger').value
        sampling = self.tango_device.read_attribute('sampling').value
        points = self.tango_device.read_attribute('points_per_channel').value
        # generate times array
        times = numpy.linspace(0, (points - 1) * sampling, points, dtype=numpy.float32)
        if trigger < points:
            trigger_offset = times[trigger]
            times -= trigger_offset
        # save channels data and properties
        for i, number in enumerate(channels_list):
            try:
                chan = PicoLog1000.Channel(self.tango_device, number)
                properties = chan.properties()
                # read flags
                sdf = self.as_boolean(properties.get("save_data", ['False'])[0])
                slf = self.as_boolean(properties.get("save_log", ['False'])[0])
                # save signal properties and data
                if sdf or slf:
                    chan.save_properties(zip_file, self.folder, self.name)
                    chan.save_log(log_file)
                    if sdf:
                        # read data
                        chan.read_y()
                        # generate times values
                        chan.x = times + (i * sampling / len(channels_list))
                        chan.save_data(zip_file, self.folder)
            except:
                self.logger.warning("%s save exception" % self.name)
                self.logger.debug('', exc_info=True)
