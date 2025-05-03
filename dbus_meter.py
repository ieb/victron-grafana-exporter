import os
import dbus
from dbus_utils import BusItemTracker

import logging
log = logging.getLogger(__name__)


class Meter:
    def get_measurement_name(self) -> str:
        raise Exception('Implemented by subclass')
    def get_fields(self) -> dict:
        raise Exception('Implemented by subclass')


class DbusMeterModel:
    name: str
    measurement_name: str
    servicenamePrefix: str
    mappings: dict
    debug: str

    def __init__(self, name: str, measurement_name: str, servicenamePrefix: str, mappings:dict, debug: False):
        self.name = name
        self.measurement_name = measurement_name
        self.servicenamePrefix = servicenamePrefix
        self.mappings = mappings
        self.debug = debug

class DBusMeters:
    meterConfigs = []

    def __init__(self, config:dict):
        c = config['meters']
        for meter in c:
            self.meterConfigs.append(
                DbusMeterModel(meter['name'], 
                    meter['measurement_name'], 
                    meter['serviceNamePrefix'],
                    meter['mappings'],
                    meter['debug']))

    def create(self) -> list:
        meters = []
        for meterConfig in self.meterConfigs:
            meters.append(DbusMeter(meterConfig))
        return meters

class DbusMeter(Meter):
    '''
    Sets up a connection to the local dbus and collects metrics as a snapshot
    the paths to collect are defined by mappings.

    '''
    fields = {}
    mappings = {}
    tracker = None
    def __init__(self, config: DbusMeterModel):
        self.config = config
        dbusConn = dbus.SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else dbus.SystemBus()
        dbusNames = dbusConn.list_names()
        for x in dbusNames:
            s = str(x)
            if s.startswith(config.servicenamePrefix):
                serviceName = s
        if serviceName == None:
            raise Exception(f'service name not found')
        self.tracker = BusItemTracker(dbusConn, serviceName, '/', self.update)

    def destroy(self):
        if self.tracker != None:
            self.tracker.__del__()
            self.tracker = None

    def get_measurement_name(self) -> str:
        return self.config.measurement_name

    def get_fields(self) -> dict:
        return self.fields

    def updateIfNDef(self, infoName: str, dbusPath: str, changes: dict) -> None:
        try:
            self.fields[infoName] = changes[dbusPath]
        except:
            pass

    def update(self, changes) -> None:
        for name, path in self.config.mappings.items():
            self.updateIfNDef(name, path, changes)
        if self.config.debug:
            log.info(f'changes:{changes} fields:{self.fields}')
