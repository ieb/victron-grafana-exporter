
import requests
import time
import logging
import traceback
log = logging.getLogger(__name__)

class P8SMetricsMeter():
    def __init__(self):
        self.metrics = {
            'p8s.sent': 0,
            'p8s.exception': 0,
            'p8s.fail': 0,
            'p8s.ok': 0,
        }

    def inc(self, key):
        try:
            self.metrics[key] = self.metrics[key]+1
        except:
            self.metrics[key] = 1
    def collect(self, source):
        now = time.time()
        nowSeconds = int(now)
        metrics = []
        for fieldName, value in self.metrics.items():
            metrics.append(f'{fieldName}={value}')
        return [ f've_p8s,source={source} {",".join(metrics)} {nowSeconds}000000000' ]

 

class P8sWriter:

    def __init__(self, source, collectors, watchdog, config: dict):
        self.collectors = collectors
        self.source = source
        self.url = config['url']
        self.userId = config['userId']
        self.apiKey = config['apiKey']
        self.metrics = P8SMetricsMeter()
        self.collectors.append(self.metrics)
        self.debug = False
        self.watchdog = watchdog


    def update(self):
        log.debug('starting update')
        self.watchdog.update()
        try:
            status = []
            for c in self.collectors:
                payload = c.collect(self.source)
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
                        status.append(f'{c} {response.json()}')
                        if self.debug > 0:
                            log.info(f'p8s < {response.json()}')
                except Exception as err:
                    log.error(f'Update failed Exception')
                    self.metrics.inc('p8s.exception')
                    status.append('failed collection')
                    traceback.print_exc()
            if len(status) > 0:
                log.error(status)
        except:
            traceback.print_exc()            
            log.error(f'Update failed')
        return True
