from DumperItem import *


class TangoAttribute(DumperItem):
    def __init__(self, device_name, attribute_name, zip_folder=None, force=True, ahead=None):
        super().__init__(device_name)
        self.attribute_name = attribute_name
        self.folder = zip_folder
        self.force = force
        self.ahead = ahead
        # self.retry_count = 3
        self.channel = DumperItem.Channel(self.device, attribute_name)

    def save(self, log_file, zip_file, zip_folder=None):
        if zip_folder is None:
            zip_folder = self.folder
        # save_data and save_log flags
        sdf = self.properties().get("save_data", [False])[0]
        slf = self.properties().get("save_log", [False])[0]
        # force save if requested during attribute creation
        if self.force:
            sdf = True
            slf = True
        if sdf or slf:
            self.channel.save_properties(zip_file, zip_folder)
            self.channel.read_y()
            self.channel.read_x()
        if slf:
            self.channel.save_log(log_file)
        if sdf:
            self.channel.save_data(zip_file, zip_folder)
