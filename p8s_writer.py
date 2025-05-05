
import requests
import time
import logging
import traceback
log = logging.getLogger(__name__)

class P8SMetricsMeter():
    def __init__(self):
        self.metrics = {
            'p8s.sent': 0
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
        return f've_p8s,source={source} {",".join(metrics)} {nowSeconds}000000000'

 

class P8sWriter:

    def __init__(self, source, scanner, config: dict):
        self.scanner = scanner
        self.source = source
        self.url = config['url']
        self.userId = config['userId']
        self.apiKey = config['apiKey']
        self.metrics = P8SMetricsMeter()
        self.debug = False


    def update(self):
        log.debug('starting update')
        try:
            payload = self.scanner.collect(self.source)
            payload.append(self.metrics.collect(self.source))
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
            log.error(f'Update failed')
        return True
