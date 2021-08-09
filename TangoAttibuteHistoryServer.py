#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Attribute history tango device server
A. L. Sanin, started 05.08.2021
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
DEFAULT_ATTRIB_CONFIG = {'ready': False, 'attribute': None, 'device_proxy': None,
                         'local_name': None, 'name': None}


class TangoAttributeHistoryServer(TangoServerPrototype):
    server_version = '1.0'
    tango_devices = {}
    logger = TangoServerPrototype.config_logger()

    @command(dtype_in=str, dtype_out=str)
    def read_history(self, name):
        return str(read_attribute_history(name))

    @command(dtype_in=int)
    def set_log_level(self, level):
        self.logger.setLevel(level)
        msg = '%s Log level set to %d' % (self.get_name(), level)
        self.logger.info(msg)
        self.info_stream(msg)

    def init_device(self):
        try:
            if self in TangoAttributeHistoryServer.device_list:
                self.delete_device()
            super().init_device()
            self.set_state(DevState.INIT)
            # configure remote attributes
            self.attributes = {}
            properties = self.properties()
            for prop in properties:
                if prop not in SERVER_CONFIG:
                    try:
                        s = properties[prop][0]
                        if s is not None and s != '':
                            params = json.loads(s)
                        else:
                            params = None
                        self.attributes[prop] = self.configure_attribute(prop, params)
                    except:
                        self.log_exception('Attribute %s config error' % prop)
            self.config['attributes'] = self.attributes
            TangoAttributeHistoryServer.device_list.append(self)
            self.logger.info('Device %s has been initiated with %s attributes', self.get_name(), len(self.attributes))
            self.set_state(DevState.STANDBY)
        except:
            self.log_exception()
            self.set_state(DevState.FAULT)

    def delete_device(self):
        self.remove_all_attributes()
        if self in TangoAttributeHistoryServer.device_list:
            TangoAttributeHistoryServer.device_list.remove(self)
            self.logger.info('Device %s has been deleted', self.get_name())

    def read_attribute(self, attr: tango.Attribute):
        name = attr.get_name()
        try:
            remote_name = None
            for nm in self.attributes:
                if self.attributes[nm]['local_name'] == name:
                    remote_name = nm
                    break
            conf = self.attributes[remote_name]
            if not conf['ready']:
                # reconnect to attribute
                conf = self.configure_attribute(remote_name)
            if not conf['ready']:
                msg = 'Cannot reconnect %s' % name
                self.logger.warning(msg)
                self.debug_stream(msg)
                attr.set_value(EMPTY_HISTORY)
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                return EMPTY_HISTORY
            d_p = conf['device_proxy']
            a_n = conf['attribute_name']
            n = conf['depth']
            data = d_p.attribute_history(a_n, n)
            info = d_p.get_attribute_config_ex(a_n)[0]
            try:
                scale = float(info.display_unit)
            except:
                scale = 1.0
            history = numpy.zeros((n, 2))
            for i, d in enumerate(data):
                history[i, 1] = d.value * scale
                history[i, 0] = d.time.totime()
            attr.set_value(history)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
            # self.logger.debug('Reading OK')
            return history
        except:
            self.log_exception('Error reading %s' % name)
            attr.set_value(EMPTY_HISTORY)
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            return EMPTY_HISTORY

    def configure_attribute(self, name, param=None):
        local_name = name.replace('/', '.')
        # check if attribute exists
        if local_name in self.attributes:
            self.logger.debug('Attribute exists for %s', name)
            return self.attributes[local_name]
        conf = DEFAULT_ATTRIB_CONFIG
        conf['local_name'] = local_name
        conf['name'] = name
        if param is not None:
            for p in param:
                conf[p] = param[p]
        try:
            d_n, a_n = TangoAttributeHistoryServer.split_attribute_name(name)
            conf['device_name'] = d_n
            conf['attribute_name'] = a_n
            # create device proxy
            if d_n in TangoAttributeHistoryServer.tango_devices:
                d_p = TangoAttributeHistoryServer.tango_devices[d_n]
                self.logger.debug('Using existent proxy for %s', name)
            else:
                d_p = tango.DeviceProxy(d_n)
                d_p.ready = False
                TangoAttributeHistoryServer.tango_devices[d_n] = d_p
                self.logger.debug('Proxy has been created for %s', name)
            # check if device is on
            if not d_p.ready:
                try:
                    ping = d_p.ping()
                    d_p.ready = True
                    self.logger.debug('Ping for %s is %s s', name, ping)
                except:
                    d_p.ready = False
                    self.logger.debug('No ping for %s', name)
            conf['device_proxy'] = d_p
            if not d_p.ready:
                self.logger.warning('Device is not ready for %s', name)
                return conf
            # self.logger.debug('Device is ready for %s', name)
            # check if remote attribute exists
            try:
                d_p.read_attribute(a_n)
            except:
                self.logger.warning('Attribute %s is not readable', name)
                return conf
            # check if remote attribute is polled
            if 'period' in conf:
                period = conf['period']
            else:
                period = d_p.get_attribute_poll_period(a_n)
                conf['period'] = period
            if period <= 5:
                self.logger.warning('Polling can not be enabled for %s', name)
                conf.pop('period', None)
                return conf
            d_p.poll_attribute(a_n, period)
            period = d_p.get_attribute_poll_period(a_n)
            if period <= 5:
                self.logger.warning('Polling can not be enabled for %s', name)
                return conf
            # self.logger.debug('Polling has been restarted for %s', name)
            p_s = self.convert_polling_status(d_p.polling_status(), a_n)
            depth = p_s['depth']
            conf['depth'] = depth
            self.logger.debug('Polling depth for %s is %s', name, depth)
            if 'delta_t' in conf:
                n = int(conf['delta_t'] * 1000.0 / period)
            else:
                n = int(depth)
            if n > depth:
                self.logger.warning('Not enough polling depth %s s for %s', depth * period / 1000.0, name)
            conf['ready'] = True
            # self.logger.info('Attribute for %s has been configured', name)
        except:
            self.log_exception('Attribute config exception for %s' % name)
            conf['ready'] = False
        return conf

    def create_attribute(self, name):
        conf = self.attributes.get(name, {'ready': False})
        if not conf['ready']:
            return False
        # get remote attr info
        info = conf['device_proxy'].get_attribute_config_ex(conf['attribute_name'])[0]
        # create local attribute
        local_label = conf.get('label', info.label + '_history')
        local_unit = conf.get('unit', info.unit)
        local_format = conf.get('format', info.format)
        local_display_unit = conf.get('display_unit', '')
        attr = tango.server.attribute(name=conf['local_name'], dtype=numpy.float,
                                      dformat=tango.AttrDataFormat.IMAGE,
                                      max_dim_x=2, max_dim_y=conf['depth'],
                                      fread=self.read_attribute,
                                      label=local_label,
                                      doc='history of ' + info.label,
                                      unit=local_unit,
                                      display_unit=local_display_unit,
                                      format=local_format,
                                      min_value=info.min_value,
                                      max_value=info.max_value)
        # add attr to device
        self.add_attribute(attr)
        conf['attribute'] = attr
        self.logger.debug('History attribute for %s has been created', conf['name'])
        return True

    def create_all_attributes(self):
        self.logger.debug('entry')
        n = 0
        m = 0
        for name in self.attributes:
            try:
                if self.create_attribute(name):
                    n += 1
            except:
                m += 1
                self.log_exception('Attribute %s creation error for %s' % (name, self))
        if n > 0:
            self.set_state(DevState.RUNNING)
            return True
        else:
            self.logger.warning('No attribute has been created')
            if m > 0:
                self.set_state(DevState.FAULT)
            else:
                self.set_state(DevState.STANDBY)
            return False

    def remove_all_attributes(self):
        for nm in self.attributes:
            self.remove_one_attribute(nm)

    def remove_one_attribute(self, name):
        try:
            conf = self.attributes[name]
            if conf['attribute'] is not None:
                self.remove_attribute(conf['local_name'])
                conf['attribute'] = None
                self.logger.debug('Attribute has been %s removed', name)
        except:
            self.log_exception('Attribute %s can not be removed' % name)


