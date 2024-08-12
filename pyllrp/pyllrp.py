import io
import codecs
import itertools
import bitstring
try:
	from . import llrpdef
except Exception:
	import llrpdef
llrpdef.choiceDefinitions = { k + '_Parameter' : v + '_Parameter' for k, v in llrpdef.choiceDefinitions.items() }

#----------------------------------------------------------------------------------
# Python support for LLRP (Low Level Reader Protocol).
# Includes all Impinj extensions.
#
# Edward Sitarski, 2013 (edward.sitarski@gmail.com)
#
# The idea is to parse the LLRP definitions in XML and translate them into a python-friendly form.
# Then read the compiled form and dynamically generate Python classes, supporting all LLRP messages, parameters
# and the full Impinj extension
# For examples, see TagInventory.py and TagWriter.py.
#
# The advantage of parsing the XML is that there is a lot to the LLRP specification there.
# pyllrp enforces all protocol constraints, including parameter ordering and values.
#
# Missing fields are allowed.
# All integer fields are initialized to zero, all boolean fields are initialized to False, all strings to empty.
#
# The PackUnpack classes handle the variable number of Parameters in Messages, in Parameters,
# and Parameters nested in Parameters.
#
# Classes for the Messages and Parameters are created dynamically in _MakeClass from field specs.
# The "__slots__" feature is used to limit the available fields in each Message and Parameter.
# This prevents assignment to non-existent fields by mistake.
#
# A Message class looks as follows if it were declared in Python:
#
# class MESSAGE_Message:
#	def __init__( self, <fields specific to message> )
#		# Any fields not specified take default values.
#		pass
#
#	def __repr__( self )
#		''' Print out the message and all its nested structure. '''
#		pass
#
#	def send( self, socket ):
#		''' Send this object, in LLRP binary, to a socket.
#		pass
#

CustomTypeCode = 1023

class _FieldDef:
	__slots__ = ['Name', 'TypeCode', 'Enum', 'Format', 'Default']
	
	def __init__( self, Name, TypeCode, Enum = None, Format = None, Default = None ):
		self.Name = Name
		self.TypeCode = TypeCode
		if Enum:
			self.Enum = globals()[Enum]
		else:
			self.Enum = None
		self.Format = Format
		self.Default = Default
		
	def read( self, s, obj, bytesRemaining = None ):
		ftype = self.TypeCode
		attr = self.Name
		if 'intbe' in ftype or ftype == 'bool' or ftype.startswith('bits'):
			setattr( obj, attr, s.read(ftype) )
		elif ftype == 'string':
			length = s.read( 'uintbe:16' )
			eftype = f'bytes:{length}'
			st = s.read( eftype )
			setattr( obj, attr, st.decode().rstrip('\x00') )		# Decode utf-8
		elif ftype.startswith('array'):
			length = s.read( 'uintbe:16' )
			eftype = 'uintbe:{}'.format(ftype.split(':')[1])
			arr = [s.read(eftype) for i in range(length)]
			setattr( obj, attr, arr )
		elif ftype == 'bitarray':
			length = s.read( 'uintbe:16' )
			eftype = f'bits:{length}'
			bstr = s.read( eftype )
			setattr( obj, attr, bstr.tobytes() )
		elif ftype.startswith('skip'):
			skip = int(ftype.split(':',1)[1])
			s.read( f'int:{skip}' )
		elif ftype == 'bytesToEnd':
			assert bytesRemaining is not None, 'bytesToEnd type requires bytesRemaining to be set'
			by = s.read( f'bytes:{bytesRemaining}' )		# Read as bytes.
			setattr( obj, attr, bitstring.BitStream(bytes=by) )		# Set attr to a bitstream.
		else:
			assert False, f'Unknown FieldDef type: "{ftype}"'

	def write( self, s, obj ):
		''' Write the field from the obj to the bitstring. '''
		ftype = self.TypeCode
		attr = self.Name
		try:
			if 'intbe' in ftype or ftype == 'bool':
				s.append( bitstring.pack(ftype, getattr(obj, attr)) )
			elif ftype.startswith('bits'):
				v = getattr( obj, attr )
				length = int(ftype.split(':')[1])
				for i in range(length-1, -1, -1):
					s.append( bitstring.pack('bool', bool(v & (1<<i))) )
			elif ftype == 'string':
				by = getattr(obj, attr, '').encode()	# Encode utf-8.
				s.append( bitstring.Bits(uintbe=len(by), length=16) )
				s.append( bitstring.Bits(bytes=by) )
			elif ftype.startswith('array'):
				arr = getattr( obj, attr, [] )
				length = int(ftype.split(':')[1])
				s.append( bitstring.Bits(uintbe=len(arr), length=16) )
				for e in arr:
					s.append( bitstring.Bits(uintbe=e, length=length) )
			elif ftype == 'bitarray':
				by = getattr(obj, attr, b'')	# Expects bytes.
				if isinstance(by, int):
					# Convert int to bytes.
					assert by > 0, 'bitarray cannot be initialized with negative integer'
					v = f'{by:x}'			# Convert to hex.
					if len(v) & 1:			# Ensure hex number has an even number of hex chars.
						v = '0' + v
					by = codecs.encode( v, 'hex_codec' )	# Encode to bytes as hex.
				s.append( bitstring.Bits(uintbe=len(by)*8, length=16) )
				s.append( bitstring.Bits(bytes=by) )
			elif ftype.startswith('skip'):
				skip = int(ftype.split(':',1)[1])
				assert skip > 0
				s.append( bitstring.pack(f'int:{skip}=0') )
			elif ftype == 'bytesToEnd':
				s.append( getattr(obj, attr) )		# assume the field is a bitstream
			else:
				assert False
		except bitstring.CreationError as e:
			print( f'write: {ftype} {attr} {getattr(obj, attr)}' )
			raise

	def init( self, obj ):
		''' Initialize a field value based on its ftype. '''
		ftype = self.TypeCode
		attr = self.Name
		if 'intbe' in ftype or ftype.startswith('bits'):
			setattr( obj, attr, self.Default if self.Default else 0 )
		elif ftype == 'bool':
			setattr( obj, attr, False )
		elif ftype == 'string':
			setattr( obj, attr, '' )
		elif ftype.startswith('array'):
			setattr( obj, attr, [] )
		elif ftype == 'bitarray':
			setattr( obj, attr, bytes() )
		elif ftype == 'bytesToEnd':
			assert False
			setattr( obj, attr, bitstring.BitStream() )
		else:
			assert ftype.startswith('skip'), f'Unknown field type: "{ftype}"'
			
	def __repr__( self ):
		return f'FieldDef( "{self.Name}", "{self.TypeCode}" )'

