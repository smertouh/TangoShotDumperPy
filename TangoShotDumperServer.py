#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Shot dumper tango device server
A. L. Sanin, started 25.06.2021
"""

import time
import sys
import logging

import numpy

import tango
from tango import AttrQuality, AttrWriteType, DispLevel, DevState, DebugIt
from tango.server import Device, attribute, command, pipe, device_property

NaN = float('nan')


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


class TangoShotDumperServer(Device):
    version = '1.0'
    devices = []
    from .imports import *

    logger = config_logger(name=__qualname__, level=logging.DEBUG)

    def init_device(self):
        if self not in TangoShotDumperServer.devices:
            TangoShotDumperServer.devices.append(self)
        self.picolog = None
        self.device_type_str = "Unknown PicoLog device"
        self.device_name = ''
        self.device_proxy = None
        self.channels_list = []
        self.record_initiated = False
        self.data_ready_value = False
        self.init_result = None
        self.points = 1000
        self.record_us = 1000000
        self.trigger_enabled = 0
        self.trigger_auto = 0
        self.trigger_auto_ms = 0
        self.trigger_channel = 1
        self.trigger_dir = 0
        self.trigger_threshold = 2048
        self.trigger_hysteresis = 100
        self.trigger_delay = 10.0
        try:
            self.set_state(DevState.INIT)
            self.device_name = self.get_name()
            self.device_proxy = tango.DeviceProxy(self.device_name)
            # read config from device properties
            level = self.get_device_property('log_level', 10)
            self.logger.setLevel(level)
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
            self.init_result = None
            msg = '%s %s has been initialized' % (self.device_name, self.device_type_str)
            self.logger.info(msg)
            self.info_stream(msg)
            self.set_state(DevState.STANDBY)
        except Exception as ex:
            self.init_result = ex
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
                    msg = '%s Recording finished, data is ready' % dev.device_name
                    dev.logger.info(msg)
                    dev.info_stream(msg)
            except:
                dev.record_initiated = False
                dev.data_ready_value = False
                msg = '%s Reading data error' % dev.device_name
                dev.logger.warning(msg)
                dev.error_stream(msg)
                dev.logger.debug('', exc_info=True)
    # PicoPyServer.logger.debug('loop exit')


if __name__ == "__main__":
    TangoShotDumperServer.run_server(event_loop=looping)
