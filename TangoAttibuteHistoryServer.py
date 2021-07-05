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
        # config
        try:
            self.set_state(DevState.INIT)
            # read config from device properties
            level = self.get_device_property('log_level', logging.DEBUG)
            self.logger.setLevel(level)
            # read config from file
            self.config_file = self.get_device_property('config_file', 'TangoAttributeHistoryServer.json')
            self.read_config(self.config_file)
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

    def read_config(self, file_name):
        try:
            # Read config from file
            with open(file_name, 'r') as configfile:
                s = configfile.read()
            self.config = json.loads(s)
            # Restore log level
            self.logger.setLevel(self.config_get('log_level', logging.DEBUG))
            self.logger.debug("Log level set to %s" % self.logger.level)
            # Restore server parameters
            self.sleep = self.config_get("sleep", 1.0)
            self.out_root_dir = self.config_get("out_root_dir", '.\\data\\')
            self.shot = self.config_get('shot', 0)
            # Restore devices
            items = self.config_get("devices", [])
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
            self.logger.debug('Configuration restored from %s' % file_name)
            return True
        except:
            self.logger.info('Configuration read error from %s' % file_name)
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

    def read_history(self, attr: tango.Attribute):
        attr_name = attr.get_name()
        #self.logger.debug('read_general entry %s %s', self.device_name, attr_name)
        if not self.is_connected():
            self.set_error_attribute_value(attr)
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            msg = '%s %s Waiting for reconnect' % (self.device_name, attr_name)
            self.logger.debug(msg)
            self.debug_stream(msg)
            return []






    def activate(self):
        n = 0
        for item in self.device_list:
            try:
                if item.activate():
                    n += 1
            except:
                # self.server_device_list.remove(item)
                self.logger.error("%s activation error", item)
                self.logger.debug('', exc_info=True)
        return n

    def check_new_shot(self):
        for item in self.device_list:
            try:
                if item.new_shot():
                    self.shot_number_value += 1
                    self.write_shot_number(self.shot_number_value)
                    self.shot_time_value = time.time()
                    self.write_shot_time(self.shot_time_value)
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
            self.shot += 1
            self.config['shot'] = self.shot
            self.config['shot_time'] = dts
            print("\r\n%s New Shot %d" % (dts, self.shot))
            self.make_log_folder()
            self.lock_output_dir()
            self.log_file = self.open_log_file(self.out_dir)
            # Write date and time
            self.log_file.write(dts)
            # Write shot number
            self.log_file.write('; Shot=%d' % self.shot)
            # Open zip file
            self.zip_file = self.open_zip_file(self.out_dir)
            for item in self.device_list:
                print("Saving from %s" % item.name)
                try:
                    item.logger = self.logger
                except:
                    pass
                try:
                    item.save(self.log_file, self.zip_file)
                except:
                    self.logger.error("Exception saving %s" % str(item))
                    self.logger.debug('', exc_info=True)
            zfn = os.path.basename(self.zip_file.filename)
            self.zip_file.close()
            self.log_file.write('; File=%s' % zfn)
            self.log_file.write('\n')
            self.log_file.close()
            self.unlock_output_dir()
            self.write_config(self.config_file)
        except:
            self.logger.error("Unexpected exception")
            self.logger.debug('', exc_info=True)
        print(TangoShotDumperServer.time_stamp(), "Waiting for next shot ...")
        return

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
                split = attr_n.split('/')
                a_n = split[-1]
                d_n = attr_n.replace('/' + a_n, '')
                conf['device_name'] = d_n
                conf['attr_name'] = a_n
                d_p = tango.DeviceProxy(d_n)
                conf['device'] = d_p
                try:
                    d_p.ping(a_n)
                    conf['alive'] = True
                except:
                    conf['alive'] = False
                a_c = d_p.get_attribute_config_ex(a_n)
                attr = tango.Attr(attr_n, tango.DevDouble, tango.AttrWriteType.READ)
                dev.add_attribute(attr, dev.read_general)

                attribute_history(self, attr_name, depth,
                                  extract_as=ExtractAs.Numpy)→sequence < DeviceAttributeHistory >

                get_attribute_config_ex(self, name)→AttributeInfoListEx:

                is_attribute_polled(self, attr_name)→bool

                is_locked(self)→bool

                ping(self)→int
                time                 elapsed in microseconds
                Throwsexception if                 device is not alive

                poll_attribute(self, attr_name, period)→None
                Add
                an
                attribute
                to
                the
                list
                of
                polled
                attributes.Parametersattr_name(str)
                attribute
                nameperiod(int)
                polling
                period in milliseconds

                polling_status(self)→sequence < str >
                Return(sequence < str >)
                One
                string
                for each polled command / attribute.Eachstring is multi-line string with:•
                attribute / command
                name•  attribute / command
                polling
                period in milliseconds•  attribute / command
                polling
                ring
                buffer•  time
                needed
                for last attribute / command execution in milliseconds•  time since data in the ring buffer has not been updated•  delta time between the last records in the ring buffer•  exception parameters in case of the last execution failed

                set_attribute_config(self, attr_info_ex) -> None
                Change the extended attribute configuration
                for the specified attributeParametersattr_info_ex(AttributeInfoEx) extended attribute informa-tion


            except:
                pass


if __name__ == "__main__":
    TangoShotDumperServer.run_server(post_init_callback=post_init_callback, event_loop=looping)
