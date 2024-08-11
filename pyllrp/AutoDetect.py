import socket
import threading
from queue import Queue, Empty
try:
	from .pyllrp import UnpackMessageFromSocket, ConnectionAttemptEvent_Parameter, ConnectionAttemptStatusType
except ImportError:
	from pyllrp import UnpackMessageFromSocket, ConnectionAttemptEvent_Parameter, ConnectionAttemptStatusType

def is_impinj_reader( ip, port ):
	# Connect to the socket.
	readerSocket = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
	readerSocket.settimeout( 4.0 )
	try:
		readerSocket.connect( (ip, port) )
	except Exception as e:
		return False
	
	# Get the reader's default response.
	try:
		response = UnpackMessageFromSocket( readerSocket )
	except Exception as e:
		return False
	finally:
		readerSocket.close()
		readerSocket = None
	
	# Check if the response is valid.
	try:
		connectionAttemptEvent = response.getFirstParameterByClass(ConnectionAttemptEvent_Parameter)
		return connectionAttemptEvent and connectionAttemptEvent.Status == ConnectionAttemptStatusType.Success
	except Exception as e:
		return False
	
def connection_tester(job_q, results_q, port):
	while results_q.empty():	# Quit as soon as we detect a reader.
		ip = job_q.get()
		if ip is None:
			break
		
		try:
			if is_impinj_reader(ip, port):
				results_q.put(ip)
		except Exception as e:
			pass

def get_my_ip():
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		# doesn't have to be reachable
		s.connect(('10.255.255.255', 1))
		IP = s.getsockname()[0]
	except Exception as e:
		IP = '127.0.0.1'
	finally:
		s.close()
	return IP

def check_network(pool_size=255, port=5084):
	""" Check the network for readers. """
	""" Multithread the calls for performance. """
	
	# get my IP and compose a base like 192.168.1.xxx
	ip_parts = get_my_ip().split('.')
	base_ip = ip_parts[0] + '.' + ip_parts[1] + '.' + ip_parts[2] + '.'

	# prepare the jobs queue
	jobs = Queue()
	results = Queue()
	
	pool = [threading.Thread(target=connection_tester, args=(jobs, results, port)) for i in range(pool_size)]
	for p in pool:
		p.start()

	# cue the ping processes
	my_low_order = int( ip_parts[3] )
	low_orders = sorted( (i for i in range(1,255) if i != my_low_order), key=lambda v: abs(v-my_low_order) )
	for i in low_orders:
		jobs.put('{}{}'.format(base_ip, i))
		
	for p in pool:
		jobs.put(None)

	for p in pool:
		p.join()
		
	try:
		return results.get(False)
	except Empty:
		return None

GetDefaultHost = get_my_ip
	
def findImpinjHost( impinjPort=5084 ):
	return check_network(port=impinjPort)

def AutoDetect( impinjPort=5084 ):
	return findImpinjHost(impinjPort), GetDefaultHost()
		
if __name__ == '__main__':
	print( AutoDetect() )
