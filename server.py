import asyncio
import socket
import os
import sys
import json
import traceback

class core():
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        if socket.has_dualstack_ipv6():
            listener = socket.create_server(address=('::', self.config['listen']), family=socket.AF_INET6,
                                            dualstack_ipv6=True)
        else:
            listener = socket.create_server(address=('0.0.0.0', self.config['listen']), family=socket.AF_INET,
                                            dualstack_ipv6=False)
        server = asyncio.start_server(client_connected_cb=self.handler, sock=listener, backlog=4096)
        self.loop.set_exception_handler(self.exception_handler)
        self.loop.create_task(server)
        self.loop.run_forever()

    async def handler(self, client_reader, client_writer):
        try:
            client_hello = await client_reader.read(256)
            for x in self.SNIs:
                if x in client_hello:
                    server_reader, server_writer = await asyncio.open_connection(host=self.SNIs[x][0],
                                                                                 port=self.SNIs[x][1])
                    server_writer.write(client_hello)
                    await server_writer.drain()
                    await asyncio.gather(self.switch(client_reader, server_writer, client_writer),
                                         self.switch(server_reader, client_writer, server_writer))
                    break
        except Exception as e:
            traceback.clear_frames(e.__traceback__)
            e.__traceback__ = None
            await self.clean_up(client_writer, server_writer)

    async def switch(self, reader, writer, other):
        try:
            while True:
                data = await reader.read(16384)
                writer.write(data)
                await writer.drain()
                if data == b'':
                    break
        except Exception as e:
            traceback.clear_frames(e.__traceback__)
            e.__traceback__ = None
            await self.clean_up(writer, other)
        finally:
            await self.clean_up(writer, other)
    
    async def clean_up(self, writer1=None, writer2=None):
        try:
            writer1.close()
            await writer1.wait_closed()
        except Exception as e:
            traceback.clear_frames(e.__traceback__)
            e.__traceback__ = None
        try:
            writer2.close()
            await writer2.wait_closed()
        except Exception as e:
            traceback.clear_frames(e.__traceback__)
            e.__traceback__ = None

    def exception_handler(self, loop, context):
        pass

class shunter(core):
    def __init__(self):
        self.SNIs = dict()
        self.load_config()

    def serve_forever(self):
        core.__init__(self)

    def load_config(self):
        self.config_path = os.path.abspath(os.path.dirname(sys.argv[0]))
        if os.path.exists(self.config_path + '/config.json'):
            with open(self.config_path + '/config.json', 'r') as file:
                content = file.read()
            content = self.translate(content)
            self.config = json.loads(content)
            for x in self.config['servers']:
                if self.config['servers'][x]['sni'].lower() != 'none':
                    self.SNIs[self.config['servers'][x]['sni'].encode('utf-8')] = (self.config['servers'][x]['ip'], self.config['servers'][x]['port'])
            for x in self.config['servers']:
                if self.config['servers'][x]['sni'].lower() == 'none':
                    self.SNIs[b''] = (self.config['servers'][x]['ip'], self.config['servers'][x]['port'])
            self.config['listen'] = int(self.config['listen'])
        else:
            example = {'listen': '','servers': {'Yashmak': {'sni': '', 'ip': '', 'port': ''}}}
            try:
                os.makedirs(self.config_path)
            except Exception:
                pass
            with open(self.config_path + 'config.json', 'w') as file:
                json.dump(example, file, indent=4)

    def translate(self, content):
        return content.replace('\\', '/')

if __name__ == '__main__':
    server = shunter()
    server.serve_forever()