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

NaN = float('nan')


class TangoAttributeHistoryServer(Device):
    version = '1.0'
    server_device_list = []

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

    @command(dtype_in=str, dtype_out=str)
    def read_history(self, name):
        return str(read_attribute_history(name))

    def init_device(self):
        # set default properties
        self.logger = self.config_logger(name=__name__, level=logging.DEBUG)
        self.device_proxy = tango.DeviceProxy(self.get_name())
        self.log_file = None
        self.zip_file = None
        self.out_root_dir = '.\\data\\'
        self.out_dir = None
        self.locked = False
        self.shot_number_value = 0
        self.shot_time_value = 0.0
        self.config = Configuration()
        # config
        try:
            self.set_state(DevState.INIT)
            # read config from device properties
            level = self.get_device_property('log_level', logging.DEBUG)
            self.logger.setLevel(level)
            # read config from file
            self.config_file = self.get_device_property('config_file', 'TangoAttributeHistoryServer.json')
            self.config = Configuration(self.config_file)
            self.set_config()
            # read shot number
            n = self.get_device_property('shot_number', 0)
            self.write_shot_number(n)
            # read shot time
            t = self.get_device_property('shot_time', 0.0)
            self.write_shot_time(t)
            properties = self.properties()
            self.attributes = {}
            for prop in properties:
                try:
                    self.attributes[prop] = eval(properties[prop])
                except:
                    pass
            if self not in TangoAttributeHistoryServer.server_device_list:
                TangoAttributeHistoryServer.server_device_list.append(self)
            self.logger.info('Device %s added with %s attributes', self.get_name(), len(self.attributes))
        except:
            msg = 'Exception in TangoAttributeHistoryServer'
            self.logger.error(msg)
            self.error_stream(msg)
            self.logger.debug('', exc_info=True)
            self.set_state(DevState.FAULT)

    def log_exception(self, message=None, *args, level=logging.ERROR):
        if message is None:
            ex_type, ex_value, traceback = sys.exc_info()
            message = 'Exception %s %s'
            args = (ex_type, ex_value)
        msg = message % args
        self.logger.log(level, msg)
        self.error_stream(msg)
        self.logger.debug('', exc_info=True)

    def read_shot_number(self):
        return self.shot_number_value

    def write_shot_number(self, value):
        self.set_device_property('shot_number', str(value))
        self.shot_number_value = value

    def read_shot_time(self):
        return self.shot_time_value

    def write_shot_time(self, value):
        self.set_device_property('shot_time', str(value))
        self.shot_time_value = value

    def get_device_property(self, prop: str, default=None):
        try:
            # self.assert_proxy()
            pr = self.device_proxy.get_property(prop)[prop]
            result = None
            if len(pr) > 0:
                result = pr[0]
            if default is None:
                return result
            if result is None or result == '':
                result = default
            else:
                result = type(default)(result)
        except:
            # self.logger.debug('Error reading property %s for %s', prop, self.name)
            result = default
        return result

    def set_device_property(self, prop: str, value: str):
        try:
            # self.assert_proxy()
            self.device_proxy.put_property({prop: value})
        except:
            self.logger.info('Error writing property %s for %s', prop, self.device_name)
            self.logger.debug('', exc_info=True)

    def property_list(self, filter: str = '*'):
        return self.device_proxy.get_property_list(filter)

    def properties(self, filter: str = '*'):
        # returns dictionary with device properties
        names = self.device_proxy.get_property_list(filter)
        return self.device_proxy.get_property(names)

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

    def config_get(self, name, default=None):
        try:
            result = self.config.get(name, default)
            if default is not None:
                result = type(default)(result)
        except:
            result = default
        return result

    def set_config(self):
        try:
            # log level
            self.logger.setLevel(self.config.get('log_level', logging.DEBUG))
            self.logger.debug("Log level set to %s" % self.logger.level)
            # Restore server parameters
            self.sleep = self.config.get("sleep", 1.0)
            self.out_root_dir = self.config.get("out_root_dir", '.\\data\\')
            self.shot = self.config.get('shot', 0)
            # Restore devices
            items = self.config.get("devices", [])
            self.device_list = []
            if len(items) <= 0:
                self.logger.error("No devices declared")
                return False
            for unit in items:
                try:
                    if 'exec' in unit:
                        exec(unit["exec"])
                    if 'eval' in unit:
                        item = eval(unit["eval"])
                        self.device_list.append(item)
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

    def write_config(self, file_name):
        try:
            self.config['shot'] = self.shot
            with open(file_name, 'w') as configfile:
                configfile.write(json.dumps(self.config, indent=4))
            self.logger.debug('Configuration saved to %s' % file_name)
        except:
            self.logger.info('Configuration save error to %s' % file_name)
            self.logger.debug('', exc_info=True)
            return False

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
                    d_n, a_n = split_attribute_name(attr_n)
                    conf['device_name'] = d_n
                    conf['attr_name'] = a_n
                    d_p = tango.DeviceProxy(d_n)
                    conf['device'] = d_p
                    try:
                        d_p.ping(a_n)
                        a_c = d_p.get_attribute_config_ex(a_n)
                        p_s = convert_polling_status(d_p.polling_status(), a_n)
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


def convert_polling_status(p_s, name):
    result = {'period': 0, 'depth': 0}
    s1 = 'Polled attribute name = '
    s2 = 'Polling period (mS) = '
    s3 = 'Polling ring buffer depth = '
    # s4 = 'Time needed for the last attribute reading (mS) = '
    # s4 = 'Data not updated since 54 mS'
    # s6 = 'Delta between last records (in mS) = 98, 100, 101, 98'
    n1 = s1 + name
    for s in p_s:
        if s.startswith(n1):
            for ss in s.split('\n'):
                try:
                    if ss.startswith(s2):
                        result['period'] = int(ss.replace(s2, ''))
                    elif ss.startswith(s3):
                        result['depth'] = int(ss.replace(s3, ''))
                except:
                    pass
    return result

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


def split_attribute_name(name):
    split = name.split('/')
    a_n = split[-1]
    d_n = name.replace('/' + a_n, '')
    return d_n, a_n


def read_attribute_history(name, delta_t=None):
    logger = TangoAttributeHistoryServer.config_logger()
    conf = {}
    history = [[], []]
    conf['alive'] = False
    d_n, a_n = split_attribute_name(name)
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
        p_s = convert_polling_status(d_p.polling_status(), a_n)
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
            history[i, 0] = d.value
            history[i, 1] = d.time.totime()
        conf['alive'] = True
    except:
        logger.debug('', exc_info=True)
        conf['alive'] = False
    return history


class Configuration():
    def __init__(self, file_name=None, default=None):
        if default is None:
            default = {}
        if file_name is not None:
            if not self.read(file_name):
                self.data = default

    def get(self, name, default=None):
        try:
            result = self.data.get(name, default)
            if default is not None:
                result = type(default)(result)
        except:
            result = default
        return result

    def add(self, name: str, value):
        self.data[name] = value

    def read(self, file_name):
        # Read config from file
        with open(file_name, 'r') as configfile:
            self.data = json.loads(configfile.read())
            self.add('file_name', file_name)
        return True

    def write(self, file_name):
        with open(file_name, 'w') as configfile:
            configfile.write(json.dumps(self.data, indent=4))
        return True


if __name__ == "__main__":
    # TangoShotDumperServer.run_server(post_init_callback=post_init_callback, event_loop=looping)
    an = 'sys/tg_test/1/double_scalar'
    a = read_attribute_history(an)
    print(a, a[:, 1].ptp())
