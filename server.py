import asyncio
import socket
import os
import sys
import json
import traceback
import multiprocessing
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
class worker():
    def __init__(self, listener, rules):
        port = listener.getsockname()[1]
        self.rules = dict()
        for x in rules.keys():
            if port in rules[x][0]:
                self.rules[x] = rules[x]
        self.loop = asyncio.get_event_loop()
        server = asyncio.start_server(client_connected_cb=self.handler, sock=listener, backlog=4096)
        self.loop.set_exception_handler(self.exception_handler)
        self.loop.create_task(server)
        self.loop.run_forever()

    async def handler(self, client_reader, client_writer):
        try:
            server_writer = None
            client_hello = await asyncio.wait_for(client_reader.read(256),20)
            if client_hello == b'':
                raise Exception
            instruction = client_hello[:4]
            if b'GET' in instruction or b'POST' in instruction:
                is_tls = False
            else:
                is_tls = True
            host = None
            port = None
            for x in self.rules:
                key_word = x[:5].lower()
                if is_tls and b'sni' in key_word:
                    sni = x[4:].lower()
                    if sni == b'none':
                        host = self.rules[x][1][0]
                        port = self.rules[x][1][1]
                    if sni in client_hello:
                        host = self.rules[x][1][0]
                        port = self.rules[x][1][1]
                        break
                elif not is_tls and b'url' in key_word:
                    url = x[4:]
                    if url.lower() == b'none':
                        host = self.rules[x][1][0]
                        port = self.rules[x][1][1]
                    domain = url.replace(b'http://',b'',1)
                    position = domain.find(b'/')
                    if position == -1:
                        path = b'/'
                    else:
                        path = domain[position:]
                        domain = domain[:position]
                    if domain in client_hello and (position == -1 or path in client_hello):
                        host = self.rules[x][1][0]
                        port = self.rules[x][1][1]
                        break
            if host == None or port == None:
                raise Exception
            server_reader, server_writer = await asyncio.wait_for(asyncio.open_connection(host=host, port=port),5)
            server_writer.write(client_hello)
            await server_writer.drain()
            await asyncio.gather(self.switch(client_reader, server_writer, client_writer),
                                 self.switch(server_reader, client_writer, server_writer))
        except Exception as error:
            traceback.clear_frames(error.__traceback__)
            error.__traceback__ = None
            await self.clean_up(client_writer, server_writer)

    async def switch(self, reader, writer, other):
        try:
            while 1:
                data = await reader.read(32768)
                if data == b'':
                    raise Exception
                writer.write(data)
                await writer.drain()
        except Exception as error:
            traceback.clear_frames(error.__traceback__)
            error.__traceback__ = None
            await self.clean_up(writer, other)

    async def clean_up(self, writer1=None, writer2=None):
        try:
            if writer1 != None:
                writer1.close()
        except Exception as error:
            traceback.clear_frames(error.__traceback__)
            error.__traceback__ = None
        try:
            if writer2 != None:
                writer2.close()
        except Exception as error:
            traceback.clear_frames(error.__traceback__)
            error.__traceback__ = None
        try:
            if writer1 != None:
                await writer1.wait_closed()
                writer1 = None
        except Exception as error:
            traceback.clear_frames(error.__traceback__)
            error.__traceback__ = None
        try:
            if writer2 != None:
                await writer2.wait_closed()
                writer2 = None
        except Exception as error:
            traceback.clear_frames(error.__traceback__)
            error.__traceback__ = None

    def exception_handler(self, loop, context):
        pass

class core():
    def __init__(self):
        listeners = []
        for addr in self.config['listen']:
            try:
                if '[' in addr[:addr.rfind(':')]:
                    addr = addr.replace('[', '')
                    addr = addr.replace(']', '')
                    listeners.append(socket.create_server(address=(addr[:addr.rfind(':')], int(addr[addr.rfind(':') + 1:])),
                                             family=socket.AF_INET6, reuse_port=True, dualstack_ipv6=True))
                else:
                    listeners.append(socket.create_server(address=(addr[:addr.rfind(':')], int(addr[addr.rfind(':') + 1:])),
                                             family=socket.AF_INET, reuse_port=True, dualstack_ipv6=False))
            except Exception:
                print("Invalid address", addr)
        process_pool = []
        for listener in listeners:
            for x in range(os.cpu_count()):
                P = multiprocessing.Process(target=worker, args=(listener, self.rules,))
                P.start()
                process_pool.append(P)
        for x in process_pool:
            x.join()

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
                d_addr = d_addr.replace('[', '')
                d_addr = d_addr.replace(']', '')
                d_port = int(self.config[x]['dst'][self.config[x]['dst'].rfind(':') + 1:])
                self.rules[self.config[x]['rule'].encode('utf-8')] = (s_port, (d_addr, d_port))
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