import re
import socket
import subprocess
from .pyllrp import UnpackMessageFromSocket, ConnectionAttemptEvent_Parameter, ConnectionAttemptStatusType

def GetDefaultHost():
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		# doesn't have to be reachable
		s.connect(('10.255.255.255', 1))
		IP = s.getsockname()[0]
	except Exception:
		IP = '127.0.0.1'
	finally:
		s.close()
	return IP
	
def findImpinjHost( impinjPort=5084 ):
	''' Search ip addresses adjacent to the computer in an attempt to find the reader. '''
	ip = [int(i) for i in GetDefaultHost().split('.')]
	j = 0
	for i in range(14):
		j = -j if j > 0 else -j + 1
		
		ipTest = list( ip )
		ipTest[-1] += j
		if not (0 <= ipTest[-1] < 256):
			continue
			
		impinjHost = '.'.join( '{}'.format(v) for v in ipTest )
		
		readerSocket = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
		readerSocket.settimeout( 4.0 )
		try:
			readerSocket.connect( (impinjHost, impinjPort) )
		except Exception as e:
			continue
		
		try:
			response = UnpackMessageFromSocket( readerSocket )
		except Exception as e:
			readerSocket.close()
			continue
			
		readerSocket.close()
		
		# Check if the connection succeeded.
		connectionAttemptEvent = response.getFirstParameterByClass(ConnectionAttemptEvent_Parameter)
		if connectionAttemptEvent and connectionAttemptEvent.Status == ConnectionAttemptStatusType.Success:
			return impinjHost
			
	return None

def AutoDetect( impinjPort=5084 ):
	return findImpinjHost(impinjPort), GetDefaultHost()
		
if __name__ == '__main__':
	print( AutoDetect() )