#----------------------------------------------------------------------------------

class _EnumDef:
	''' A small class for llrp enumerated values. '''
	__slots__ = ['_name', '_choices', '_valueToName', '_nameToValue']

	def __init__( self, name, choices ):
		self._name = name
		self._choices = choices
		self._valueToName = { value:name for value, name in choices }
		self._nameToValue = { name:value for value, name in choices }
		
	def __getattr__( self, attr ):
		return self._nameToValue[attr]
		
	def getName( self, value ):
		if isinstance(value, list):
			return '[{}]'.format( ','.join( self.getName(v) for v in value ) )
		try:
			if isinstance(value, bool) and len(self._choices) == 2:
				value = int(value)
			return self._valueToName[value]
		except KeyError:
			return f'UnknownEnum={value}'
		
	def valid( self, value ):
		return value in self._valueToName
		
	def __repr__( self ):
		return '{}:\n  {}\n'.format(self._name, '\n  '.join( '{}={}'.format(name, str(value)) for value, name in self._choices))

#----------------------------------------------------------------------------------
# Guarantees a unique id even across multiple threads in CPython.
#
_CurMessageIDCounter = itertools.count(1)

def _initFieldDefs( self, *args, **kwargs ):
	''' Initialize all data fields based on each format. '''
	for f in self.FieldDefs:
		f.init( self )
		
	self.Parameters = []
	self._Length = 0
	
	# If this is a Message, initialize the message id to an invalid value.
	try:
		self._MessageID = None
	except AttributeError:
		pass
	
	# For convenience, Messages and Parameters with only one field can be initialized with a positional argument.
	# For example, it is possible to write ROSpecID_Parameter(123) as it only has one field (ROSpecID).
	# For objects with multiple values, each values must be specified with kwargs.
	if args:
		assert self.FieldCount == 1, 'Object can only have one field to initialize with positional argument'
		assert len(args) == 1, 'Cannot initialize more than one field with positional initialization'
		setattr( self, self.__slots__[0], args[0] )
		
	for key, value in kwargs.items():
		if key == 'MessageID':
			self._MessageID = value
		else:
			setattr( self, key, value )
	
	# Use a default unique MessageID if None.
	if getattr(self, '_MessageID', 'NA') is None:
		self._MessageID = next(_CurMessageIDCounter)

def _setSingleField( self, value ):
	assert self.FieldCount == 1, 'Object can only have one field to initialize with _setSingleField'
	setattr( self, self.__slots__[0], value )
		
def _getValues( self ):
	''' Get all specified values of an LLRP object. '''
	return [(f.Name, getattr(self, f.Name)) for f in self.FieldDefs if not f.TypeCode.startswith('skip')]

def _getRepr( self, indent = 0 ):
	''' Get the representation of an LLRP object. '''
	# Check for the number of values
	values = self._getValues()
	numValues = len(values) + (1 if hasattr(self, '_MessageID') else 0)
	
	s = io.StringIO()
	def w( v ):
		s.write( v )
	def iw( v ):
		s.write( '    ' * indent )
		s.write( v )
	
	if numValues > 1 or self.Parameters:
		# Output in long form (one line per value and parameter).
		iw( f'{self.Name}(\n' )
		try:
			iw( '  {}={},\n'.format('MessageID', repr(self._MessageID)) )
		except AttributeError:
			pass
			
		for f in self.DataFields:
			if f.Enum:
				iw( '  {}={}.{},\n'.format(f.Name, f.Enum._name, f.Enum.getName(getattr(self, f.Name))) )
			elif f.Name == 'ParameterTypeCode':
				v = getattr(self, f.Name)
				iw( '{}={}, # {}\n'.format(f.Name, repr(v), _parameterClassFromTypeCode[v].Name ) )
			else:
				iw('  {}={},\n'.format(f.Name, repr(getattr(self, f.Name, 'unknown')) ) )
		if self.Parameters:
			iw( '  Parameters=[\n' )
			for p in self.Parameters:
				s.write( p._getRepr( indent + 1 ) )
			iw( '  ]\n' )
		iw( '){}\n'.format(',' if indent else '') )
	else:
		# Output in short form as there is only one value.
		iw( '{}( '.format(self.Name) )
		try:
			w( ' {}={} )\n'.format('MessageID', repr(self._MessageID)) )
		except AttributeError:
			pass
			
		for f in self.DataFields:
			if f.Enum:
				w( '{}={}.{} ),\n'.format(f.Name, f.Enum._name, f.Enum.getName(getattr(self, f.Name))) )
			else:
				w( '{}={} ),\n'.format(f.Name, repr(getattr(self, f.Name, 'unknown')) ) )
		
	return s.getvalue()
	
