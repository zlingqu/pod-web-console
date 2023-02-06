
import redis
import json,re
import app.config as Config

    
class RedisResource(object):
    def __init__(self, expire=None, key_prefix='', *args, **kwargs):
        redis_url = Config.myConfig.REDIS
        host, port, db = re.match(r'redis://(.*):(.*)/(.*)', redis_url).groups()
        if not hasattr(RedisResource, 'pool'):
            RedisResource.getRedisCoon(host, port, db, *args, **kwargs)
        self.client = redis.StrictRedis(connection_pool=RedisResource.pool)

    @staticmethod
    def getRedisCoon(host, port, db, *args, **kwargs):
        RedisResource.pool = redis.ConnectionPool(host=host, port=port,
                                                  db=db, socket_connect_timeout=0.5,
                                                  *args, **kwargs)
    def read(self, key):
        serialize = self.client.get(key)
        if serialize is not None:
            info = json.loads(serialize.decode())
            if info is not None:
                return info
        return {}

    def write(self, key, value, expire):
        self.client.set(key, json.dumps(value).encode())
        self.client.expire(key, expire)
