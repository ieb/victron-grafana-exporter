# Victron Grafana Cloud Exporter


A module to run on a Victron GX that will export p8s metrics to grafana cloud by scanning the dbus

The module runs as a service, scans 1 or more dbus trees and exports metrics to Grafana cloud
every 60s. It can read anything made available on any dbus on the system.

Writen for python 3.8 since that is the version on a GX device. It has no dependencies beyond what
is already present on a GX device.

There is also a telegraf config for MQTT -> Influx, however it was found that:

* It uses 132Mb ram and 750MV RSS which is almost 10x most other processes on the GC device.
* The MQTT plugin is hard to configure and has proven unreliable at sending metrics at all or at a reasonably low volume.
* Needs some config to stop it spawning dbus daemons and not terminating connections properly
* It seems ok for the default OS plugin, but might not be worth the resources

# Install

    mkdir /data/grafana-exporter
    # copy these files into place including service/**
    ln -s /data/grafana-exporter/service /service/grafana-exporter
    echo ln -s /data/grafana-exporter/service /service/grafana-exporter >> /data/rc.local
    svstat /data/grafana-exporter/service
    tail -F /var/log/grafana-exporter/current | tai64nlocal 

