#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Shot dumper tango device server
A. L. Sanin, started 25.06.2021
"""
import datetime
import logging
import os
import time
import json
import zipfile

import tango
from tango import AttrQuality, AttrWriteType, DispLevel, DevState
from tango.server import Device, attribute, command, pipe, device_property

from TangoServerPrototype import TangoServerPrototype


class TangoShotDumperServer(TangoServerPrototype):
    server_version = '1.0'
    server_name = 'Tango Shot Dumper Server'

    shot_number = attribute(label="shot_number", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%d",
                            doc="Shot number")

    shot_time = attribute(label="shot_time", dtype=float,
                          display_level=DispLevel.OPERATOR,
                          access=AttrWriteType.READ,
                          unit="s", format="%d",
                          doc="Shot time")

    @command(dtype_in=int)
    def set_log_level(self, level):
        self.logger.setLevel(level)
        msg = '%s Log level set to %d' % (self.get_name(), level)
        self.logger.info(msg)
        self.info_stream(msg)

    def init_device(self):
        # set defaults
        self.log_file = None
        self.zip_file = None
        self.out_root_dir = '.\\data\\'
        self.out_dir = None
        self.locked = False
        self.shot_number_value = 0
        self.shot_time_value = 0.0
        #
        super().init_device()
        #
        self.set_state(DevState.INIT)
        try:
            # add to servers list
            if self not in TangoShotDumperServer.device_list:
                TangoShotDumperServer.device_list.append(self)
            #
            self.set_state(DevState.RUNNING)
            print(TangoShotDumperServer.time_stamp(), "Waiting for next shot ...")
        except:
            self.set_state(DevState.FAULT)
            self.log_exception('Exception in TangoShotDumperServer')

    def read_shot_number(self):
        return self.shot_number_value

    def write_shot_number(self, value):
        #self.set_device_property('shot_number', str(value))
        self.shot_number_value = value
        db = self.device_proxy.get_device_db()
        pr = db.get_device_attribute_property(self.get_name(), 'shot_number')
        pr['shot_number']['__value'] = str(value)
        db.put_device_attribute_property(self.get_name(), pr)

    # def write_attribute(self, attr_name, value):
    #     self.set_device_property(attr_name, str(value))
    #     self.shot_number_value = value
    #     db = self.device_proxy.get_device_db()
    #     apr = db.get_device_attribute_property(self.device_proxy.name(), attr_name)
    #     apr[attr_name]['__value'] = str(value)
    #     db.put_device_attribute_property(self.device_proxy.name(), apr)

    def read_shot_time(self):
        return self.shot_time_value

    def write_shot_time(self, value):
        self.set_device_property('shot_time', str(value))
        self.shot_time_value = value

    def set_config(self):
        try:
            super().set_config()
            file_name = self.config.file_name
            if file_name is None:
                file_name = ''
            self.config["sleep"] = self.config.get("sleep", 1.0)
            self.out_root_dir = self.config.get("out_root_dir", '.\\data\\')
            # set shot_number
            db = self.device_proxy.get_device_db()
            pr = db.get_device_attribute_property(self.get_name(), 'shot_number')
            try:
                value = int(pr['shot_number']['__value'][0])
            except:
                value = 0
            # self.shot_number_value = self.config.get('shot_number', 0)
            self.shot_number_value = value
            self.config['shot_number'] = value
            # self.write_shot_number(self.shot_number_value)
            self.write_shot_number(value)
            # set shot_time
            self.shot_time_value = self.config.get('shot_time', 0.0)
            self.write_shot_time(self.shot_time_value)
            # Restore devices
            items = self.config.get("devices", [])
            self.dumper_devices = []
            if len(items) <= 0:
                self.logger.error("No devices declared")
                return False
            for unit in items:
                try:
                    if 'exec' in unit:
                        exec(unit["exec"])
                    if 'eval' in unit:
                        item = eval(unit["eval"])
                        item.logger = self.logger
                        self.dumper_devices.append(item)
                        self.logger.info("%s has been added" % item.name)
                    else:
                        self.logger.info("No 'eval' option for %s" % unit)
                except:
                    self.logger.warning("Error in %s" % str(unit))
                    self.logger.debug('', exc_info=True)
            self.logger.debug('Configuration restored %s' % file_name)
            return True
        except:
            self.logger.info('Configuration error %s' % file_name)
            self.logger.debug('', exc_info=True)
            return False

    def write_config(self, file_name=None):
        try:
            # self.config['shot_number'] = self.shot
            self.config.write(file_name)
            if file_name is None:
                file_name = ''
            else:
                file_name = 'to ' + file_name
            self.logger.debug('Configuration saved %s' % file_name)
        except:
            self.logger.info('Configuration save error %s' % file_name)
            self.logger.debug('', exc_info=True)
            return False

    def activate(self):
        n = 0
        for item in self.dumper_devices:
            try:
                if item.activate():
                    n += 1
            except:
                # self.server_device_list.remove(item)
                self.logger.error("%s activation error", item)
                self.logger.debug('', exc_info=True)
        return n

    def check_new_shot(self):
        for item in self.dumper_devices:
            try:
                if item.new_shot():
                    self.shot_number_value += 1
                    self.write_shot_number(self.shot_number_value)
                    self.config['shot_number'] = self.shot_number_value
                    self.shot_time_value = time.time()
                    self.write_shot_time(self.shot_time_value)
                    self.config['shot_time'] = self.shot_time_value
                    return True
            except:
                # self.device_list.remove(item)
                self.logger.error("%s check for new shot", item)
                self.logger.debug('', exc_info=True)
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
            self.logger.debug("Can not create output folder %s", of)
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
        logf = open(os.path.join(folder, self.get_log_file_name()), 'a')
        return logf

    @staticmethod
    def get_log_file_name():
        logfn = datetime.datetime.today().strftime('%Y-%m-%d.log')
        return logfn

    @staticmethod
    def open_zip_file(folder):
        fn = datetime.datetime.today().strftime('%Y-%m-%d_%H%M%S.zip')
        zip_file_name = os.path.join(folder, fn)
        zip_file = zipfile.ZipFile(zip_file_name, 'a', compression=zipfile.ZIP_DEFLATED)
        return zip_file

    def process(self):
        try:
            # activate items in devices_list
            if self.activate() <= 0:
                self.logger.info("No active devices")
                return
            # check for new shot
            if not self.check_new_shot():
                return
            # new shot - save signals
            dts = self.date_time_stamp()
            self.shot = self.shot_number_value
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
            for item in self.dumper_devices:
                print("Saving from %s" % item.name)
                try:
                    item.save(self.log_file, self.zip_file)
                except:
                    self.logger.error("Exception saving %s" % str(item))
                    self.logger.debug('', exc_info=True)
            zfn = os.path.basename(self.zip_file.filename)
            self.zip_file.close()
            self.log_file.write('; File=%s\n' % zfn)
            # self.log_file.write('\n')
            self.log_file.close()
            self.unlock_output_dir()
            self.write_config()
        except:
            self.logger.error("Unexpected exception")
            self.logger.debug('', exc_info=True)
        print(TangoShotDumperServer.time_stamp(), "Waiting for next shot ...")
        return


def looping():
    t0 = time.time()
    for dev in TangoShotDumperServer.device_list:
        time.sleep(dev.config['sleep'])
        try:
            dev.process()
            # msg = '%s processed' % dev.name
            # dev.logger.debug(msg)
            # dev.debug_stream(msg)
        except:
            msg = '%s process error' % dev
            dev.logger.warning(msg)
            dev.error_stream(msg)
            dev.logger.debug('', exc_info=True)


if __name__ == "__main__":
    TangoShotDumperServer.run_server(event_loop=looping)
