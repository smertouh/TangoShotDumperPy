#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Shot dumper tango device server
A. L. Sanin, started 25.06.2021
"""
import datetime
import logging
import os
import sys
import time
import json
import zipfile

import tango
from tango import AttrQuality, AttrWriteType, DispLevel, DevState
from tango.server import Device, attribute, command, pipe, device_property

from TangoServerPrototype import TangoServerPrototype
from TangoShotDumper import TangoShotDumper
from TangoUtils import log_exception


class TangoShotDumperServer(TangoServerPrototype, TangoShotDumper):
    server_version = '1.1'
    server_name = 'Tango Shot Dumper Server'

    shot_number = attribute(label="shot_number", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%d",
                            doc="Last shot number")

    shot_time = attribute(label="shot_time", dtype=float,
                          display_level=DispLevel.OPERATOR,
                          access=AttrWriteType.READ,
                          unit="s", format="%f",
                          doc="Last shot time")

    def init_device(self):
        # init base class TangoServerPrototype self.set_config() will be called insight
        TangoServerPrototype.init_device(self)
        if self.get_state() ==  DevState.RUNNING:
            # add to servers list
            if self not in TangoShotDumperServer.device_list:
                TangoShotDumperServer.device_list.append(self)
            #
            print(TangoShotDumperServer.time_stamp(), "Waiting for next shot ...")
        else:
            self.logger.warning('Errors init device')

    def set_config(self):
        try:
            # set_config for TangoServerPrototype part
            TangoServerPrototype.set_config(self)
            # set shot_number and short time from DB
            db = self.device_proxy.get_device_db()
            pr = db.get_device_attribute_property(self.get_name(), 'shot_number')
            try:
                value = int(pr['shot_number']['__value'][0])
            except:
                value = 0
            self.write_shot_number(value)
            # set shot_time
            pr = db.get_device_attribute_property(self.get_name(), 'shot_time')
            try:
                value = float(pr['shot_time']['__value'][0])
            except:
                value = 0.0
            self.write_shot_time(value)
            # init ShortDumper part
            TangoShotDumper.__init__(self, self.config.file_name)
            # set_config for TangoShotDumper part
            TangoShotDumper.set_config(self)
            return True
        except:
            log_exception('Configuration set error for %s', self.config.file_name)
            return False


def looping():
    t0 = time.time()
    for dev in TangoShotDumperServer.device_list:
        dt = time.time() - t0
        if dt < dev.config['sleep']:
            time.sleep(dev.config['sleep'] - dt)
        t0 = time.time()
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