def _addParameter( self, p ):
	''' Add a parameter to an LLRP object. '''
	self.Parameters.append( p )
	return p

def _getPTypeCodeName( pTypeCode ):
	return pTypeCode.Name if not isinstance(pTypeCode, tuple) else ' or '.join( v.Name for v in pTypeCode )
	
def _validate( self, path = None ):
	''' Validate all the values of an LLRP object. '''
	if not path:
		path = []
	path.append( self.__class__.__name__ )
	
	path_str = '.'.join( path )
	for f in self.FieldDefs:
		ftype = f.TypeCode
		if ftype.startswith('skip'):	# Pass over "skip" fields first as there is no field to validate.
			continue
			
		name = f.Name					# Name of this field.
		assert hasattr(self, name), '{}: Missing attribute: {}'.format('.'.join(path), name)
		value = getattr( self, name )	# Value of this field.
		
		if f.Enum:
			assert f.Enum.getName(value), f'{path_str}: field "{name}" must have value in enumeration: {f.Enum}'
		
		if ftype.startswith('uintbe') or ftype.startswith('intbe') or ftype.startswith('bits'):
			# Check type.
			assert isinstance( value, int ), f'{path_str}: field "{name}" must be "int" type, not "{value.__class__.__name__}"'
			
			# Check range if not bits.
			if ftype.startswith('uintbe'):
				value_min = 1 if name == 'ChannelIndex' else 0		# Exception: ChannelIndex is 1-based, not 0-based.
				value_max = (1<<int(ftype.split(':')[1])) - 1
				assert value_min <= value <= value_max, f'{path_str}: "uint" field "{name}={value}" must be in range [{value_min},{value_max}]'
			elif ftype.startswith('intbe'):
				bit_count = int(ftype.split(':')[1])
				value_min = -(1<<(bit_count-1))
				value_max = -value_min - 1
				assert value_min <= value <= value_max, f'{path_str}: "int" field "{name}={value}" must be in range [{value_min},{value_max}]'
		elif ftype == 'bool':
			assert isinstance( value, bool ), f'{path_str}: field "{name}" must be "bool" type, not "{value.__class__.__name__}"'
		elif ftype.startswith('array'):
			arr = value
			assert isinstance( arr, list ), f'{path_str}: field "{name}" must be "list" type, not "{value.__class__.__name__}"'
			for i, e in enumerate(arr):
				assert isinstance( e, int ), f'{path_str}: field "{name}" must contain all "ints" (not "{e.__class__.__name__}" at position {i})'
		elif ftype == 'string':
			assert isinstance( value, str ), f'{path_str}: field "{name}" must be "str" type, not "{value.__class__.__name__}"'
		elif ftype == 'bitarray':
			assert isinstance( value, bytes ), f'{path_str}: field "{name}" must be "bytes" type, not "{value.__class__.__name__}"'
		elif ftype == 'bytesToEnd':
			assert isinstance( value, bitstring.BitStream ), f'{path_str}: bytesToEnd field "{name}" must be "bitstring.BitStream" type, not "{value.__class__.__name__}"'
		else:
			assert False, f'{path_str}: Unknown field ftype: "{ftype}"'
			
	# Check that the number and type of parameters match the constraints.
	if self.ParameterDefs is None:
		assert not self.Parameters, f'{path_str}: No Parameters are allowed.'
	else:
		i, iMax = 0, len(self.Parameters)
		for p in self.ParameterDefs:
			pName = p['parameter'] + '_Parameter'
			rMin, rMax = p['repeat']
			iStart = i
			while i < iMax:
				nameCur = self.Parameters[i].__class__.__name__
				if nameCur != pName and llrpdef.choiceDefinitions.get(nameCur,'') != pName:
					break
				i += 1
			assert i - iStart >= rMin, f'{path_str}: Missing Parameter ({rMin}-{rMax}) of type: {pName}'
			assert i - iStart <= rMax, f'{path_str}: Too many Parameters ({rMin}-{rMax}) of type: {pName}'
		
	# Check that parameters are in the correct sequence.
	sequenceLast = 0
	for p in self.Parameters:
		pName = p.__class__.__name__
		try:
			sequenceCur = self.ParameterSequence[pName]
		except KeyError:
			try:
				key = llrpdef.choiceDefinitions[pName]
				sequenceCur = self.ParameterSequence[key]
			except KeyError:
				sequenceCur = 99999999
		
		assert sequenceLast <= sequenceCur, f'{path_str}: Incorrect Parameter Sequence: {pName}'
		sequenceLast = sequenceCur
	
	# Recursively validate all parameters.
	for p in self.Parameters:
		p._validate( path )
	
	path.pop()

