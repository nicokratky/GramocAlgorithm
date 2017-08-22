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
	"""Class used to store clients"""
	def __init__(self, sock, addr):
		self.sock = sock
		self.addr = addr


class GSDEPException(Exception):
	pass


class GSDEPHandler:
	"""Handler which can be extended from user"""
	def __init__(self):
		pass

	def recv(self, msg, client):
		logger.debug('Received %s from %s', msg, client.addr)

	def connect(self, client):
		logger.info('%s connected', client.addr)

	def disconnect(self, client):
		logger.info('%s disconnected', client.addr)


class Shared:
	"""Methods that will be shared by server and client"""

	def __init__(self, sock):
		self.sock = sock

	def _send(self, sock, msg, channel=CHANNELS['COM']):
		"""Send data to socket

		Header with meta information (Message length, data type and channel) will be generated first
		Message is sent in chunks

		returns True if message is sent successfully
		returns None if message is not sent successfully
		"""

		#Data will be encoded properly and data_type is determined
		data, data_type = self.prepare_data(msg)
		#Data is packed together with meta information
		data = self.pack_data(data, data_type, channel)

		try:
			total_sent = 0
			while total_sent < len(data):
				sent = sock.send(data[total_sent:min(len(data), BUFSIZE)])
				total_sent += sent

			logger.debug('Message sent: %s', data)
			#Message has been sent successfully
			return True
		except (BrokenPipeError, ConnectionResetError):
			#Error occured
			return None

	def _recv(self, sock):
		""" Receive data from socket

		Header will be received and unpacked first
		Then the actual data can be received and converted accordingly
		"""

		#Get meta information (Message Length, Channel and Data Type)
		header = self.get_header(sock)

		if header is None:
			return None

		msg_len, data_type, channel = header[0], header[1], header[2]

		logger.debug('Message of length %d will be received.', msg_len)

		#Actual message is received
		message = self._recvall(sock, msg_len)

		data = {
			'channel': channel,
			'msg': self.convert_data(message, data_type)
		}

		logger.debug('Got: %s', data['msg'])

		return data

	def _recvall(self, sock, n):
		"""Receive n bytes of data from socket"""

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
		"""Convert data to bytearray and return data type"""

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
		"""Convert bytearray back to right data type"""

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
		"""Pack data according to the PACK_FORMAT"""

		return struct.pack(PACK_FORMAT, len(data), DATA_TYPES[data_type], channel) + data

	def get_header(self, sock):
		"""Get meta info"""

		header = self._recvall(sock, METADATA_LENGTH)

		if not header:
			return None

		unpacked = struct.unpack(PACK_FORMAT, header)

		return unpacked[0], unpacked[1], unpacked[2]

