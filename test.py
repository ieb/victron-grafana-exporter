
import os
import dbus
import time
from dbus_utils import unwrap_dbus_value
import logging
log = logging.getLogger(__name__)

# bus interface name
VE_INTERFACE = "com.victronenergy.BusItem"




class DbusMeterMontor:
    def __init__(self, config):
        self.includeConfig = config
        self.globalIgnore = config['global']
        self.dbusConn = dbus.SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else dbus.SystemBus()

    def includeKey(self, config, k) -> bool:
        for p in self.globalIgnore:
            if p.startswith('!'):
                if k.startswith(p[1:]):
                    log.debug(f'reject {k} {p}')
                    return False
            else:
                if k.startswith(p):
                    return True
        for p in config:
            if p.startswith('!'):
                if k.startswith(p[1:]):
                    log.debug(f' reject {k} {p}')
                    return False
            if k.startswith(p):
                return True        
            if p == '!*':
                log.debug(f' reject {k} {p}')
                return False
        return True

    def scan(self) -> list:
        dbusNames = self.dbusConn.list_names()
        payload = {}
        now = time.time()
        nowSeconds = int(now)
        for x in dbusNames:
            serviceName = str(x)
            includeServiceConfig = None
            for k,v in self.includeConfig.items():
                if serviceName.startswith(k):
                    includeServiceConfig = v
                    break
            if includeServiceConfig != None:
                print(f'Processing {x}')
                values = self.dbusConn.call_blocking(serviceName, '/', VE_INTERFACE, 'GetValue', '', [])
                metrics = []
                for k,v in values.items():
                    if self.includeKey(includeServiceConfig, k):
                        value = unwrap_dbus_value(v)
                        if isinstance(value, (int, float)):
                            metrics.append(f'{k}={value}')
                        else:
                            log.debug(f' reject type {value}')
                log.debug("\n".join(metrics))
                payload[serviceName] = f'{serviceName},source=test {",".join(metrics)} {nowSeconds}000000000'
        return payload;



if __name__ == '__main__':

    includeConfig = {
        'global': [
            '!Mgmt/',
            '!Device',
            '!Product',
            '!Model',
            '!AllowedRoles',
            '!Role',
            '!HardwareVersion',
            '!FirmwareVersion',
            '!Serial',
        ],      
        'com.victronenergy.settings': [
            'Settings/DynamicGeneration',
            '!*'
            ],
        'com.victronenergy.battery': [
            '!AvailableBatteryServices',
            '!AutoSelectedTemperatureService',
            '!Dc/Battery/TemperatureService'
            ],
        'com.victronenergy.system': [
            '!*'
            ],
        'com.victronenergy.vebus': [
            '!Devices/'
            ],
        'com.victronenergy.pvinverter': [
            ],
        'com.victronenergy.grid': [
            ]
    }

    dbusMon = DbusMeterMontor(includeConfig)
    payload = dbusMon.scan()
    total = 0
    for k,v in payload.items():
        total = total + len(v)
        print(f'{k} {len(v)} {v}')

    print(f'total {total}')