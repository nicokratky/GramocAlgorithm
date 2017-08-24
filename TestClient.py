import sys
from GSDEP import Client, CHANNELS, CMDS
import logging
from time import sleep, time
import threading
from matplotlib import pyplot as plt

FORMAT = '%(asctime)s - %(name)s - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger(__name__)

IP = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
PORT = sys.argv[2] if len(sys.argv) > 2 else 1337

c = Client(IP, PORT)
c.connect()

c.send(CMDS['start_data'])


fig = plt.figure()

fig.canvas.set_window_title('Client')

plt.grid(True)

ax1 = fig.add_subplot(111)

num_samples_to_plot = 1000

xaxis = [i for i in range(num_samples_to_plot)]

ch1 = [0 for i in range(num_samples_to_plot)]
ch2 = [0 for i in range(num_samples_to_plot)]
ch3 = [0 for i in range(num_samples_to_plot)]
ch4 = [0 for i in range(num_samples_to_plot)]
ch5 = [0 for i in range(num_samples_to_plot)]
ch6 = [0 for i in range(num_samples_to_plot)]

line1, = ax1.plot(xaxis, ch1, linewidth=1.0, color='r')
line2, = ax1.plot(xaxis, ch2, linewidth=1.0, color='g')
line3, = ax1.plot(xaxis, ch3, linewidth=1.0, color='b')
line4, = ax1.plot(xaxis, ch4, linewidth=1.0, color='c')
line5, = ax1.plot(xaxis, ch5, linewidth=1.0, color='m')
line6, = ax1.plot(xaxis, ch6, linewidth=1.0, color='y')

ax1.set_ylim(-10, 10)

start = time()
try:
	while True:
		msg = c.recv()['msg']

		c1 = msg[0]
		c2 = msg[1]
		c3 = msg[2]
		c4 = msg[3]
		c5 = msg[4]
		c6 = msg[5]

		ch1 = (ch1 + c1)[len(c1):]
		ch2 = (ch2 + c2)[len(c2):]
		ch3 = (ch3 + c3)[len(c3):]
		ch4 = (ch4 + c4)[len(c4):]
		ch5 = (ch5 + c5)[len(c5):]
		ch6 = (ch6 + c6)[len(c6):]

		line1.set_ydata(ch1)
		line2.set_ydata(ch2)
		line3.set_ydata(ch3)
		line4.set_ydata(ch4)
		line5.set_ydata(ch5)
		line6.set_ydata(ch6)

		plt.draw()
		plt.pause(0.00001)
except:
	c.close()