class Server(Shared):
	def __init__(self, handler, ip='', port=1337, backlog=1):
		#Open server socket
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		#Explicitly allow to bin to a port which is in TIME_WAIT
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		#Bind to address
		self.sock.bind((ip, port))
		#Start listening
		self.sock.listen(backlog)

		#Attach handler
		self.handler = handler

		super().__init__(self.sock)

		#List of connected clients
		self.clients = []

		self.running = True

		#Start accepting clients
		t = threading.Thread(target=self._thread_accept_clients)
		t.start()

	def _thread_accept_clients(self):
		"""Wait for clients to connect

		Also performs handshake and starts receive thread for that client
		"""
		while self.running:
			logging.info('Waiting for connection')
			(conn, addr) = self.sock.accept()
			logging.info('Got connection from %s', addr)

			#Store client info in seperate object
			c = ClientObject(conn, addr)

			#Perform handshake
			if self.handshake(c):
				self.clients.append(c)

				logger.info('%s connected', addr)

				logger.info('Starting receive thread for %s', addr)
				#Start receiving messages from that client
				t = threading.Thread(target=self._thread_receive, args=(c,), daemon=True)
				t.start()

				#Notify handler that new client is connected
				self.handler.connect(conn)
			else:
				#If handshake was unsuccessfull, close connection
				conn.close()

	def _thread_receive(self, client):
		"""Receive messages from one specific client

		Receives message, handles command if it is one
		"""
		logger.debug('Receive thread for %s started', client.addr)
		while self.running:
			#Wait for message
			req = self.recv(client)

			if req is None:
				#Per definition, if message is None, socket is closed -> disconnect
				self.disconnect(client)
				return
			else:
				#If message is command, handle it
				if req['msg'] in CMDS.values():
					if req['msg'] == CMDS['disconnect']:
						self.disconnect(client)
						#Send FIN packet
						self.send(client, CMDS['disconnect'], handshake=True)
						return

				#Else, forward message to handler for further processing
				self.handler.recv(req, client)

	def handshake(self, client):
		"""Performs handshake with client"""

		#Wait for SYN packet
		request = self.recv(client)

		if request is not None and request['msg'] == CMDS['synchronize']:
			logger.info('Shaking hands with %s', client.addr)

			#Send SYN/ACK
			self.send(client, CMDS['acknowledge'], handshake=True)

			#Wait for ACK
			response = self.recv(client)

			if response is not None and response['msg'] == CMDS['acknowledge']:
				#Handshake successfull
				return True
		#Handshake unsuccessfull
		return False

	def disconnect(self, client):
		"""Disconnects client from server"""
		logging.info('%s disconnected', client.addr)

		#Delete client object from list
		for i, o in enumerate(self.clients):
		    if o.addr == client.addr:
		        del self.clients[i]
		        break

		#Notify handler about disconnected client
		self.handler.disconnect(client)

	def shutdown(self):
		"""Shuts down the server"""
		logger.info('Shutting down')

		self.runnning = False

		#Close all open connections
		for c in self.clients:
			c.sock.close()

		#Empty client list
		self.clients = []

		#Close server socket
		self.sock.close()

	def send(self, client, msg, channel=CHANNELS['COM'], handshake=False):
		"""Send message to client"""

		#Only send message if client is in connected client list or it is a handshake message (SYN, ACK, FIN)
		if (client in self.clients) or handshake:
			suc = self._send(client.sock, msg, channel)

			if not suc:
				#If sending was not successfull, disconnect that client
				self.disconnect(client)
				return
		else:
			#If client is not in connected client list, raise exception
			raise GSDEPException('Client not connected!')

	def multicast(self, client_list, msg, channel=CHANNELS['COM']):
		"""Multicast message to all clients in client_list"""
		for client in client_list:
			self.send(client, msg, channel)

	def recv(self, client):
		"""Receive message from client"""

		return self._recv(client.sock)

class Client(Shared):
	def __init__(self, ip='localhost', port=1337):
		socket.setdefaulttimeout(5)

		#Create TCP socket
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.ip = ip
		self.port = port

		super().__init__(self.sock)

		self.connected = False

	def connect(self):
		"""Connect to server and perform handshake"""

		logger.info('Connecting to %s on port %d', self.ip, self.port)
		self.sock.connect((self.ip, self.port))

		if self.handshake():
			logger.info('Connected')
			self.connected = True
			#Handshake successfull
			return True
		else:
			#Handshake unsuccessfull
			return False

	def handshake(self):
		"""Perform handshake"""

		logger.info('Performing handshake')

		#Send SYN packet
		self.send(CMDS['synchronize'])

		#Wait for SYN/ACK
		response = self.recv()

		if response is not None and response['msg'] == CMDS['acknowledge']:
			logger.debug('Received SYN/ACK')
			#Send ACK
			self.send(CMDS['acknowledge'])
			return True

		return False

	def send(self, msg):
		"""Send message to server"""

		try:
			self._send(self.sock, msg, CHANNELS['COM'])
		except BrokenPipeError as e:
			#Socket closed
			logger.error('Failed to send, broken pipe', exc_info=True)

	def recv(self):
		"""Receive message from server"""
		return self._recv(self.sock)

	def close(self):
		"""Close connection"""

		logger.info('Closing connection')
		#Send stop_data
		self.send(CMDS['stop_data'])
		#Send FIN
		self.send(CMDS['disconnect'])

		#Dont close connection until FIN is received, otherwise server could fail
		closed = False
		while not closed:
			res = self.recv()
			if res is not None and res['msg'] == CMDS['disconnect']:
				self.sock.close()
				closed = True
