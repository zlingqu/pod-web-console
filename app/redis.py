
import redis
import json

class RedisResource(object):
    def __init__(self, host, port, db, expire=None, key_prefix='', *args, **kwargs):
        if not hasattr(RedisResource, 'pool'):
            RedisResource.getRedisCoon(host, port, db, *args, **kwargs)
        self.client = redis.StrictRedis(connection_pool=RedisResource.pool)
        self.key_prefix = key_prefix
        self.expire = expire

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
