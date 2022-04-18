from PrototypeDumperDevice import *


class AdlinkADC(PrototypeDumperDevice):
    def __init__(self, device_name='binp/nbi/adc0', folder="ADC_0", **kwargs):
        super().__init__(device_name, **kwargs)
        self.shot_time = 1.0
        self.folder = folder
        self.shot = -7
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
        if ns < 0:
            return False
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
                channel = PrototypeDumperDevice.Channel(self.device, attr)
                channel.logger = self.logger
                properties = channel.read_properties()
                # save_data and save_log flags
                sdf = self.as_boolean(properties.get("save_data", [False])[0])
                slf = self.as_boolean(properties.get("save_log", [False])[0])
                properties_saved = False
                log_saved = False
                data_saved = False
                retry_count = 3
                while retry_count > 0:
                    try:
                        if sdf or slf:
                            if channel.y is None:
                                channel.read_y()
                            if channel.x is None:
                                channel.read_x()
                        # Save signal properties
                        if sdf or slf and not properties_saved:
                            if channel.save_properties(zip_file, folder):
                                properties_saved = True
                        # Save log
                        if slf and not log_saved:
                            channel.save_log(log_file)
                            log_saved = True
                        # Save signal data
                        if sdf and not data_saved:
                            channel.save_data(zip_file, folder)
                            data_saved = True
                        break
                    except:
                        log_exception("%s channel save exception", self.name)
                        retry_count -= 1
                    if retry_count > 0:
                        self.logger.debug("Retries reading %s" % self.name)
                    if retry_count == 0:
                        self.logger.warning("Error reading %s" % self.name)
