import struct
import socket
import logging
import json
import threading
from time import sleep
import select

FORMAT = '%(asctime)s - %(name)s - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger(__name__)

BUFSIZE = 4096

DATA_TYPES = {
	dict: 1,
	str: 2,
	int: 3,
	float: 4,
	'list int': 5,
	'list float': 6,
}

CHANNELS = {
	'COM': 1,
	'DAT': 2
}

CMDS = {
	'synchronize': 'SYN',
	'acknowledge': 'ACK',
	'disconnect': 'FIN',
	'start_data': 'STD',
	'stop_data': 'SPD',
}

PACK_FORMAT = '>IHH'
METADATA_LENGTH = struct.calcsize(PACK_FORMAT)

class ClientObject:
	def __init__(self, sock, addr):
		self.sock = sock
		self.addr = addr

class GSDEPException(Exception):
	pass

class GSDEPHandler:
	def __init__(self):
		pass

	def recv(self, msg, client):
		logger.debug('Received %s from %s', msg, client.addr)

	def connect(self, client):
		logger.info('%s connected', client.addr)

	def disconnect(self, client):
		logger.info('%s disconnected', client.addr)

class Shared:
	def __init__(self, sock):
		self.sock = sock

	def _send(self, sock, msg, channel=CHANNELS['COM']):
		data, data_type = self.prepare_data(msg)
		data = self.pack_data(data, data_type, channel)

		try:
			total_sent = 0
			while total_sent < len(data):
				sent = sock.send(data[total_sent:min(len(data), BUFSIZE)])
				total_sent += sent

			logger.debug('Message sent: %s', data)
			return True
		except (BrokenPipeError, ConnectionResetError):
			return None

	def _recv(self, sock):
		header = self.get_header(sock)

		if header is None:
			return None

		msg_len, data_type, channel = header[0], header[1], header[2]

		logger.debug('Message of length %d will be received.', msg_len)

		message = self._recvall(sock, msg_len)

		data = {
			'channel': channel,
			'msg': self.convert_data(message, data_type)
		}

		logger.debug('Got: %s', data['msg'])

		return data

	def _recvall(self, sock, n):
		chunks = []
		bytes_rcvd = 0

		while bytes_rcvd < n:
			try:
				chunk = sock.recv(min(n - bytes_rcvd, BUFSIZE))
			except OSError:
				logging.warning('Error receiving message, socket not connected')
				return None

			if chunk == b'':
				return None

			chunks.append(chunk)
			bytes_rcvd += len(chunk)

		return b''.join(chunks)

	def prepare_data(self, data):
		data_type = type(data)

		if data_type == str:
			data = data.encode()
		elif data_type == dict:
			data = json.dumps(data, separators=(',',':')).encode()
		elif data_type in (int, float):
			data = str(data).encode()
		elif data_type == list:
			inner_type = type(data[0])

			if inner_type == int:
				data_type = 'list int'
			elif inner_type == float:
				data_type = 'list float'

			data = data = json.dumps(data, separators=(',',':')).encode()

		return data, data_type

	def convert_data(self, data, data_type):
		if data_type == DATA_TYPES[str]:
			return data.decode()
		elif data_type == DATA_TYPES[dict]:
			return json.loads(data.decode())
		elif data_type == DATA_TYPES[int]:
			return int(data.decode())
		elif data_type == DATA_TYPES[float]:
			return float(data.decode())
		elif data_type in (DATA_TYPES['list float'], DATA_TYPES['list int']):
			return json.loads(data.decode())

		return None

	def pack_data(self, data, data_type, channel):
		return struct.pack(PACK_FORMAT, len(data), DATA_TYPES[data_type], channel) + data

	def get_header(self, sock):
		header = self._recvall(sock, METADATA_LENGTH)

		if not header:
			return None

		unpacked = struct.unpack(PACK_FORMAT, header)

		return unpacked[0], unpacked[1], unpacked[2]

class Server(Shared):
	def __init__(self, handler, ip='', port=1337, backlog=1):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.sock.bind((ip, port))
		self.sock.listen(backlog)

		self.handler = handler

		super().__init__(self.sock)

		self.clients = []

		self.running = True

		t = threading.Thread(target=self._thread_accept_clients)
		t.start()

	def _thread_accept_clients(self):
		while self.running:
			logging.info('Waiting for connection')
			(conn, addr) = self.sock.accept()
			logging.info('Got connection from %s', addr)

			c = ClientObject(conn, addr)

			if self.handshake(c):
				self.clients.append(c)

				logger.info('%s connected', addr)

				logger.info('Starting receive thread for %s', addr)
				t = threading.Thread(target=self._thread_receive, args=(c,), daemon=True)
				t.start()

				self.handler.connect(conn)
			else:
				conn.close()

	def _thread_receive(self, client):
		logger.debug('Receive thread for %s started', client.addr)
		while self.running:
			req = self.recv(client)

			if req is None:
				self.disconnect(client)
				return
			else:
				if req['msg'] in CMDS.values():
					if req['msg'] == CMDS['disconnect']:
						self.disconnect(client)
						self.send(client, CMDS['disconnect'], handshake=True)
						return

				self.handler.recv(req, client)

	def handshake(self, client):
		request = self.recv(client)

		if request is not None and request['msg'] == CMDS['synchronize']:
			logger.info('Shaking hands with %s', client.addr)

			self.send(client, CMDS['acknowledge'], handshake=True)

			response = self.recv(client)

			if response is not None and response['msg'] == CMDS['acknowledge']:
				return True
		return False

	def disconnect(self, client):
		logging.info('%s disconnected', client.addr)

		for i, o in enumerate(self.clients):
		    if o.addr == client.addr:
		        del self.clients[i]
		        break

		self.handler.disconnect(client)

	def shutdown(self):
		logger.info('Shutting down')

		self.runnning = False

		for c in self.clients:
			c.sock.close()

		self.clients = []

		self.sock.close()

	def send(self, client, msg, channel=CHANNELS['COM'], handshake=False):
		if (client in self.clients) or handshake:
			suc = self._send(client.sock, msg, channel)

			if not suc:
				self.disconnect(client)
				return
		else:
			raise GSDEPException('Client not connected!')

	def multicast(self, client_list, msg, channel=CHANNELS['COM']):
		for client in client_list:
			self.send(client, msg, channel)

	def recv(self, client):
			return self._recv(client.sock)

class Client(Shared):
	def __init__(self, ip='localhost', port=1337):
		socket.setdefaulttimeout(5)

		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.ip = ip
		self.port = port

		super().__init__(self.sock)

		self.connected = False

	def connect(self):
		logger.info('Connecting to %s on port %d', self.ip, self.port)
		self.sock.connect((self.ip, self.port))

		if self.handshake():
			logger.info('Connected')
			self.connected = True
			return True
		else:
			return False

	def handshake(self):
		logger.info('Performing handshake')

		self.send(CMDS['synchronize'])

		response = self.recv()

		if response is not None and response['msg'] == CMDS['acknowledge']:
			logger.debug('Received SYN/ACK')
			self.send(CMDS['acknowledge'])
			return True

		return False

	def send(self, msg):
		try:
			self._send(self.sock, msg, CHANNELS['COM'])
		except BrokenPipeError as e:
			logger.error('Failed to send, broken pipe', exc_info=True)

	def recv(self):
		return self._recv(self.sock)

	def close(self):
		logger.info('Closing connection')
		self.send(CMDS['stop_data'])
		self.send(CMDS['disconnect'])

		closed = False
		while not closed:
			res = self.recv()
			if res is not None and res['msg'] == CMDS['disconnect']:
				self.sock.close()
				closed = True
