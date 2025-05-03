import dbus

import logging
log = logging.getLogger(__name__)

dbus_int_types = (dbus.Int32, dbus.UInt32, dbus.Byte, dbus.Int16, dbus.UInt16, dbus.UInt32, dbus.Int64, dbus.UInt64)


def unwrap_dbus_value(val):
    """Converts D-Bus values back to the original type. For example if val is of type DBus.Double,
    a float will be returned."""
    if isinstance(val, dbus_int_types):
        return int(val)
    if isinstance(val, dbus.Double):
        return float(val)
    if isinstance(val, dbus.Array):
        v = [unwrap_dbus_value(x) for x in val]
        return None if len(v) == 0 else v
    if isinstance(val, (dbus.Signature, dbus.String)):
        return str(val)
    # Python has no byte type, so we convert to an integer.
    if isinstance(val, dbus.Byte):
        return int(val)
    if isinstance(val, dbus.ByteArray):
        return "".join([bytes(x) for x in val])
    if isinstance(val, (list, tuple)):
        return [unwrap_dbus_value(x) for x in val]
    if isinstance(val, (dbus.Dictionary, dict)):
        # Do not unwrap the keys, see comment in wrap_dbus_value
        return dict([(x, unwrap_dbus_value(y)) for x, y in val.items()])
    if isinstance(val, dbus.Boolean):
        return bool(val)
    return val    

class BusItemTracker(object):
    '''
    Watches the dbus for changes to a single value on a service.
    The value is available at .value, it will be None is no value is present
    @param bus dbus object, session or system
    @param serviceName  eg com.victronenergy.system
    @param path path of the property eg /Ac/L1/Power
    '''
    def __init__(self, bus, serviceName : str,  path : str, onchange):
        self._path = path
        self._value = None
        self._onchange = onchange
        self._values = {}
        self._match = bus.get_object(serviceName, path, introspect=False).connect_to_signal(
            "ItemsChanged", self._items_changed_handler)
        log.info(f' added tracker for  {serviceName} {path}')


    def __del__(self):
        self._match.remove()
        self._match = None
    
    @property
    def value(self):
        return self._value
    
    def _items_changed_handler(self, items: dict) -> None:
        if not isinstance(items, dict):
            return
        for path, changes in items.items():
            try:
                self._values[str(path)] = unwrap_dbus_value(changes['Value'])
            except KeyError:
                continue
        self._onchange(self._values)