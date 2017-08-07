import GSDEP
from time import sleep

c = GSDEP.Client('localhost', 1337)
c.connect()

for i in range(100):
	c.send({str(i): i})
	sleep(0.1)

c.close()
