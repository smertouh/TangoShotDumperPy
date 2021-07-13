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

EMPTY_HISTORY = numpy.empty((0, 2))
SERVER_CONFIG = ('log_level', 'config_file')

class TangoAttributeHistoryServer(TangoServerPrototype):
    version = '0.0'
    tango_devices = []

    # shot_time = attribute(label="shot_time", dtype=float,
    #                       display_level=DispLevel.OPERATOR,
    #                       access=AttrWriteType.READ,
    #                       unit="s", format="%d",
    #                       doc="Shot time")

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
            self.set_server_config()
            # # read and set shot time
            # t = self.get_device_property('shot_time', 0.0)
            # self.write_shot_time(t)
            # configure remote attributes
            self.attributes = {}
            properties = self.properties()
            for prop in properties:
                if prop not in SERVER_CONFIG:
                    try:
                        params = json.loads(properties[prop])
                        self.attributes[prop] = self.configure_attribute(prop, params)
                    except:
                        self.log_exception('Attribute %s config error' % prop)
            if self not in TangoAttributeHistoryServer.device_list:
                TangoAttributeHistoryServer.device_list.append(self)
            self.logger.info('Device %s added with %s attributes', self.get_name(), len(self.attributes))
            self.set_state(DevState.STANDBY)
        except:
            self.log_exception()
            self.set_state(DevState.FAULT)

    # def read_shot_time(self):
    #     return self.shot_time_value
    #
    # def write_shot_time(self, value):
    #     self.set_device_property('shot_time', str(value))
    #     self.shot_time_value = value

    def set_server_config(self):
        try:
            # log level
            self.logger.setLevel(self.config.get('log_level', logging.DEBUG))
            self.logger.debug("Log level set to %s" % self.logger.level)
            self.logger.debug('Configuration restored from %s' % self.config.get('file_name'))
            return True
        except:
            self.log_exception('Configuration set error')
            return False

    def configure_attribute(self, name, param=None):
        if param is None:
            param = {}
        # check if attribute exists
        if name in self.attributes:
            self.logger.debug('Attribute for %s exists', name)
            return self.attributes[name]
        conf = {'ready': False, 'attribute': None, 'local_name': name.replace('/', '_'),
                'device_proxy': None, 'period': -1}
        try:
            d_n, a_n = TangoAttributeHistoryServer.split_attribute_name(name)
            conf['device_name'] = d_n
            conf['attribute_name'] = a_n
            # create device proxy
            if d_n in TangoAttributeHistoryServer.tango_devices:
                d_p = TangoAttributeHistoryServer.tango_devices[d_n]
            else:
                d_p = tango.DeviceProxy(d_n)
                d_p.ready = False
                TangoAttributeHistoryServer.tango_devices[d_n] = d_p
            # check if device is on
            if not d_p.ready:
                try:
                    d_p.ping()
                    d_p.ready = True
                except:
                    d_p.ready = False
            conf['device_proxy'] = d_p
            if not d_p.ready:
                self.logger.debug('Device is off for %s', name)
                return conf
            self.logger.debug('Device for %s detected', name)
            # check if remote attribute exists
            try:
                result = d_p.read_attribute(a_n)
            except:
                self.logger.debug('Attribute %s is not readable', name)
                return conf
            # check if remote attribute is polled
            period = d_p.get_attribute_poll_period(a_n)
            conf['period'] = period
            if not d_p.is_attribute_polled(a_n):
                d_p.poll_attribute(a_n, period)
                period = d_p.get_attribute_poll_period(a_n)
            conf['period'] = period
            if period <= 0:
                self.logger.warning('Polling can not be enabled for %s', name)
                return conf
            self.logger.debug('Polling has been restarted for %s', name)



            depth = d_p.get_attr_poll_ring_depth(a_n)
            conf['depth'] = depth
            if 'delta_t' in param:
                n = int(param['delta_t'] * 1000.0 / period)
            else:
                n = int(depth)
            if n > depth:
                self.logger.warning('Polling depth is only %s s for %s', depth * period / 1000.0, name)
            conf['ready'] = True
        except:
            self.log_exception('Attribute config exception')
            conf['ready'] = False
        return conf

    def initialize(self, param=None):
        n = 0
        for name in self.attributes:
            try:
                conf = self.attributes[name]
                if conf['ready']:
                    if conf['attribute'] is None:
                        # create local attribute
                        if conf['attribute'] is None:
                            # create local attribute
                            attr = tango.Attr(conf['local_name'], [[float], [float]], tango.AttrWriteType.READ)
                            self.add_attribute(attr, self.read_attribute)
                            conf['attribute'] = attr
                            # set local attr info according to the remote one
                            info = conf['device_proxy'].get_attribute_config_ex(conf['attribute_name'])
                            #             attr_info_ex(AttributeInfoEx) extended attribute information
                            info = AttributeInfoEx()
                            info.data_format = tango.AttrDataFormat.IMAGE
                            info.data_type = tango.AttrDataFormat.IMAGE
                            info.writable = False
                            self.set_attribute_config(info)
                            self.logger.debug('Attribute %s initialized', conf['local_name'])
                    n += 1
            except:
                self.log_exception('Attribute %s initialization failure' % name)
        if n > 0:
            self.set_state(DevState.RUNNING)
        else:
            self.set_state(DevState.STANDBY)

    def read_attribute(self, attr: tango.Attribute):
        name = attr.get_name()
        try:
            remote_name = None
            for nm in self.attributes:
                if nm['local_name'] == name:
                    remote_name = nm
            conf = self.attributes[remote_name]
            if not conf['ready']:
                # reconnect to attribute
               conf = self.configure_attribute(remote_name)
            if not conf['ready']:
                msg = 'Cannot reconnect %s' % name
                self.logger.debug(msg)
                self.debug_stream(msg)
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                return EMPTY_HISTORY
            d_p = conf['device_proxy']
            a_n = conf['attribute_name']


            if not d_p.is_attribute_polled(a_n):
                self.ogger.debug('Polling is disabled for %s', name)
                return EMPTY_HISTORY
            # test if device is alive
            d_p.ping()
            p_s = TangoAttributeHistoryServer.convert_polling_status(d_p.polling_status(), a_n)
            a = 'depth'
            if p_s[a] <= 0:
                self.logger.debug('Polling is disabled for %s', name)
                return EMPTY_HISTORY
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
            conf['ready'] = True
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        except:
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            self.log_exception('Error reading %s', name)
            return EMPTY_HISTORY


def post_init_callback():
    for dev in TangoAttributeHistoryServer.server_device_list:
        for attr_n in dev.attributes:
            try:
                conf = dev.attributes[attr_n]
                if conf['ready']:
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
    history = numpy.empty((0,2))
    conf['ready'] = False
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
        conf['ready'] = True
    except:
        logger.debug('', exc_info=True)
        conf['ready'] = False
    return history


if __name__ == "__main__":
    # TangoShotDumperServer.run_server(post_init_callback=post_init_callback, event_loop=looping)
    an = 'sys/tg_test/1/double_scalar'
    a = read_attribute_history(an)
    print(a, a[:, 1].ptp())
