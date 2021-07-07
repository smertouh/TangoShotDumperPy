#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Shot dumper tango device server
A. L. Sanin, started 05.07.2021
"""
import datetime
import logging
import os
import sys
import time
import json
import zipfile

import numpy
import tango
from tango import AttrQuality, AttrWriteType, DispLevel, DevState
from tango.server import Device, attribute, command, pipe, device_property

from TangoServerPrototype import TangoServerPrototype, Configuration


class TangoAttributeHistoryServer(TangoServerPrototype):
    version = '0.0'

    shot_time = attribute(label="shot_time", dtype=float,
                          display_level=DispLevel.OPERATOR,
                          access=AttrWriteType.READ,
                          unit="s", format="%d",
                          doc="Shot time")

    @command(dtype_in=str, dtype_out=str)
    def read_history(self, name):
        return str(read_attribute_history(name))

    def init_device(self):
        # set default properties
        self.logger = self.config_logger(name=__name__, level=logging.DEBUG)
        self.device_proxy = tango.DeviceProxy(self.get_name())
        self.shot_time_value = 0.0
        self.config = Configuration()
        # configure device
        try:
            self.set_state(DevState.INIT)
            # read config from device properties
            level = self.get_device_property('log_level', logging.DEBUG)
            self.logger.setLevel(level)
            # read config from file and set config
            config_file = self.get_device_property('config_file', 'TangoAttributeHistoryServer.json')
            self.config = Configuration(config_file)
            self.set_config()
            # read and set shot time
            t = self.get_device_property('shot_time', 0.0)
            self.write_shot_time(t)
            # configure remote attributes
            self.attributes = {}
            properties = self.properties()
            for prop in properties:
                try:
                    self.attributes[prop] = eval(properties[prop])
                except:
                    pass
            if self not in TangoAttributeHistoryServer.device_list:
                TangoAttributeHistoryServer.device_list.append(self)
            self.logger.info('Device %s added with %s attributes', self.get_name(), len(self.attributes))
        except:
            self.log_exception()
            self.set_state(DevState.FAULT)

    def read_shot_time(self):
        return self.shot_time_value

    def write_shot_time(self, value):
        self.set_device_property('shot_time', str(value))
        self.shot_time_value = value

    def set_config(self):
        try:
            # log level
            self.logger.setLevel(self.config.get('log_level', logging.DEBUG))
            self.logger.debug("Log level set to %s" % self.logger.level)
            # Restore server parameters
            self.shot = self.config.get('shot', 0)
            # Restore devices
            items = self.config.get("devices", [])
            self.devices = []
            if len(items) <= 0:
                self.logger.error("No devices declared")
                return False
            for unit in items:
                try:
                    if 'exec' in unit:
                        exec(unit["exec"])
                    if 'eval' in unit:
                        item = eval(unit["eval"])
                        self.devices.append(item)
                        self.logger.info("%s has been added" % item)
                    else:
                        self.logger.info("No 'eval' option for %s" % unit)
                except:
                    self.logger.warning("Error in %s" % str(unit))
                    self.logger.debug('', exc_info=True)
            self.logger.debug('Configuration restored from %s' % self.config.get('file_name'))
            return True
        except:
            self.logger.info('Configuration read error')
            self.logger.debug('', exc_info=True)
            return False

    def configure_target(self, name, param):
        conf = {'alive': False}
        d_n, a_n = TangoAttributeHistoryServer.split_attribute_name(name)
        conf['device_name'] = d_n
        conf['attribute_name'] = a_n
        d_p = tango.DeviceProxy(d_n)
        conf['device_proxy'] = d_p
        try:
            if not d_p.is_attribute_polled(a_n):
                self.logger.debug('Polling is disabled for %s', name)
                return conf
            # test if device is alive
            d_p.ping()
            p_s = TangoAttributeHistoryServer.convert_polling_status(d_p.polling_status(), a_n)
            a = 'depth'
            if p_s[a] <= 0:
                self.logger.debug('Polling is disabled for %s', name)
                return conf
            if delta_t is not None:
                n = int(delta_t * 1000.0 / p_s['period'])
            else:
                n = int(p_s[a])
            if n > p_s[a]:
                self.logger.debug('Polling depth is only for %s s', p_s[a] * p_s['period'] / 1000.0)
                n = p_s[a]
            a = 'period'
            conf[a] = p_s[a]
            data = d_p.attribute_history(a_n, n)
            history = numpy.zeros((n, 2))
            for i, d in enumerate(data):
                history[i, 1] = d.value
                history[i, 0] = d.time.totime()
            conf['alive'] = True
        except:
            logger.debug('', exc_info=True)
            conf['alive'] = False
        return history

    # def restore_polling(self, attr_name: str):
    #     try:
    #         p = self.get_attribute_property(attr_name, 'polling')
    #         pn = int(p)
    #         self.dp.poll_attribute(attr_name, pn)
    #     except:
    #         #self.logger.warning('', exc_info=True)
    #         pass


def looping():
    t0 = time.time()
    for dev in TangoAttributeHistoryServer.server_device_list:
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


def post_init_callback():
    for dev in TangoAttributeHistoryServer.server_device_list:
        for attr_n in dev.attributes:
            try:
                conf = dev.attributes[attr_n]
                if 'alive' not in conf or not conf['alive']:
                    conf['alive'] = False
                    d_n, a_n = dev.split_attribute_name(attr_n)
                    conf['device_name'] = d_n
                    conf['attr_name'] = a_n
                    d_p = tango.DeviceProxy(d_n)
                    conf['device'] = d_p
                    try:
                        d_p.ping(a_n)
                        a_c = d_p.get_attribute_config_ex(a_n)
                        p_s = TangoAttributeHistoryServer.convert_polling_status(d_p.polling_status(), a_n)
                        a = 'depth'
                        if a in conf and conf[a] > p_s[a]:
                            dev.logger.debug('Polling depth mismatch %s > %s', conf[a], p_s[a])
                        a = 'period'
                        if a in conf and conf[a] != p_s[a]:
                            dev.logger.debug('Polling period mismatch %s != %s', conf[a], p_s[a])
                        # create local attribute
                        attr = tango.Attr(attr_n, [[float], [float]], tango.AttrWriteType.READ)
                        dev.add_attribute(attr, dev.read_general)
                        conf['attribute'] = attr
                        conf['alive'] = True
                    except:
                        conf['alive'] = False

            except:
                pass


    #             attribute_history(self, attr_name, depth,
    #                               extract_as=ExtractAs.Numpy)→sequence < DeviceAttributeHistory >
    #
    #             is_attribute_polled(self, attr_name)→bool
    #
    #             is_locked(self)→bool
    #
    #             poll_attribute(self, attr_name, period)→None
    #             Add
    #             an
    #             attribute
    #             to
    #             the
    #             list
    #             of
    #             polled
    #             attributes.Parametersattr_name(str)
    #             attribute
    #             nameperiod(int)
    #             polling
    #             period in milliseconds
    #
    #
    #
    #             set_attribute_config(self, attr_info_ex) -> None
    #             Change the extended attribute configuration
    #             for the specified attributeParametersattr_info_ex(AttributeInfoEx) extended attribute informa-tion


def read_attribute_history(name, delta_t=None):
    logger = TangoAttributeHistoryServer.config_logger()
    conf = {}
    history = [[], []]
    conf['alive'] = False
    d_n, a_n = TangoAttributeHistoryServer.split_attribute_name(name)
    conf['device_name'] = d_n
    conf['attribute_name'] = a_n
    d_p = tango.DeviceProxy(d_n)
    conf['device_proxy'] = d_p
    try:
        if not d_p.is_attribute_polled(a_n):
            logger.debug('Polling is disabled for %s', name)
            return history
        # test if device is alive
        d_p.ping()
        p_s = TangoAttributeHistoryServer.convert_polling_status(d_p.polling_status(), a_n)
        a = 'depth'
        if p_s[a] <= 0:
            logger.debug('Polling is disabled for %s', name)
            return history
        if delta_t is not None:
            n = int(delta_t * 1000.0 / p_s['period'])
        else:
            n = int(p_s[a])
        if n > p_s[a]:
            logger.debug('Polling depth is only for %s s', p_s[a] * p_s['period'] / 1000.0)
            n = p_s[a]
        a = 'period'
        conf[a] = p_s[a]
        data = d_p.attribute_history(a_n, n)
        history = numpy.zeros((n, 2))
        for i, d in enumerate(data):
            history[i, 1] = d.value
            history[i, 0] = d.time.totime()
        conf['alive'] = True
    except:
        logger.debug('', exc_info=True)
        conf['alive'] = False
    return history


if __name__ == "__main__":
    # TangoShotDumperServer.run_server(post_init_callback=post_init_callback, event_loop=looping)
    an = 'sys/tg_test/1/double_scalar'
    a = read_attribute_history(an)
    print(a, a[:, 1].ptp())
