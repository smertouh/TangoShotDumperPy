from PrototypeDumperDevice import *


class AdlinkADC(PrototypeDumperDevice):
    def __init__(self, device_name='binp/nbi/adc0', folder="ADC_0"):
        super().__init__(device_name)
        self.folder = folder
        self.shot = self.read_shot()

    def read_shot(self):
        try:
            shot = self.device.read_attribute("Shot_id").value
            return shot
        except:
            return -1

    def read_shot_time(self):
        try:
            t0 = time.time()
            elapsed = self.device.read_attribute('Elapsed')
            if elapsed.quality != tango._tango.AttrQuality.ATTR_VALID:
                return -self.shot_time
            self.shot_time = t0 - elapsed.value
            return self.shot_time
        except:
            return -self.shot_time

    def new_shot(self):
        ns = self.read_shot()
        if self.shot == ns:
            return False
        self.shot = ns
        return True

    def save(self, log_file, zip_file, folder=None):
        if folder is None:
            folder = self.folder
        attributes = self.device.get_attribute_list()
        for attr in attributes:
            if attr.startswith("chany"):
                retry_count = 3
                while retry_count > 0:
                    try:
                        channel = PrototypeDumperDevice.Channel(self.device, attr)
                        channel.logger = self.logger
                        # Read save_data and save_log flags
                        properties = channel.read_properties()
                        sdf = self.as_boolean(properties.get("save_data", [False])[0])
                        slf = self.as_boolean(properties.get("save_log", [False])[0])
                        # Save signal properties
                        if sdf or slf:
                            channel.save_properties(zip_file, folder)
                            channel.read_y()
                            channel.read_x()
                        # Save log
                        if slf:
                            channel.save_log(log_file)
                        # Save signal data
                        if sdf:
                            channel.save_data(zip_file, folder)
                        break
                    except:
                        self.logger.warning("%s channel save exception" % self.name)
                        self.logger.debug('', exc_info=True)
                        retry_count -= 1
                    if retry_count > 0:
                        self.logger.debug("Retry reading %s" % self.name)
                    if retry_count == 0:
                        self.logger.warning("Error reading %s" % self.name)
