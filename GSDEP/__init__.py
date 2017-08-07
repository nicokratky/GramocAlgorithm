import struct
import socket
import logging
import coloredlogs
import json
from time import sleep

logger = logging.getLogger(__name__)

coloredlogs.install(level='DEBUG', logger=logger)

BUFSIZE = 4096

DATA_TYPES = {
	dict: 1,
	str: 2,
	int: 3,
	float: 4
}

CHANNELS = {
	'COM': 1,
	'DAT': 2
}

CMDS = ['CNCT', 'DISCNCT']

PACK_FORMAT = '>IBB'
METADATA_LENGTH = struct.calcsize(PACK_FORMAT)

def _send(sock, msg, channel=CHANNELS['COM']):
	data, data_type = prepare_data(msg)
	data = pack_data(data, data_type, channel)

	total_sent = 0
	while total_sent < len(data):
		sent = sock.send(data[total_sent:])
		total_sent += sent

	logger.debug('Message sent: %s', data)

def _recv(sock):
	header = get_header(sock)

	if header is None:
		return None

	msglen, data_type, channel = header[0], header[1], header[2]

	logger.debug('Message of length %d will be received.', msglen)

	message = _recvall(sock, msglen)

	data = {
		'channel': channel,
		'msg': convert_data(message, data_type)
	}

	return data

def _recvall(sock, n):
	chunks = []
	bytes_rcvd = 0

	while bytes_rcvd < n:
		chunk = sock.recv(min(n - bytes_rcvd, 2048))

		if chunk == b'':
			return None

		chunks.append(chunk)
		bytes_rcvd += len(chunk)

	return b''.join(chunks)

def prepare_data(data):
	data_type = type(data)

	if data_type == str:
		data = data.encode()
	elif data_type in (dict, list):
		data = json.dumps(data, separators=(',',':')).encode()
	elif data_type in (int, float):
		data = str(data).encode()

	return data, data_type

def convert_data(data, data_type):
	if data_type == DATA_TYPES[str]:
		return data.decode()
	elif data_type == DATA_TYPES[dict]:
		return json.loads(data.decode())
	elif data_type == DATA_TYPES[int]:
		return int(data.decode())
	elif data_type == DATA_TYPES[float]:
		return float(data.decode())

	return None

def pack_data(data, data_type, channel):
	return struct.pack(PACK_FORMAT, len(data), DATA_TYPES[data_type], channel) + data

def get_header(sock):
	header = _recvall(sock, METADATA_LENGTH)

	if not header:
		return None

	unpacked = struct.unpack(PACK_FORMAT, header)

	return unpacked[0], unpacked[1], unpacked[2]

class Server:
	def __init__(self, ip, port):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		self.sock.bind((ip, port))

		self.running = False

		self.client_connected = False
		self.connection = None
		self.client_address = None

	def start(self):
		self.running = True
		self.sock.listen(1)
		self.wait_for_handshake()

	def shutdown(self):
		logger.info('Shutting down')
		self.running = False
		self.sock.close()

	def send(self, msg, channel=CHANNELS['COM']):
		if self.client_connected:
			_send(self.connection, msg, channel)

	def recv(self):
		"""Receive message from Client
		Only for communication purposes
		No Data is sent to the server
		"""

		return _recv(self.connection)

	def wait_for_handshake(self):
		logger.info('Waiting for connection')
		self.connection, self.client_address = self.sock.accept()
		logger.info('Got connection from %s', self.client_address)

		while 1:
			data = self.recv()

			if(data['channel'] == CHANNELS['COM'] and data['msg'] == 'CNCT'):
				logger.info('Shaking hands...')
				self.client_connected = True
				self.send('CNCT')
				break
			else:
				sleep(0.1)

		self.run()


	def run(self):
		self.running = True
		while self.running and self.client_connected:
			self.handle_request()

	def handle_request(self):
		request = self.recv()

		if request['msg'] in CMDS:
			if request['msg'] == 'DISCNCT':
				logger.info('Received DISCNCT from %s', self.client_address)
				self.client_connected = False
				self.running = False
				self.wait_for_handshake()
		else:
			logger.debug('Handle request: ' + json.dumps(request))



class Client:
	def __init__(self, ip, port):
		socket.setdefaulttimeout(5)

		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		self.server_address = (ip, port)

	def connect(self):
		logger.info('Connecting to %s', self.server_address)
		self.sock.connect(self.server_address)
		logger.info('Connected to server.')

		logger.info('Shaking hands...')
		while True:
			self.send('CNCT')

			data = self.recv()
			if data is None:
				continue

			if(data['channel'] == CHANNELS['COM'] and data['msg'] == 'CNCT'):
				break
			else:
				sleep(0.1)

	def send(self, msg):
		try:
			_send(self.sock, msg, CHANNELS['COM'])
		except BrokenPipeError as e:
			logger.error('Failed to send, broken pipe', exc_info=True)

	def recv(self):
		return _recv(self.sock)

	def close(self):
		logger.info('Closing connection')
		self.send('DISCNCT')
		self.sock.close()