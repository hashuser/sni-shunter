import asyncio
import socket
import os
import sys
import json
import traceback

class core():
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        listeners = []
        servers = []
        for addr in self.config['listen']:
            try:
                if '[' in addr[:addr.rfind(':')]:
                    addr = addr.replace('[', '')
                    addr = addr.replace(']', '')
                    listeners.append(socket.create_server(address=(addr[:addr.rfind(':')], int(addr[addr.rfind(':') + 1:])),
                                             family=socket.AF_INET6, dualstack_ipv6=False))
                    listeners.append(socket.create_server(address=(addr[:addr.rfind(':')], int(addr[addr.rfind(':') + 1:])),
                                             family=socket.AF_INET6, dualstack_ipv6=True))
                else:
                    listeners.append(socket.create_server(address=(addr[:addr.rfind(':')], int(addr[addr.rfind(':') + 1:])),
                                             family=socket.AF_INET, dualstack_ipv6=False))
            except Exception:
                print("Invalid address", addr)
        for listener in listeners:
            servers.append(asyncio.start_server(client_connected_cb=self.handler, sock=listener, backlog=4096))
        self.loop.set_exception_handler(self.exception_handler)
        asyncio.gather(*servers)
        self.loop.run_forever()

    async def handler(self, client_reader, client_writer):
        try:
            print('New')
            client_hello = await client_reader.read(256)
            host = None
            port = None
            for x in self.rules:
                if b'sni' in x[:5]:
                    sni = x[x.find(b'=') + 1:]
                    if ((b'!=' in x[:5] and sni not in client_hello) or ( b'!=' not in x[:5] and sni in client_hello)) and client_writer.get_extra_info("sockname")[1] in self.rules[x][0]:
                        host = self.rules[x][1][0]
                        port = self.rules[x][1][1]
                        break
                elif b'url' in x[:5]:
                    if x.find(b'/',x.find(b'=')+8) == -1:
                        path = b'/'
                    else:
                        path = x[x.find(b'/',x.find(b'=')+8):]
                    domain = x[:x.find(b'/',x.find(b'=')+8)].replace(b'url=http://',b'')
                    if ((b'!=' in x[:5] and (path not in client_hello or domain not in domain)) or ( b'!=' not in x[:5] and (path in client_hello and domain in client_hello))) and client_writer.get_extra_info("sockname")[1] in self.rules[x][0]:
                        host = self.rules[x][1][0]
                        port = self.rules[x][1][1]
                        break
            server_reader, server_writer = await asyncio.open_connection(host=host,port=port)
            server_writer.write(client_hello)
            await server_writer.drain()
            await asyncio.gather(self.switch(client_reader, server_writer, client_writer),
                                 self.switch(server_reader, client_writer, server_writer))
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
        self.rules = dict()
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
            listen = set()
            for x in self.config:
                s_port = []
                for y in self.config[x]['listen']:
                    listen.add(y)
                    s_port.append(int(y[y.rfind(':') + 1:]))
                d_addr = self.config[x]['dst'][:self.config[x]['dst'].rfind(':')]
                d_addr = d_addr.replace('[','')
                d_addr = d_addr.replace(']', '')
                d_port = int(self.config[x]['dst'][self.config[x]['dst'].rfind(':') + 1:])
                self.rules[self.config[x]['rule'].encode('utf-8')] = (s_port,(d_addr,d_port))
            self.config['listen'] = list(listen)
        else:
            example = {'Yashmak': {'listen': [''], 'dst': '' ,'rule': ''}}
            try:
                os.makedirs(self.config_path)
            except Exception:
                pass
            with open(self.config_path + '/config.json', 'w') as file:
                json.dump(example, file, indent=4)

    def translate(self, content):
        return content.replace('\\', '/')

if __name__ == '__main__':
    server = shunter()
    server.serve_forever()