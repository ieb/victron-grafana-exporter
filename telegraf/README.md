# Telegraf to Grafana CLoud

As an alternative to dbus -> driver -> p8s using custom code this is config using Telgraf to Grafana Cloud over in the influxd route, which can collect from OS level plugins and MQTT.

The downside of Telegraf is it uses a whopping 130MB of RSS (774MB VSZ) which bumps a Multiplus Memory usage to 60% from more like 45%... and its not doing a lot. Compared to the other processes on a VenusOS install, it sticks out like a very sore thumb.


# Install


    mkdir /data/telegraf
    cd /data/telegraf
    wget https://dl.influxdata.com/telegraf/releases/telegraf-1.34.2_linux_armhf.tar.gz
    tar xv telegraf-1.34.2_linux_armhf.tar.gz

Copy this folder and tree into /data/telegraf such that /data/teletraf/service exists

copy /data/telegraf/etc/telegraf/.env.sample to /data/telegraf/etc/telegraf/.env and edit

    ln -s /data/telegraf/service /service/telegraf

To make it permanent

    echo ln -s /data/telegraf/service /service/telegraf



# MQTT


Connecting to the MQTT server on localhost on the GX device does not normally require auth or TLS, you can test it with 

    mosquitto_sub -t 'N/${VID}/#' -h localhost -v > capture.txt &

To see all you may need to emit a keepalive

    mosquitto_pub -t 'R/${VID}/keepalive' -m '' -h localhost

Then kill the sub job and look at capture.txt 

Format of each value is 

    N/${VID}/grid/40/Ac/L1/Current {"value":0.6802441477775574} 

Configuring telegraph to emit nicely foratted metrics is hard so I left the labels as they are, Everything will appear in a single mqtt_consumer metric labeled by topic

# Data Points Per minute

By default telegraph sends a metric on every update, which can result in > 5K data points per minute which is 5x the Grafana Cloud free tier. Even the default configuration of scrapes in Telegraf is 10s. Using a final aggregator set to send data once per minute should lower he rate and bandwidth consumption.

# Testing

Since the MQTT stream updates independent of the agent when testing a test-wait delay must be added to allow the test to see data. Also the test wait must be longer than the aggregator plugin period.

    source /data/telegraf/etc/telegraf/.env
    /data/telegraf/telegraf-1.34.2/usr/bin/telegraf --config /data/telegraf/etc/telegraf/telegraf.conf --config-directory /data/telegraf/etc/telegraf/telegraf.d/ --test-wait 60


To test one config 

    /data/telegraf/telegraf-1.34.2/usr/bin/telegraf --config /data/telegraf/etc/telegraf/telegraf.d/mqtt.conf --test-wait 10 