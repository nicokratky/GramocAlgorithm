import sys
from GSDEP import Server, GSDEPHandler, CHANNELS, CMDS
from time import sleep
import random
import logging
import threading
import struct
import socket

FORMAT = '%(asctime)s - %(name)s - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
logger = logging.getLogger(__name__)

IP = sys.argv[1] if len(sys.argv) > 1 else ''
PORT = int(sys.argv[2] if len(sys.argv) > 2 else 1337)

class SensorHandler(GSDEPHandler):
	def __init__(self):
		super().__init__()

		#server which distributes data to clients
		self.server = Server(self, IP, PORT)

		#create socket for connecting to the UDP server on the ADC board
		self.sensor = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sensor.settimeout(1)

		#IP-address of the ADC board
		self.sensor_addr = ('192.168.101.81', 9760)

		#send hello message
		self.sensor.sendto('Hello UDP server'.encode('utf-8'), self.sensor_addr)

		#receive initial data
		print(self.sensor.recvfrom(100)[0].decode())

		#list of clients that request sensor data
		self.requesting = []

		#creat thread for sending messages to the ADC board
		self.t_keepalive = threading.Thread(target=self.keepalive)
		#create thread for sending data from the ADC board to requesting clients
		self.t_send_sensor_data = threading.Thread(target=self.send_sensor_data)

	def connect(self, client):
		pass

	def disconnect(self, client):
		pass

	def recv(self, msg, client):
		"""
		Handle received data
		"""

		payload = msg['msg']

		if payload in CMDS.values():
			if payload == CMDS['start_data']:
				#append client to requesting if start_data command is received
				if client not in self.requesting:
					self.requesting.append(client)
					logging.debug('Added %s to requesting', client.addr)
			if payload == CMDS['stop_data']:
				#remove client from requesting if stop_data command is received
				if client in self.requesting:
					logging.debug('Removed %s from requesting', client.addr)
					self.requesting.remove(client)
		else:
			print(payload)

	def start(self):
		# start thread that sens messages to the ADC board
		self.t_keepalive.start()
		#start thread that read data from the ADC board and sends it to requesting clients
		self.t_send_sensor_data.start()

	def keepalive(self):
		#continuously send OK to UDP so that it wont shut down
		while self.server.running:
			message = 'OK'
			self.sensor.sendto(message.encode('utf-8'), self.sensor_addr)
			sleep(1)

	def send_sensor_data(self):
		logging.info('Started sensor data thread')

		while self.server.running:
			#retry receiving when connection to temporarly lost (i.e. board has been unplugged temporarly)
			try:
				#receive data from the UDP socket
				data = self.sensor.recvfrom(4096)

				#convert the received bytearray to a tuple of shorts
				#There are 600 samples in a packet (100 samples per channel)
				adc_data = struct.unpack('600h', data[0])

				#separate data for each channel
				c1 = list(adc_data[::6])
				c2 = list(adc_data[1::6])
				c3 = list(adc_data[2::6])
				c4 = list(adc_data[3::6])
				c5 = list(adc_data[4::6])
				c6 = list(adc_data[5::6])

				#convert ADC values to volts
				c1 = [i*(10/32767) for i in c1]
				c2 = [i*(10/32767) for i in c2]
				c3 = [i*(10/32767) for i in c3]
				c4 = [i*(10/32767) for i in c4]
				c5 = [i*(10/32767) for i in c5]
				c6 = [i*(10/32767) for i in c6]

				#if requesting is not empty, send data
				if self.requesting:
					self.server.multicast(self.requesting, c1)

			except:
				sleep(0.1)

try:
	sensor = SensorHandler()
	sensor.start()
except KeyboardInterrupt:
	sensor.server.shutdown()

