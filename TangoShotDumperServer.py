#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Shot dumper tango device server
A. L. Sanin, started 25.06.2021
"""

import logging
import sys
import time
import json

import tango
from tango import DevState
from tango.server import Device

NaN = float('nan')


class TangoShotDumperServer(Device):
    version = '1.0'
    device_list = []

    def init_device(self):
        # set default properties
        self.logger = self.config_logger(name=__qualname__, level=logging.DEBUG)
        # read config
        try:
            self.set_state(DevState.INIT)
            # read config from device properties
            level = self.get_device_property('log_level', 10)
            self.logger.setLevel(level)
            # read config from file
            self.config_file = self.get_device_property('config_file', 'ShotDumperPy.json')
            self.read_config(self.config_file)

            devices = self.get_device_property('devices', '{}')
            # create PicoLog1000 device
            self.picolog = PicoLog1000()
            self.set_state(DevState.ON)
            # change PicoLog1000 logger to class logger
            self.picolog.logger = self.logger
            # open PicoLog1000 device
            self.picolog.open()
            self.set_state(DevState.OPEN)
            self.picolog.get_info()
            self.device_type_str = self.picolog.info['PICO_VARIANT_INFO']
            # set sampling interval channels and number of points
            self.set_sampling()
            # set trigger
            self.set_trigger()
            # OK message
            msg = '%s %s has been initialized' % (self.device_name, self.device_type_str)
            self.logger.info(msg)
            self.info_stream(msg)
            self.set_state(DevState.STANDBY)
            # add device to the list
            if self not in TangoShotDumperServer.devices:
                TangoShotDumperServer.devices.append(self)
        except Exception as ex:
            msg = '%s Exception initialing PicoLog: %s' % (self.device_name, sys.exc_info()[1])
            self.logger.error(msg)
            self.error_stream(msg)
            self.logger.debug('', exc_info=True)
            self.set_state(DevState.FAULT)

    def delete_device(self):
        try:
            self.picolog.stop()
        except:
            pass
        try:
            self.picolog.close()
        except:
            pass
        self.set_state(DevState.CLOSE)
        msg = '%s PicoLog has been deleted' % self.device_name
        self.logger.info(msg)
        self.info_stream(msg)

    @staticmethod
    def config_logger(name: str = __name__, level: int = logging.DEBUG):
        logger = logging.getLogger(name)
        if not logger.hasHandlers():
            logger.propagate = False
            logger.setLevel(level)
            f_str = '%(asctime)s,%(msecs)3d %(levelname)-7s %(filename)s %(funcName)s(%(lineno)s) %(message)s'
            log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(log_formatter)
            logger.addHandler(console_handler)
        return logger

    def read_config(self, file_name):
        try:
            # Read config from file
            with open(file_name, 'r') as configfile:
                s = configfile.read()
            self.config = json.loads(s)
            # Restore log level
            self.logger.setLevel(self.config.get('log_level', logging.DEBUG))
            self.logger.log(logging.DEBUG, "Log level set to %d" % self.logger.level)
            self.config["sleep"] = float(self.config.get("sleep", 1.0))
            self.out_dir = self.config.get("out_dir", '.\\data\\')
            self.shot = self.config.get('shot', 0)
            # Restore devices
            items = self.config.get("devices", [])
            if len(items) <= 0:
                self.logger.error("No devices declared")
                return False
            for unit in items:
                try:
                    if 'exec' in unit:
                        exec(unit["exec"])
                    if 'eval' in unit:
                        item = eval(unit["eval"])
                        self.devise_list.append(item)
                        self.logger.info("%s has been added" % unit["eval"])
                    else:
                        self.logger.info("No 'eval' option for %s" % unit)
                except:
                    self.logger.warning("Error in %s initialization" % str(unit))
                    self.logger.debug('', exc_info=True)
            self.logger.info('Configuration restored from %s' % file_name)
            return True
        except:
            self.logger.info('Configuration restore error from %s' % file_name)
            self.logger.debug('', exc_info=True)
            return False


def looping():
    time.sleep(0.001)
    for dev in PicoPyServer.devices:
        if dev.record_initiated:
            try:
                if dev.picolog.ready():
                    dev.stop_time_value = time.time()
                    dev.picolog.read()
                    dev.record_initiated = False
                    dev.data_ready_value = True
                    msg = '%s Recording finished, y is ready' % dev.device_name
                    dev.logger.info(msg)
                    dev.info_stream(msg)
            except:
                dev.record_initiated = False
                dev.data_ready_value = False
                msg = '%s Reading y error' % dev.device_name
                dev.logger.warning(msg)
                dev.error_stream(msg)
                dev.logger.debug('', exc_info=True)
    # PicoPyServer.logger.debug('loop exit')


if __name__ == "__main__":
    TangoShotDumperServer.run_server(event_loop=looping)