def _getMessageID( self ):
	return self._MessageID
			
def _setMessageID( self, MessageID ):
	self._MessageID = MessageID

def _sendToSocket( self, socket ):
	socket.sendall( self.pack(bitstring.BitStream()).tobytes() )

def _getLLRPStatusSuccess( self ):
	for p in self.Parameters:
		if isinstance( p, LLRPStatus_Parameter ):
			return p.StatusCode == StatusCode.M_Success
	assert False, f'Message "{self.__class__.__name__}" has no LLRPStatus parameter.'

def _getAllParametersByClass( self, parameterClass ):
	for p in self.Parameters:
		if isinstance( p, parameterClass ):
			yield p
		else:
			yield from p.getAllParametersByClass( parameterClass )

def _getFirstParameterByClass( self, parameterClass ):
	for p in self.Parameters:
		if isinstance( p, parameterClass ):
			return p
		match = p.getFirstParameterByClass( parameterClass )
		if match:
			return match
	return None
		
def _MakeClass( messageOrParameter, Name, TypeCode, PackUnpack ):
	''' Make an LLRP class (Message or Parameter). '''
	extraFields = ['Parameters', '_Length']
	if messageOrParameter == 'Message':
		extraFields.append( '_MessageID' )
		
	classAttrs = {
		'Name':				Name,					# Name of this message/parameter.
		'TypeCode':			TypeCode,				# LLRP Type integer
		'PackUnpack':		PackUnpack,				# Instance to pack/unpack it into a bitstream.
		'FieldDefs':		PackUnpack.FieldDefs,	# Fields specified for this object.
		'__slots__':		[ f.Name for f in PackUnpack.FieldDefs if not f.Name.startswith('skip') ] + extraFields, # Available fields in this object.
		'ParameterDefs':	PackUnpack.ParameterDefs, # Parameters specified for this object.
		'ParameterSequence':PackUnpack.ParameterSequence, # Required sequence of Parameters for this object.
		'FieldCount':		sum( 1 for f in PackUnpack.FieldDefs if not f.Name.startswith('skip') ),			# Field count for convenience.
		'DataFields':		[ f for f in PackUnpack.FieldDefs if not f.Name.startswith('skip') ],				# List of data fields.
		'__init__':			_initFieldDefs,			# Initialize the object and default field values.
		'_setSingleField':	_setSingleField,		# Set the single field from a position argument (fails on multi-field objects).
		'_getRepr':			_getRepr,				# Routine to format the message/parameter.
		'__repr__':			_getRepr,				# Default formatting call.
		'_getValues':		_getValues,				# Gets all values of specified fields.
		'getAllParametersByClass':	_getAllParametersByClass,	# Iterator to get parameters matching a certain type (or list of types).
		'getFirstParameterByClass': _getFirstParameterByClass,	# Returns first matching parameter.
		'add':				_addParameter,			# Convenience function to add a parameter.
		'_validate':		_validate,				# Validate all data fields and parameters.
		'pack':				lambda self, s: self.PackUnpack.pack(s, self),
	}
	if messageOrParameter == 'Parameter':
		classAttrs['Encoding'] = PackUnpack.Encoding							# Add encoding if a Parameter.
	else:
		classAttrs['MessageID'] = property( _getMessageID, _setMessageID )		# Add MessageID if a Message.
		classAttrs['send'] = _sendToSocket										# Also add "send" method.
		if Name.endswith( 'RESPONSE' ):
			classAttrs['success'] = _getLLRPStatusSuccess

	MPClass = type( Name + '_' + messageOrParameter, (object,), classAttrs )	# Dynamically create the class.
	return MPClass

#---------------------------------------------------------------------------------------------------------

