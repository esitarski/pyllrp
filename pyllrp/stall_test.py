import socket, threading, time, sys, importlib
import pyllrp as L
from LLRPConnector import LLRPConnector

srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(1); port = srv.getsockname()[1]
def report(mid, epc):
	return L.RO_ACCESS_REPORT_Message(MessageID=mid, Parameters=[L.TagReportData_Parameter(Parameters=[
		L.EPC_96_Parameter(EPC=epc), L.FirstSeenTimestampUTC_Parameter(Microseconds=int(time.time()*1e6))])]).pack(L.bitstring.BitArray()).tobytes()
def reader():
	c, _ = srv.accept()
	L.READER_EVENT_NOTIFICATION_Message(MessageID=0, Parameters=[L.ReaderEventNotificationData_Parameter(Parameters=[
		L.UTCTimestamp_Parameter(Microseconds=int(time.time()*1e6)), L.ConnectionAttemptEvent_Parameter(Status=0)])]).send(c)
	time.sleep(0.2)
	r1, r2, r3 = report(1, 0x111), report(2, 0x222), report(3, 0x333)
	c.sendall(r1)
	c.sendall(r2[:13]); time.sleep(1.5)		# Stall mid-message, longer than the socket timeout.
	c.sendall(r2[13:] + r3)					# Rest of #2 and all of #3 in one write.
	time.sleep(1.0); c.close()
threading.Thread(target=reader, daemon=True).start()

epcs, errors = [], []
conn = LLRPConnector(); conn.TimeoutSecs = 0.5
conn.connect('127.0.0.1', port)
conn.addHandler(L.RO_ACCESS_REPORT_Message, lambda c, m: epcs.extend(t['EPC'] for t in m.getTagData()))
orig_listen = conn.listen
def listen():
	try: orig_listen()
	except Exception as e: errors.append(f'{type(e).__name__}: {e}')
conn.listen = listen
conn.startListener(); time.sleep(2.5); conn.keepGoing = False; conn.thread.join(3)
print(f'LLRPConnector: received EPCs {[hex(e) for e in epcs]}  listener errors: {errors or "none"}')
