import sys
from GSDEP import Server, GSDEPHandler, CHANNELS, CMDS
from time import sleep, time
import random
import logging
import threading
import struct
import socket
from matplotlib import pyplot as plt

FORMAT = '%(asctime)s - %(name)s - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
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

		num_samples_to_plot = 1000
		self.xaxis = [i for i in range(num_samples_to_plot)]
		self.ch1 = [0 for i in range(num_samples_to_plot)]
		self.ch2 = [0 for i in range(num_samples_to_plot)]
		self.ch3 = [0 for i in range(num_samples_to_plot)]
		self.ch4 = [0 for i in range(num_samples_to_plot)]
		self.ch5 = [0 for i in range(num_samples_to_plot)]
		self.ch6 = [0 for i in range(num_samples_to_plot)]

	def connect(self, client):
		pass

	def disconnect(self, client):
		pass

	def recv(self, msg, client):
		"""Handle received data

		Checks if received message is a command
		If no command -> print message
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
		"""Start threads for sending data to user"""

		# start thread that sens messages to the ADC board
		self.t_keepalive.start()
		#start thread that read data from the ADC board and sends it to requesting clients
		self.t_send_sensor_data.start()

	def keepalive(self):
		"""continuously sends OK to UDP so that it wont shut down"""

		while self.server.running:
			message = 'OK'
			self.sensor.sendto(message.encode('utf-8'), self.sensor_addr)
			sleep(1)

	def send_sensor_data(self):
		"""Read data from ADC board and send it to requesting clients"""

		logging.info('Started sensor data thread')
		current_milli_time = lambda: int(round(time() * 1000))

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

				self.ch1 = (self.ch1 + c1)[len(c1):]
				self.ch2 = (self.ch2 + c2)[len(c1):]
				self.ch3 = (self.ch3 + c3)[len(c1):]
				self.ch4 = (self.ch4 + c4)[len(c1):]
				self.ch5 = (self.ch5 + c5)[len(c1):]
				self.ch6 = (self.ch6 + c6)[len(c1):]

				#if requesting is not empty, send data
				if self.requesting:
					self.server.multicast(self.requesting, [c1, c2, c3, c4, c5, c6])

			except:
				sleep(0.1)

	def plot_data(self):
		fig = plt.figure()
		fig.canvas.set_window_title('Server')

		plt.grid(True)

		ax1 = fig.add_subplot(111)

		line1, = ax1.plot(self.xaxis, self.ch1, linewidth=1.0, color='r')
		line2, = ax1.plot(self.xaxis, self.ch2, linewidth=1.0, color='g')
		line3, = ax1.plot(self.xaxis, self.ch3, linewidth=1.0, color='b')
		line4, = ax1.plot(self.xaxis, self.ch4, linewidth=1.0, color='c')
		line5, = ax1.plot(self.xaxis, self.ch5, linewidth=1.0, color='m')
		line6, = ax1.plot(self.xaxis, self.ch6, linewidth=1.0, color='y')

		ax1.set_ylim(-10, 10)

		while self.server.running:
			line1.set_ydata(self.ch1)
			line2.set_ydata(self.ch2)
			line3.set_ydata(self.ch3)
			line4.set_ydata(self.ch4)
			line5.set_ydata(self.ch5)
			line6.set_ydata(self.ch6)

			plt.draw()
			plt.pause(0.000001)

try:
	sensor = SensorHandler()
	sensor.start()
	sensor.plot_data()
except KeyboardInterrupt:
	sensor.server.shutdown()