class _MessagePackUnpack:
	''' Pack and Unpack an LLRP Message. '''
	def __init__( self, TypeCode, Name, FieldDefs, ParameterDefs ):
		self.TypeCode = TypeCode
		self.Name = Name
		self.FieldDefs = FieldDefs if Name != 'Custom' else FieldDefs[:2]
		self.ParameterDefs = ParameterDefs
		if ParameterDefs:
			self.ParameterSequence = { pp['parameter']+'_Parameter':i for i, pp in enumerate(ParameterDefs) }
		else:
			self.ParameterSequence = {}
		self.Code = self.getCode()

	def isCustom( self ):
		try:
			return (self.TypeCode == CustomTypeCode and
					self.FieldDefs[0].Name == 'VendorIdentifier' and self.FieldDefs[0].Default is not None and
					self.FieldDefs[1].Name == 'MessageSubtype'   and self.FieldDefs[1].Default is not None
			)
		except (IndexError, KeyError):
			return False
		
	def getCode( self ):
		if self.isCustom():
			VendorIdentifier = self.FieldDefs[0].Default
			MessageSubtype = self.FieldDefs[1].Default
			return (self.TypeCode, VendorIdentifier, MessageSubtype)
		else:
			return self.TypeCode

	def unpack( self, s ):
		m = _messageClassFromTypeCode[self.TypeCode]( MessageID = -1 )	# Use a dummy MessageID - get the real one from the bitstream later.
	
		beginPos = s.pos
		TypeCode = s.read('uintbe:16')
		TypeCode &= ((1<<10)-1)
		assert m.TypeCode == TypeCode
		m._Length = s.read('uintbe:32')
		m._MessageID = s.read('uintbe:32')
		
		# Read the fields of this message.
		for f in self.FieldDefs:
			f.read( s, m, m._Length - ((s.pos - beginPos) >> 3) )
			
		if m.TypeCode == CustomTypeCode:
			# Rebind to the specific custom message based on vendor and subtype.
			mCustomClass = _messageClassFromTypeCode.get( (self.TypeCode, m.VendorIdentifier, m.MessageSubtype), None )
			if mCustomClass:
				mCustom = mCustomClass( MessageID = m._MessageID )
				mCustom._Length = m._Length
				m = mCustom
				
				# Read the rest of the fields.
				for f in m.FieldDefs[2:]:
					f.read( s, m, m._Length - ((s.pos - beginPos) >> 3) )
			else:
				# Unrecognized custom message.  Skip the remaining bytes and return a plain CustomMessage object.
				s.read( 'bytes:{}'.format(m._Length - ((s.pos - beginPos) >> 3) ) )
			
		while ((s.pos - beginPos) >> 3) < m._Length:
			m.Parameters.append( UnpackParameter(s) )
			
		return m
		
	def pack( self, s, m ):
		m._validate()
		
		beginPos = len(s)
		# Add Version 1 code to the message type - the (1<<10).
		s.append( bitstring.pack('uintbe:16, uintbe:32, uintbe:32', (1<<10) | m.TypeCode, 0, m._MessageID) )
		
		for f in m.FieldDefs:
			f.write( s, m )
		for p in m.Parameters:
			p.pack( s )

		# Fix the message length field.
		endPos = len(s)
		m._Length = (endPos - beginPos) >> 3
		s.overwrite( bitstring.pack('uintbe:32', m._Length), beginPos + 16 )
		s.pos = endPos
		return s

#---------------------------------------------------------------------------------------------------------

class _ParameterPackUnpack:
	''' Pack and Unpack an LLRP Parameter (TLV or TV encoding). '''
	TLV = 'TLV'
	TV = 'TV'
	def __init__( self, TypeCode, Name, Encoding, FieldDefs, ParameterDefs, Length = -1 ):
		self.TypeCode = TypeCode
		self.Name = Name
		self.Encoding = Encoding
		self.FieldDefs = FieldDefs
		self.ParameterDefs = ParameterDefs
		if ParameterDefs:
			self.ParameterSequence = { pp['parameter']+'_Parameter':i for i, pp in enumerate(ParameterDefs) }
		else:
			self.ParameterSequence = {}
		self.Length = Length	# only for TV encoded _parameters
		self.Code = self.getCode()

	def isCustom( self ):
		if self.Name == 'Custom':	# Ironically, the Custom field is not a custom field.
			return False
		
		# A true custom field has the CustomTypeCode with the VendorIdentifier and Subtype defined.
		try:
			return (self.TypeCode == CustomTypeCode and
					self.FieldDefs[0].Name == 'VendorIdentifier' and self.FieldDefs[0].Default is not None and
					self.FieldDefs[1].Name == 'ParameterSubtype' and self.FieldDefs[1].Default is not None
			)
		except (IndexError, KeyError):
			return False
		
	def getCode( self ):
		if self.isCustom():
			VendorIdentifier = self.FieldDefs[0].Default
			ParameterSubtype = self.FieldDefs[1].Default
			return (self.TypeCode, VendorIdentifier, ParameterSubtype)
		else:
			return self.TypeCode

	def unpack( self, s ):
		p = _parameterClassFromTypeCode[self.TypeCode]()
		
		beginPos = s.pos
		TypeCode = s.peek( 'uintbe:8' )
		if TypeCode & (1<<7):
			TypeCode &= ((1<<7) - 1)
			p._Length = self.Length
			assert p.Encoding == self.TV
			s.read( 'uintbe:8' )
		else:
			TypeCode = s.read('uintbe:16')
			TypeCode &= ((1<<10)-1)
			assert p.Encoding == self.TLV
			p._Length = s.read('uintbe:16')
		
		assert TypeCode == self.TypeCode
		
		# Read the fields of this parameter.
		# For custom parameters, this will only read VendorIdentifier and ParameterSubtype.
		# For non-custom parameters, this will read all the fields.
		for f in self.FieldDefs:
			f.read( s, p )
			
		if TypeCode == CustomTypeCode:
			# Switch to the custom parameter fields based on the VendorIdentifier and ParameterSubtype read by the Custom type.
			pCustomClass = _parameterClassFromTypeCode.get( (CustomTypeCode, p.VendorIdentifier, p.ParameterSubtype), None )
			if pCustomClass:
				pCustom = pCustomClass()
				pCustom._Length = p._Length
				
				# Read the remaining fields for the custom type, skipping VendorIdentifier and ParameterSubtype.
				p = pCustom
				for f in p.FieldDefs[2:]:
					f.read( s, p )
			else:
				# Unrecognized custom parameter.  Skip the remaining bytes and return a plain CustomParameter object.
				s.read( 'bytes:{}'.format(p._Length - ((s.pos - beginPos) >> 3) ) )
			
		if p.Encoding == self.TLV:
			while ((s.pos - beginPos) >> 3) < p._Length:
				p.Parameters.append( UnpackParameter(s) )

		return p
		
	def pack( self, s, p ):
		p._validate()

		beginPos = len(s)
		if p.Encoding == self.TLV:
			s.append( bitstring.pack('uintbe:16, uintbe:16', p.TypeCode, 0) )
		else:
			assert not p.Parameters, 'LLRP TV _parameters cannot contain nested parameters'
			s.append( bitstring.pack('uintbe:8', p.TypeCode | 128 ) )
		
		for f in p.FieldDefs:	# Was self.FieldDefs.  We need to use the "p" to handle the extra fields in the custom messages.
			f.write( s, p )

		# Fix the length field.
		if p.Encoding == self.TLV:
			for pp in p.Parameters:
				pp.pack( s )
				
			endPos = len(s)
			p._Length = (endPos - beginPos) >> 3
			s.overwrite( bitstring.pack('uintbe:16', p._Length), beginPos + 16 )
			s.pos = endPos
		else:
			p._Length = self.Length
		return s

