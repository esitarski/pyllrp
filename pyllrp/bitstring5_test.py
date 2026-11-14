"""Extra round-trip tests for pyllrp under bitstring 5.0, covering the paths the built-in __main__ tests skip."""
import socket
import threading
import bitstring
import pyllrp as L

passed = failed = 0
def check(name, cond, detail=''):
	global passed, failed
	if cond:
		passed += 1
		print(f'PASS  {name}')
	else:
		failed += 1
		print(f'FAIL  {name}  {detail}')

def roundtrip(m):
	s = m.pack(bitstring.BitArray())
	return s, L.UnpackMessage(bitstring.Reader(s))

# 1. bits:2 fields (Session, MB, T) round-trip as ints and re-pack identically.
m = L.SET_READER_CONFIG_Message(MessageID=10, Parameters=[
	L.AntennaConfiguration_Parameter(AntennaID=1, Parameters=[
		L.RFTransmitter_Parameter(HopTableID=1, ChannelIndex=1, TransmitPower=81),
		L.C1G2InventoryCommand_Parameter(Parameters=[
			L.C1G2Filter_Parameter(T=L.C1G2TruncateAction.Truncate, Parameters=[
				L.C1G2TagInventoryMask_Parameter(MB=3, Pointer=32, TagMask=b'\xde\xad'),
			]),
			L.C1G2SingulationControl_Parameter(Session=2, TagPopulation=100, TagTransitTime=3000),
		]),
	]),
])
s1, u = roundtrip(m)
sc = u.getFirstParameterByClass(L.C1G2SingulationControl_Parameter)
flt = u.getFirstParameterByClass(L.C1G2Filter_Parameter)
mask = u.getFirstParameterByClass(L.C1G2TagInventoryMask_Parameter)
check('bits:2 Session reads back as int 2', sc.Session == 2 and type(sc.Session) is int, repr(sc.Session))
check('bits:2 T reads back as enum int', flt.T == L.C1G2TruncateAction.Truncate, repr(flt.T))
check('bits:2 MB=3 + bitarray TagMask', mask.MB == 3 and mask.TagMask == b'\xde\xad', f'{mask.MB!r} {mask.TagMask!r}')
check('unpacked message re-packs byte-identical', u.pack(bitstring.BitArray()).tobytes() == s1.tobytes())

# 2. RO_ACCESS_REPORT with EPC_96 (uintbe:96), EPCData (bitarray), negative PeakRSSI (intbe:8).
epc96 = 0x3008_33B2_DDD9_0140_0000_0001
rpt = L.RO_ACCESS_REPORT_Message(MessageID=11, Parameters=[
	L.TagReportData_Parameter(Parameters=[
		L.EPC_96_Parameter(EPC=epc96),
		L.AntennaID_Parameter(AntennaID=2),
		L.PeakRSSI_Parameter(PeakRSSI=-62),
		L.FirstSeenTimestampUTC_Parameter(Microseconds=1_700_000_000_000_000),
		L.TagSeenCount_Parameter(TagCount=5),
	]),
	L.TagReportData_Parameter(Parameters=[
		L.EPCData_Parameter(EPC=bytes.fromhex('E2801160600002')),
	]),
])
_, u = roundtrip(rpt)
td = u.getTagData()
check('EPC_96 uintbe:96 round-trip', td[0]['EPC'] == epc96, repr(td[0].get('EPC')))
check('PeakRSSI intbe:8 negative', td[0]['PeakRSSI'] == -62, repr(td[0].get('PeakRSSI')))
check('timestamp / antenna / count', (td[0]['Timestamp'], td[0]['AntennaID'], td[0]['TagSeenCount']) == (1_700_000_000_000_000, 2, 5))
check('EPCData bitarray round-trip', td[1]['EPC'] == bytes.fromhex('E2801160600002'), repr(td[1].get('EPC')))

# 3. Strings, arrays, skip fields, custom parameters with strings.
gc = L.GET_READER_CONFIG_RESPONSE_Message(MessageID=12, Parameters=[
	L.LLRPStatus_Parameter(StatusCode=L.StatusCode.M_Success, ErrorDescription='ok ✓'),
	L.Identification_Parameter(IDType=L.IdentificationType.MAC_Address, ReaderID=[0, 22, 37, 1, 2, 3]),
	L.ImpinjDetailedVersion_Parameter(ModelName='R420', SerialNumber='370-17-01-0001', SoftwareVersion='7.6', FirmwareVersion='', FPGAVersion='x', PCBAVersion='y'),
])
_, u = roundtrip(gc)
check('success() on response', u.success())
check('UTF-8 string round-trip', u.getFirstParameterByClass(L.LLRPStatus_Parameter).ErrorDescription == 'ok ✓')
check('array:8 round-trip', u.getFirstParameterByClass(L.Identification_Parameter).ReaderID == [0, 22, 37, 1, 2, 3])
dv = u.getFirstParameterByClass(L.ImpinjDetailedVersion_Parameter)
check('custom parameter strings', (dv.ModelName, dv.SerialNumber, dv.FirmwareVersion) == ('R420', '370-17-01-0001', ''))

# 4. Unknown custom parameter is skipped (bytes:N read path).
cfg = L.GET_READER_CONFIG_RESPONSE_Message(MessageID=13, Parameters=[L.LLRPStatus_Parameter(StatusCode=0)])
raw = cfg.pack(bitstring.BitArray())
unknown = bitstring.pack('uintbe:16, uintbe:16, uintbe:32, uintbe:32, bytes', 1023, 4+4+4+3, 99999, 7, b'abc')
raw.append(unknown)
raw.overwrite(16, bitstring.pack('uintbe:32', len(raw) // 8))
u = L.UnpackMessage(bitstring.Reader(raw))
check('unknown custom parameter skipped', len(u.Parameters) == 2 and type(u.Parameters[1]) is L.Custom_Parameter)

# 5. Socket path: send(), UnpackMessageFromSocket() and WaitForMessage(), with byte-at-a-time delivery.
a, b = socket.socketpair()
L.KEEPALIVE_Message(MessageID=500).send(a)
rpt.send(a)
nonmatching = []
got = L.WaitForMessage(11, b, nonmatching.append)
check('send + UnpackMessageFromSocket + WaitForMessage', got.MessageID == 11 and isinstance(nonmatching[0], L.KEEPALIVE_Message))

data = gc.pack(bitstring.BitArray()).tobytes()
def drip():
	for i in range(len(data)):
		a.sendall(data[i:i+1])
t = threading.Thread(target=drip); t.start()
got = L.UnpackMessageFromSocket(b); t.join()
check('UnpackMessageFromSocket with fragmented recv', got.MessageID == 12 and got.success())
a.close(); b.close()

# 6. The except clause in _FieldDef.write now catches bitstring 5's ValueError (and re-raises).
fd = L._FieldDef('X', 'uintbe:16')
class Obj: X = 70000
try:
	fd.write(bitstring.BitArray(), Obj())
	check('write out-of-range raises ValueError', False, 'no exception')
except ValueError:
	check('write out-of-range raises ValueError', True)

# 7. bitarray write from int now produces real bytes.
class Obj2: X = 0xABCD
s = bitstring.BitArray(); L._FieldDef('X', 'bitarray').write(s, Obj2())
check('bitarray write from int', s.tobytes() == b'\x00\x10\xab\xcd', s.hex)

print(f'\n{passed} passed, {failed} failed')
raise SystemExit(1 if failed else 0)
