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