def _DefTV( TypeCode, Name, FieldDefs ):
	''' Define a TV parameter (no explicit length field). '''
	Length = 8		# Adjust for the leading TypeCode (8 bits).
	for f in FieldDefs:
		Length += int(f.TypeCode.split(':')[1])
	assert Length & 7 == 0
	Length >>= 3	# Divide by 8 to get bytes from bits.
	return _ParameterPackUnpack( TypeCode, Name, _ParameterPackUnpack.TV, FieldDefs, None, Length )
	
def _DefTLV( TypeCode, Name, FieldDefs, ParameterDefs ):
	''' Define a TLV parameter (length field included). '''
	return _ParameterPackUnpack( TypeCode, Name, _ParameterPackUnpack.TLV, FieldDefs, ParameterDefs )

def _fixFieldDefs( fields ):
	return [_FieldDef(	f['name'],
						f['type'],
						f.get('enumeration', None),
						f.get('format', None),
						f.get('default', None) ) for f in fields]

#-----------------------------------------------------------------------------
# Create Enum instances and add to the global namespace.
#
_enumClassFromName = {}
for e in llrpdef.enums:
	Name = e['name']
	Choices = e['choices']
	_enumClassFromName[Name] = _EnumDef( Name, Choices )

globals().update( _enumClassFromName )

#-----------------------------------------------------------------------------
# Create Parameter classes from the specs.
# Initialize a dict to retrieve the Parameter PackUnpack class from the TypeCode.
# Initialize a dict to retrieve the Parameter class from the TypeCode.
#
_ParameterPackUnpackLookup = {}
_parameterClassFromName = {}
_parameterClassFromTypeCode = {}
for p in llrpdef.parameters:
	TypeCode = p['typeNum']
	Name = p['name']
	if TypeCode <= 127:
		pup = _DefTV( TypeCode, Name, _fixFieldDefs(p['fields']) )
	else:
		pup = _DefTLV( TypeCode, Name, _fixFieldDefs(p.get('fields',[])), p.get('parameters', None) )
		
	parameterClassName = pup.Name + '_Parameter'
	_ParameterPackUnpackLookup[TypeCode] = pup
	cls = _MakeClass( 'Parameter', pup.Name, TypeCode, pup )
	
	_parameterClassFromName[parameterClassName] = cls	
	_parameterClassFromTypeCode[pup.getCode()] = cls
	
globals().update( _parameterClassFromName )	# Add Parameter classes to global namespace.

#-----------------------------------------------------------------------------
# Create Messages classes from the specs.
# Initialize a dict to retrieve the Message PackUnpack class from the TypeCode.
# Initialize a dict to retrieve the Message class from the TypeCode.
#
_MessagePackUnpackLookup = {}
_messageClassFromName = {}
_messageClassFromTypeCode = {}
for m in llrpdef.messages:
	TypeCode = m['typeNum']
	Name = m['name']
	pup = _MessagePackUnpack(TypeCode, Name, _fixFieldDefs(m.get('fields',[])), m.get('parameters',None))
	messageClassName = pup.Name + '_Message'
	_MessagePackUnpackLookup[TypeCode] = pup
	_messageClassFromTypeCode[pup.Code] = _messageClassFromName[messageClassName] = _MakeClass( 'Message', pup.Name, TypeCode, pup )
	
globals().update( _messageClassFromName )	# Add Message classes to global namespace.

# Cleanup the definitions as we don't need them anymore.
del llrpdef.enums
del llrpdef.parameters
del llrpdef.messages
	
#------------------------------------------------------------------
# Routines to handle messages over a socket.
#
def UnpackMessageFromSocket( sock ):
	zeroLenChunkMax = 2
	
	# Read the header bytes to get the messageID and length.
	headerBytes = (16+32) >> 3
	
	zeroLenChunkCount = 0
	chunks = []
	messageLen = 0
	while messageLen < headerBytes:
		# print headerBytes, messageLen, headerBytes - messageLen
		chunk = sock.recv( headerBytes - messageLen )
		if not chunk:
			zeroLenChunkCount += 1
			if zeroLenChunkCount < zeroLenChunkMax:
				continue
			raise RuntimeError( 'LLRP socket connection broken' )
		chunks.append( chunk )
		messageLen += len(chunk)
		zeroLenChunkCount = 0
	
	# Convert to a BitStream to get the message TypeCode and Length.
	s = bitstring.ConstBitStream( bytes=b''.join(chunks) )
	TypeCode = s.read('uintbe:16')
	TypeCode &= ((1<<10)-1)
	Length = s.read('uintbe:32')
	
	# print( 'UnpackMessageFromSocket: TypeCode={} Length={} {}'.format(TypeCode, Length, _messageClassFromTypeCode[TypeCode].__name__) )
	
	# Read the remaining message based on the Length.
	zeroLenChunkCount = 0
	while messageLen < Length:
		chunk = sock.recv( Length - messageLen )
		if not chunk:
			zeroLenChunkCount += 1
			if zeroLenChunkCount < zeroLenChunkMax:
				continue
			raise RuntimeError( 'LLRP socket connection broken' )
		chunks.append( chunk )
		messageLen += len(chunk)
		zeroLenChunkCount = 0
	
	# Convert the full message to a BitStream and parse it.
	s = bitstring.ConstBitStream( bytes=b''.join(chunks) )
	return _MessagePackUnpackLookup[TypeCode].unpack( s )