def post_init_callback():
    TangoAttributeHistoryServer.logger.debug('entry')
    for dev in TangoAttributeHistoryServer.device_list:
        TangoAttributeHistoryServer.logger.debug('loop %s', dev)
        dev.create_all_attributes()
        # for attr_n in dev.attributes:
        #     try:
        #         conf = dev.attributes[attr_n]
        #         if conf['ready']:
        #             if conf['attribute'] is None:
        #                 # get remote attr info
        #                 info = conf['device_proxy'].get_attribute_config_ex(conf['attribute_name'])[0]
        #                 # create local attribute
        #                 local_label = conf.get('label', info.label + '_history')
        #                 local_unit = conf.get('unit', info.unit)
        #                 local_format = conf.get('format', info.format)
        #                 local_display_unit = conf.get('display_unit', '')
        #                 attr = tango.server.attribute(name=conf['local_name'], dtype=numpy.float,
        #                                               dformat=tango.AttrDataFormat.IMAGE,
        #                                               max_dim_x=2, max_dim_y=conf['depth'],
        #                                               fread=dev.read_attribute,
        #                                               label=local_label,
        #                                               doc='history of ' + info.label,
        #                                               unit=local_unit,
        #                                               display_unit=local_display_unit,
        #                                               format=local_format,
        #                                               min_value=info.min_value,
        #                                               max_value=info.max_value)
        #                 # add attr to device
        #                 dev.add_attribute(attr)
        #                 conf['attribute'] = attr
        #                 dev.logger.info('History attribute for %s has been created', conf['name'])
        #     dev.set_state(DevState.RUNNING)
        # except:
        #     dev.log_exception('Initialize Error %s %s' % (dev, attr_n))
        #     dev.set_state(DevState.FAULT)
    TangoAttributeHistoryServer.logger.debug('exit')


def read_attribute_history(name, delta_t=None):
    logger = TangoAttributeHistoryServer.config_logger()
    conf = {}
    history = numpy.empty((0, 2))
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
        info = d_p.get_attribute_config_ex(a_n)[0]
        try:
            scale = float(info.display_unit)
        except:
            scale = 1.0
        history = numpy.zeros((n, 2))
        for i, d in enumerate(data):
            history[i, 1] = d.value * scale
            history[i, 0] = d.time.totime()
        conf['ready'] = True
    except:
        logger.debug('', exc_info=True)
        conf['ready'] = False
    return history


if __name__ == "__main__":
    TangoAttributeHistoryServer.run_server(post_init_callback=post_init_callback)
    # an = 'sys/tg_test/1/double_scalar'
    # a = read_attribute_history(an)
    # print(a, a[:, 1].ptp())
