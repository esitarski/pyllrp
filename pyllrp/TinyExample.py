#!/usr/bin/env python
import sys
import time

try:
	from . import pyllrp
	from .AutoDetect import AutoDetect
	from .LLRPConnector import LLRPConnector
	from .TagInventory import TagInventory
except Exception as e:
	import pyllrp
	from AutoDetect import AutoDetect
	from LLRPConnector import LLRPConnector
	from TagInventory import TagInventory

#-----------------------------------------------------------------------------------------

def CustomExtensionTest( reader ):
	'''
		Test Impinj custom message.
	'''
	with LLRPConnector() as conn:
		conn.connect( reader )
		
		message = IMPINJ_ENABLE_EXTENSIONS_Message( MessageID = 0xeded )
		response = conn.transact( message )
		if not response.success():
			print( 'This reader does not support Impinj extensions.' )
			return
			
		message = GET_READER_CONFIG_Message( MessageID = 0xededed, RequestedData = GetReaderConfigRequestedData.All )
		response = conn.transact( message )
		if not response.success():
			print( 'GET_READER_CONFIG_Message fails.' )
			return
					
		print( response )	
		p = response.getFirstParameterByClass( ImpinjReaderTemperature_Parameter )
		if p:
			print( 'Reader Temperature =', p.Temperature )
		else:
			print( 'This reader supports Impinj extensions but did not return a Reader Temperature.' )
	
def TinyExampleTest( conn ):
	'''
		Create an rospec that reports every read as soon as it happens.
	'''
	rospecID = 123					# Arbitrary rospecID.
	inventoryParameterSpecID = 1234	# Arbitrary inventory parameter spec id.

	response = conn.transact(
		ADD_ROSPEC_Message( Parameters = [
			ROSpec_Parameter(
				ROSpecID = rospecID,
				CurrentState = ROSpecState.Disabled,
				Parameters = [
					ROBoundarySpec_Parameter(		# Configure boundary spec (start and stop triggers for the reader).
						Parameters = [
							ROSpecStartTrigger_Parameter(ROSpecStartTriggerType = ROSpecStartTriggerType.Immediate),
							ROSpecStopTrigger_Parameter(ROSpecStopTriggerType = ROSpecStopTriggerType.Null),
						]
					), # ROBoundarySpec
					AISpec_Parameter(				# Antenna Inventory Spec (specifies which antennas and protocol to use)
						AntennaIDs = [0],			# Use all antennas.
						Parameters = [
							AISpecStopTrigger_Parameter( AISpecStopTriggerType = AISpecStopTriggerType.Null ),
							InventoryParameterSpec_Parameter(
								InventoryParameterSpecID = inventoryParameterSpecID,
								ProtocolID = AirProtocols.EPCGlobalClass1Gen2,
							),
						]
					), # AISpec
					ROReportSpec_Parameter(			# Report spec (specified how often and what to send from the reader)
						ROReportTrigger = ROReportTriggerType.Upon_N_Tags_Or_End_Of_ROSpec,
						N = 1,						# N = 1 --> update on each read.
						Parameters = [
							TagReportContentSelector_Parameter(
								EnableAntennaID = True,
								EnableFirstSeenTimestamp = True,
							),
						]
					), # ROReportSpec
				]
			), # ROSpec_Parameter
		])	# ADD_ROSPEC_Message
	)
	assert response.success()

	# And enable it...
	response = conn.transact( ENABLE_ROSPEC_Message(ROSpecID = rospecID) )
	assert response.success()

	# Start thread to listen to the reader for a while.
	print( 'Listen to the connection for a few seconds...\n' )
	conn.startListener()
	time.sleep( 2 )			# Wait for some reads (we could be doing something else here too).
	conn.stopListener()

	print( 'Shutting down the connection...\n' )
	response = conn.disconnect()
	print( response )

if __name__ == '__main__':
	print( 'AutoDetecting reader...' )
	reader, computer_ip = AutoDetect()
	#reader = '192.168.0.100'
	if not reader:
		print( 'No reader detected.' )
		sys.exit( -1 )
	print( 'found reader at', reader )
	
	# Test custom extensions.
	CustomExtensionTest( reader )
	
	# Read a tag inventory from a reader and shutdown.
	ti = TagInventory( reader )
	ti.Connect()
	
	tagInventory = ti.GetTagInventory()
	for t in tagInventory:
		print( t )
	ti.Disconnect()
	
	# Check that we can connect at different power levels.
	for p in [1,5,10,20,30,40,50,60,70,80]:
		print( 'Connecting at transmitPower={}'.format(p) )
		ti = TagInventory( reader, transmitPower = p )
		ti.Connect()
		tagInventory = ti.GetTagInventory()
		for t in tagInventory:
			print( t )
		ti.Disconnect()
