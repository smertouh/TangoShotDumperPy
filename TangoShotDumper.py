#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Stand-alone version of Tango dumper
A. L. Sanin, started 07.09.2021
"""
import datetime
import logging
import os
import sys
import time
import zipfile

sys.path.append('../TangoUtils')
from Configuration import Configuration
from config_logger import *


class TangoShotDumper:
    _version = '1.1'
    _name = 'Tango Shot Dumper'

    def __init__(self, config_file_name=None):
        self.logger = config_logger(format_string=LOG_FORMAT_STRING_SHORT)
        # set defaults
        self.log_file = None
        self.zip_file = None
        self.out_dir = None
        self.locked = False
        self.lock_file = None
        if config_file_name is None:
            if len(sys.argv) > 1:
                self.config_file_name = self.__class__.__name__ + '_' + sys.argv[1].strip() + '.json'
            else:
                self.config_file_name = self.__class__.__name__ + '.json'
        else:
            self.config_file_name = config_file_name
        # default config
        self.config = Configuration(self.config_file_name,
                                    {"sleep": 1.0, 'log_level': logging.DEBUG, "out_root_dir": '.\\data\\',
                                     "shot_number": 1, "shot_time": 0.0, "devices": []
                                     }
                                    )
        self.out_root_dir = self.config.get("out_root_dir")
        self.shot_number_value = self.config.get("shot_number")
        self.shot_time_value = self.config.get("shot_time")
        self.dumper_items = []

    def read_shot_number(self):
        return self.shot_number_value

    def write_shot_number(self, value):
        self.shot_number_value = value
        self.config['shot_number'] = value

    def read_shot_time(self):
        return self.shot_time_value

    def write_shot_time(self, value=None):
        if value is None:
            value = time.time()
        self.shot_time_value = value
        self.config['shot_time'] = value

    def set_config(self):
        file_name = self.config.file_name
        if file_name is None:
            file_name = ''
        try:
            # set log level
            self.logger.setLevel(self.config.get('log_level', logging.DEBUG))
            self.logger.debug('Log level has been set to %s',
                              logging.getLevelName(self.logger.getEffectiveLevel()))
            self.config["sleep"] = self.config.get("sleep", 1.0)
            self.out_root_dir = self.config.get("out_root_dir", '.\\data\\')
            self.write_shot_number(self.config.get("shot_number", 1))
            self.write_shot_time(self.config.get("shot_time", time.time()))
            # Restore devices
            devices = self.config.get("devices", [])
            self.dumper_items = []
            if len(devices) <= 0:
                self.logger.error("No devices declared")
                return False
            for device in devices:
                try:
                    if 'exec' in device:
                        exec(device["exec"])
                    if 'eval' in device:
                        item = eval(device["eval"])
                        item.logger = self.logger
                        self.dumper_items.append(item)
                        self.logger.info("%s has been added" % item.name)
                    else:
                        self.logger.info("No 'eval' option for %s" % device)
                except:
                    log_exception(self, "Device creation error in %s", str(device), level=logging.WARNING)
            if len(self.dumper_items) > 0:
                self.logger.debug('%d dumper devices has been configured', len(self.dumper_items))
                return True
            else:
                self.logger.warning('No dumper devices has been configured')
                return False
        except:
            log_exception(self, 'Configuration set error for %s', file_name, level=logging.WARNING)
            return False

    def write_config(self, file_name=None):
        try:
            self.config.write(file_name)
            self.logger.debug('Configuration saved to %s', self.config.file_name)
            return True
        except:
            log_exception(self, 'Configuration save error to %s', file_name)
            return False

    def activate(self):
        n = 0
        for item in self.dumper_items:
            try:
                if item.activate():
                    n += 1
            except:
                log_exception(self, "%s activation error", item)
        return n

    def check_new_shot(self):
        for item in self.dumper_items:
            try:
                if item.new_shot():
                    self.shot_number_value += 1
                    self.write_shot_number(self.shot_number_value)
                    self.write_shot_time(time.time())
                    return True
            except:
                log_exception(self, "Error checking new shot for %s", item)
        return False

    @staticmethod
    def date_time_stamp():
        return datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def time_stamp():
        return datetime.datetime.today().strftime('%H:%M:%S')

    @staticmethod
    def get_log_folder():
        ydf = datetime.datetime.today().strftime('%Y')
        mdf = datetime.datetime.today().strftime('%Y-%m')
        ddf = datetime.datetime.today().strftime('%Y-%m-%d')
        folder = os.path.join(ydf, mdf, ddf)
        return folder

    def make_log_folder(self):
        of = os.path.join(self.out_root_dir, self.get_log_folder())
        try:
            if not os.path.exists(of):
                os.makedirs(of)
                self.logger.debug("Output folder %s has been created", of)
            self.out_dir = of
            return True
        except:
            self.logger.warning("Can not create output folder %s", of)
            self.out_dir = None
            return False

    def lock_output_dir(self, folder=None):
        if folder is None:
            folder = self.out_dir
        if self.locked:
            self.logger.warning("Unexpected lock")
            self.zip_file.close()
            self.log_file.close()
            self.unlock_output_dir()
        self.lock_file = open(os.path.join(folder, "lock.lock"), 'w+')
        self.locked = True
        self.logger.debug("Directory %s locked", folder)

    def unlock_output_dir(self):
        if self.lock_file is not None:
            self.lock_file.close()
            os.remove(self.lock_file.name)
        self.locked = False
        self.lock_file = None
        self.logger.debug("Directory unlocked")

    def open_log_file(self, folder: str = ''):
        log_file = open(os.path.join(folder, self.get_log_file_name()), 'a')
        return log_file

    @staticmethod
    def get_log_file_name():
        file_name = datetime.datetime.today().strftime('%Y-%m-%d.log')
        return file_name

    @staticmethod
    def open_zip_file(folder):
        fn = datetime.datetime.today().strftime('%Y-%m-%d_%H%M%S.zip')
        zip_file_name = os.path.join(folder, fn)
        zip_file = zipfile.ZipFile(zip_file_name, 'a', compression=zipfile.ZIP_DEFLATED)
        return zip_file

    def process(self):
        try:
            # activate items in self.dumper_items
            if self.activate() <= 0:
                self.logger.info("No active devices")
                return
            # check for new shot
            if not self.check_new_shot():
                return
            # new shot - save signals
            dts = self.date_time_stamp()
            self.config['shot_dts'] = dts
            print("\r\n%s New Shot %d" % (dts, self.shot_number_value))
            self.make_log_folder()
            self.lock_output_dir()
            self.log_file = self.open_log_file(self.out_dir)
            # Write date and time
            self.log_file.write(dts)
            # Write shot number
            self.log_file.write('; Shot=%d; Shot_time=%s' % (self.shot_number_value, self.shot_time_value))
            # Open zip file
            self.zip_file = self.open_zip_file(self.out_dir)
            for item in self.dumper_items:
                if item.active:
                    print("Saving from %s" % item.name)
                    try:
                        item.save(self.log_file, self.zip_file)
                    except:
                        log_exception(self, "Exception saving %s", str(item))
            zfn = os.path.basename(self.zip_file.filename)
            self.zip_file.close()
            self.log_file.write('; File=%s\n' % zfn)
            self.log_file.close()
            self.unlock_output_dir()
            self.write_config()
        except:
            log_exception(self, "Unexpected exception")
        print(self.time_stamp(), "Waiting for next shot ...")
        return


if __name__ == "__main__":
    tsd = TangoShotDumper()
    if tsd.set_config():
        t0 = time.time()
        while True:
            time.sleep(tsd.config['sleep'])
            try:
                tsd.process()
            except:
                log_exception(tsd, "%s Process exception", tsd)
