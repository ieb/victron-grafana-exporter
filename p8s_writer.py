
import requests
import time
from dbus_meter import Meter
import logging
log = logging.getLogger(__name__)

class P8SMetricsMeter(Meter):
    def __init__(self):
        self.metrics = {}

    def inc(self, key):
        try:
            self.metrics[key] = self.metrics[key]+1
        except:
            self.metrics[key] = 1
    def get_measurement_name(self) -> str:
        return "p8s"
    def get_fields(self) -> dict:
        return self.metrics
 

class P8sWriter:

    def __init__(self, source, config: dict,
            meters : type([Meter]) = []):
        self.source = source
        self.url = config['url']
        self.userId = config['userId']
        self.apiKey = config['apiKey']
        self.meters = meters
        self.metrics = P8SMetricsMeter()
        self.meters.append(self.metrics)
        self.debug = False


    def update(self):
        try:
            now = time.time()
            nowSeconds = int(now)
            payload = []
            for meter in self.meters:
                metrics = []
                for fieldName, value in meter.get_fields().items():
                    metrics.append(f'{fieldName}={value}')

                if len(metrics) > 0:
                    payload.append(f'{meter.get_measurement_name()},source={self.source} {",".join(metrics)} {nowSeconds}000000000')

            body = "\n".join(payload)
            try:
                if self.debug > 0:
                    log.info(f'p8s < {body}')
                response = requests.post(self.url, 
                         headers = {
                           'Content-Type': 'text/plain',
                           'Authorization': f'Bearer {self.userId}:{self.apiKey}'
                         },
                         data = str(body)
                )
                self.metrics.inc('p8s.sent')
                if response.status_code == 204:
                    self.metrics.inc('p8s.ok')
                    if self.debug > 0:
                        log.info(f'p8s < {response.status_code} {response}')
                else:
                    self.metrics.inc('p8s.fail')
                    if self.debug > 0:
                        log.info(f'p8s < {response.json()}')
            except Exception as err:
                self.metrics.inc('p8s.exception')
                traceback.print_exc()
        except:
            traceback.print_exc()            
            log.errro(f'Update failed')
        return True