def UnpackMessage( s ):
	''' Unpack a message from a bitstream. '''
	s.pos = 0
	TypeCode = s.peek('uintbe:16')
	TypeCode &= ((1<<10)-1)
	return _MessagePackUnpackLookup[TypeCode].unpack( s )
	
def PackMessage( m ):
	''' Pack message into a bitstream. '''
	assert m.TypeCode in _messageClassFromTypeCode
	return m.pack( bitstring.BitStream() )
	
def UnpackParameter( s ):
	''' Unpack a parameter from a bitstream. '''
	TypeCode = s.peek( 'uintbe:8' )
	if TypeCode & (1<<7):
		TypeCode &= ((1<<7) - 1)			# TV Encoding
	else:
		TypeCode = s.peek('uintbe:16')		# TLV Encoding
		TypeCode &= ((1<<10)-1)
	return _ParameterPackUnpackLookup[TypeCode].unpack( s )
	
def GetResponseClass( message ):
	''' Get the corresponding response class of a message. '''
	if message.TypeCode == CustomTypeCode:
		responseClassName = 'CUSTOM_MESSAGE_Message'
	else:
		responseClassName = message.__class__.__name__.replace('_Message', '_RESPONSE_Message')
	return globals()[responseClassName]
	
def WaitForMessage( MessageID, sock, nonMatchingMessageHandler = None ):
	''' Wait for a message matching the MessageID. '''
	''' Call the message handler on any message not matching the MessageID. '''
	while True:
		response = UnpackMessageFromSocket( sock )
		if response.MessageID == MessageID:
			return response
		elif nonMatchingMessageHandler:
			nonMatchingMessageHandler( response )

#-----------------------------------------------------------------------------

def HexFormatToStr( value ):
	if isinstance(value, bool):
		return ('0','1')[value]
	if isinstance(value, int):
		return f'{value:X}'
	return ''.join( f'{x:02X}' for x in value ).lstrip('0')

def HexFormatToInt( value ):
	return int(''.join( f'{x:02X}' for x in value ), 16)

def GetBasicAddRospecMessage( MessageID = None, ROSpecID = 123, inventoryParameterSpecID = 1234, antennas = None ):
	#-----------------------------------------------------------------------------
	# Create a basic Reader Operation Spec message
	#
	if not antennas:	# Default to all antennas if unspecified.
		antennas = [0]
	
	rospecMessage = ADD_ROSPEC_Message( MessageID = MessageID, Parameters = [
		# Initialize to disabled.
		ROSpec_Parameter(
			ROSpecID = ROSpecID,
			CurrentState = ROSpecState.Disabled,
			Parameters = [
				ROBoundarySpec_Parameter(		# Configure boundary spec (start and stop triggers for the reader).
					Parameters = [
						# Start immediately.
						ROSpecStartTrigger_Parameter(ROSpecStartTriggerType = ROSpecStartTriggerType.Immediate),
						# No stop trigger.
						ROSpecStopTrigger_Parameter(ROSpecStopTriggerType = ROSpecStopTriggerType.Null),
					]
				),
				
				AISpec_Parameter(				# Antenna Inventory Spec (specifies which antennas and protocol to use)
					AntennaIDs = antennas,		# Use specified antennas.
					Parameters = [
						AISpecStopTrigger_Parameter(
							AISpecStopTriggerType = AISpecStopTriggerType.Tag_Observation,
							Parameters = [
								TagObservationTrigger_Parameter(
									TriggerType = TagObservationTriggerType.Upon_Seeing_N_Tags_Or_Timeout,
									NumberOfTags = 500,
									NumberOfAttempts = 1,
									Timeout = 500,		# Milliseconds
									T = 0,				# Idle time between responses.
								),
							]
						),
						InventoryParameterSpec_Parameter(
							InventoryParameterSpecID = inventoryParameterSpecID,
							ProtocolID = AirProtocols.EPCGlobalClass1Gen2,
						),
					]
				),
				
				ROReportSpec_Parameter(			# Report spec (specifies what to send from the reader)
					ROReportTrigger = ROReportTriggerType.Upon_N_Tags_Or_End_Of_ROSpec,
					N = 0,
					Parameters = [
						TagReportContentSelector_Parameter(
							EnableAntennaID = True,
							EnableFirstSeenTimestamp = True,
						),
					]
				),
			]
		)	# ROSpec_Parameter
	])	# ADD_ROSPEC_Message
	return rospecMessage

