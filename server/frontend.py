import aiozmq.rpc
import asyncio
import random
import zmq

from autobahn.asyncio.websocket import WebSocketServerFactory

from rpc import BaseRpcProtocol


class RpcProtocol(BaseRpcProtocol, aiozmq.rpc.AttrHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = 1
        self.game_value = None
        self.register('count', self.count)
        self.register('ping', self.ping)
        self.register('get_user', self.get_user)
        self._client = None

    def onOpen(self):
        self._client = yield from aiozmq.rpc.connect_rpc(
            connect='tcp://127.0.0.1:5555',
            timeout=5)

        yield from aiozmq.rpc.serve_pubsub(self, subscribe='events:%s' % self._user['username'], connect='tcp://127.0.0.1:5550')

        topics = ['events', 'messages', 'other']
        i = 0
        while True:
            yield from asyncio.sleep(2)
            i += 1
            topic = random.choice(topics)
            self.publish(topic, i)
            # call RPC
            ret = yield from self._client.call.remote_func(1, i)
            print(self._user['username'], ret)

    # events handlers methods
    @aiozmq.rpc.method
    def set_value(self, value):
        self.game_value = value
        print(self._user['username'], 'set_value', self.game_value)

    # websocket RPC methods
    def count(self):
        self.value += 1
        return self.value

    @asyncio.coroutine
    def ping(self, *args):
        yield from asyncio.sleep(3)
        return args

    def get_user(self):
        return self._user


def main():
    factory = WebSocketServerFactory("ws://127.0.0.1:9000", debug=True)
    factory.protocol = RpcProtocol

    loop = asyncio.get_event_loop()
    coro = loop.create_server(factory, '0.0.0.0', 9000)
    server = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        loop.close()

if __name__ == '__main__':
    main()
