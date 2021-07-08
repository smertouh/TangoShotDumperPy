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
from tango import AttrQuality, AttrWriteType, DispLevel, DevState, AttributeInfoEx
from tango.server import Device, attribute, command, pipe, device_property

from TangoServerPrototype import TangoServerPrototype, Configuration


class TangoAttributeHistoryServer(TangoServerPrototype):
    version = '0.0'
    tango_devices = []

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
                if prop not in ('log_level', 'config_file'):
                    try:
                        params =  json.loads(properties[prop])
                        self.attributes[prop] = self.configure_target(prop, params)
                    except:
                        self.log_exception('Attribute config error')
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
            self.logger.debug('Configuration restored from %s' % self.config.get('file_name'))
            return True
        except:
            self.log_exception('Configuration set error')
            return False

    def configure_target(self, name, param=None):
        if param is None:
            param = {}
        conf = {'alive': False, 'attribute': None, 'local_name': name.replace('/', '_')}
        d_n, a_n = TangoAttributeHistoryServer.split_attribute_name(name)
        conf['device_name'] = d_n
        conf['attribute_name'] = a_n
        if d_n in TangoAttributeHistoryServer.tango_devices:
            d_p = TangoAttributeHistoryServer.tango_devices[d_n]
        else:
            d_p = tango.DeviceProxy(d_n)
            TangoAttributeHistoryServer.tango_devices[d_n] = d_p
            d_p.alive = False
        if not d_p.alive:
            # test if device is alive
            try:
                d_p.ping()
                d_p.alive = True
            except:
                d_p.alive = False
        conf['device_proxy'] = d_p
        if not d_p.alive:
            self.logger.debug('Device is offline for %s', name)
            return conf
        try:
            if not d_p.is_attribute_polled(a_n):
                period = d_p.get_attribute_poll_period(a_n)
                d_p.poll_attribute(a_n, period)
                self.logger.debug('Polling has been restarted for %s', name)
            depth = d_p.get_attr_poll_ring_depth(a_n)
            period = d_p.get_attribute_poll_period(a_n)
            conf['period'] = period
            conf['depth'] = depth
            if period <= 0:
                self.logger.warning('Polling can not be enabled for %s', name)
                return conf
            if 'delta_t' in param:
                n = int(param['delta_t'] * 1000.0 / period)
            else:
                n = int(depth)
            if n > depth:
                self.logger.warning('Polling depth is only %s s for %s', depth * period / 1000.0, name)
            conf['alive'] = True
        except:
            self.log_exception('Attribute config exception')
            conf['alive'] = False
        return conf


def post_init_callback():
    for dev in TangoAttributeHistoryServer.server_device_list:
        for attr_n in dev.attributes:
            try:
                conf = dev.attributes[attr_n]
                if conf['alive']:
                    if conf['attribute'] is None:
                        # create local attribute
                        attr = tango.Attr(conf['local_name'], [[float], [float]], tango.AttrWriteType.READ)
                        dev.add_attribute(attr, dev.read_general)
                        conf['attribute'] = attr
                        info = conf['device_proxy'].get_attribute_config_ex(conf['attribute_name'])
                        #             attr_info_ex(AttributeInfoEx) extended attribute information
                        info = AttributeInfoEx()
                        info.data_format = tango.AttrDataFormat.IMAGE
                        info.data_type = tango.AttrDataFormat.IMAGE
                        info.writable = False
                        dev.set_attribute_config(info)
            except:
                pass




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