def GetEnableRospecMesssage( MessageID, ROSpecID = 123 ):
	return ENABLE_ROSPEC_Message(MessageID = MessageID, ROSpecID = ROSpecID)
	
actions = {
	EPC_96_Parameter:					lambda x: ('EPC', x.EPC),
	EPCData_Parameter: 					lambda x: ('EPC', x.EPC),
	FirstSeenTimestampUTC_Parameter:	lambda x: ('Timestamp', x.Microseconds),
	AntennaID_Parameter:				lambda x: ('AntennaID', x.AntennaID),
	TagSeenCount_Parameter:				lambda x: ('TagSeenCount', x.TagCount),
	PeakRSSI_Parameter:					lambda x: ('PeakRSSI', x.PeakRSSI),
}
def _getTagData( self ):
	tagData = []
	for p in self.Parameters:
		if isinstance(p, TagReportData_Parameter):
			data = {}
			for pp in p.Parameters:
				try:
					key, value = actions[type(pp)](pp)
					data[key] = value
				except KeyError:
					pass
			tagData.append( data )
			
	return tagData

# Add a 'getTagData' convenience method to the RO_ACCESS_REPORT message.
RO_ACCESS_REPORT_Message.getTagData = _getTagData

# Remove the bytesToEnd Data field from the CUSTOM_MESSAGE and Custom parameter.
CUSTOM_MESSAGE_Message.FieldDefs = CUSTOM_MESSAGE_Message.FieldDefs[:-1]
Custom_Parameter.FieldDefs = Custom_Parameter.FieldDefs[:-1]

def getVendorName( vendorCode ):
	for name, code in llrpdef.vendors.items():
		if vendorCode == code:
			return name
	return str(vendorCode)

if __name__ == '__main__':
	c = IMPINJ_ENABLE_EXTENSIONS_Message()
	print( c )
	
	s = c.pack( bitstring.BitStream() )
	print( s )
	
	m = UnpackMessage( s )
	print( m )
	
	#-----------------------------

	rospecMessage = GetBasicAddRospecMessage( 1 )
	rospecMessage._validate()
	
	rospecEnableMessage = GetEnableRospecMesssage( 2 )
	rospecMessage._validate()
	
	print( rospecMessage )
	rospecMessage._validate()
	
	print( rospecEnableMessage )
	rospecEnableMessage._validate()
	
	s = rospecMessage.pack( bitstring.BitStream() )
	print( s )
	
	m = UnpackMessage( s )
	print( m )
	
	bb=s.tobytes()
	t = bitstring.ConstBitStream( bytes=bb )
	n = UnpackMessage( t )
	print( n )
	
	s = rospecEnableMessage.pack( bitstring.BitStream() )
	print( s )
	
	m = UnpackMessage( s )
	print( m )
	
	bb=s.tobytes()
	t = bitstring.ConstBitStream( bytes=bb )
	n = UnpackMessage( t )
	print( n )
	
	customMessage = IMPINJ_ENABLE_EXTENSIONS_Message( MessageID = 1 )
	print( customMessage )
	
	s = customMessage.pack( bitstring.BitStream() )
	m = UnpackMessage( s )
	print( m )
	
	customMessage = IMPINJ_ADD_ENCODE_DATA_Message( MessageID = 1, EncodeDataCacheID = 32 )
	print( customMessage )
	
	s = customMessage.pack( bitstring.BitStream() )
	m = UnpackMessage( s )
	print( m )
	
	message = READER_EVENT_NOTIFICATION_Message( MessageID = 1234, Parameters = [
		UTCTimestamp_Parameter( Microseconds = 31415626 ),
		ReaderEventNotificationData_Parameter( Parameters = [
			ConnectionAttemptEvent_Parameter(
				Status = 2,
			),
		]),
	])	# ADD_ROSPEC_Message
	print( message.__repr__() )
	print( message.getFirstParameterByClass(ConnectionAttemptEvent_Parameter) )
	
	print( ConnectionAttemptStatusType.getName(2), ConnectionAttemptStatusType.Success )
	
	# Custom Parameters Test
	customMessage = GET_READER_CONFIG_RESPONSE_Message( MessageID = 1, Parameters = [
			LLRPStatus_Parameter( StatusCode=StatusCode.M_Success ),
			ImpinjReaderTemperature_Parameter( Temperature=40 ),
		],
	)
	print( '*'*40 )
	print( customMessage )
	
	s = customMessage.pack( bitstring.BitStream() )
	m = UnpackMessage( s )
	print( m )
	
	#---------------------------------------------------------------------------
	# Check if ChannelIndex value is validated correctly.
	#
	for ci in range(2):
		message = SET_READER_CONFIG_Message( Parameters = [
			AntennaConfiguration_Parameter( AntennaID = 0, Parameters = [
				RFTransmitter_Parameter( 
					TransmitPower = 8192,
					HopTableID = 1,
					ChannelIndex = ci,			# should assert if ChannelIndex = 0.
				),
				C1G2InventoryCommand_Parameter( Parameters = [
					C1G2SingulationControl_Parameter(
						Session = 0,
						TagPopulation = 100,
						TagTransitTime = 3000,
					),
				] ),
			] ),
		] )
		try:
			message._validate()
		except Exception as e:
			if ci == 0:
				print( f'assert when ChannelIndex=0:\n\t{e}' )
