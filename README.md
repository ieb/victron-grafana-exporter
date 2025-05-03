# Victron Grafana Cloud Exporter

A module to run on a Victron GX that will export p8s metrics to grafana cloud. 

The module runs as a service, watches 1 or more dbus trees and exports metrics to Grafana cloud
every 60s. It can read anything made available on any dbus on the system.

Writen for python 3.8 since that is the version on a GX device. It has no dependences beyond what
is already present on a GX device.

# Install

    mkdir /data/grafana-exporter
    # copy these files into place including service/**
    ln -s /data/grafana-exporter/service /service/grafana-exporter
    echo ln -s /data/grafana-exporter/service /service/grafana-exporter >> /data/rc.local
    svstat /data/grafana-exporter/service
    tail -F /var/log/grafana-exporter/current | tai64nlocal 

