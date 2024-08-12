# pyllrp

A 100% complete, pure Python implementation of LLRP (Low Level Reader Protocol) also with 100% support for Impinj extensions.

Communicate with LLRP-compliant RFID readers including Impinj, Alien and ThingMagic.
See the [LLRP spec](https://www.gs1.org/sites/default/files/docs/epc/llrp_1_0_1-standard-20070813.pdf) for full details.

__pyllrp__ supports quick-and-easy scripting in portable Python to
create LLRP applications.

It is used extensively in [CrossMgr](https://github.com/esitarski/CrossMgr) (CrossMgrImpinj and TagReadWrite) and [RaceDB](https://github.com/esitarski/RaceDB) for race timing.

All LLRP features and the full Impinj extension is supported:

* Message and Parameters are Python classes.
* 100% runtime validation of all LLRP Messages and Parameters including data types, data ranges, parameter sequence and count.
* 100% support for constant values - no hardcoded values necessary.
* Impossible to pass incorrect or malformed LLRP messages to the reader.

See TinyExample.py for how to use.

A reader connection manager is also included that can connect to a reader, transact commands,
and/or start/stop a thread to listen for tag reads.
A message handler callback can be configured to respond to reader messages in your code.

See wxExample.py for a simple method to show reader messages in
a wxPython application with a Queue (requires wxPython).

The module also supports reading and writing messages in XML format, however, I find it just as easy to create the messages in Python code.

pyllrp is picky about LLRP Messages, Parameters and data types.
For example, pyllrp passing ints as bools won't work; if the value must be True/False, 1/0 won't work.
The names of all non-default fields must be specified, with the exception of Parameters which have only one field.
In this case, the single parameter can be passed in the constructor.

## How to use it:

import pyllrp and follow the example.
TinyExample.py shows how to formulate LLRP specs, messages and parameters.
To run TinyExample, from the top pyllrp directory, enter "python3 -m pyllrp.TinyExample".


## How it works:

ParseDef.py reads the LLRP XML spec file and compiles it into a dict which it pretty-prints to a file called llrpdef.py.
ParseDef must be run every time the XML files change.

pyllrp.py imports llrpdef.py and converts the Messages, Parameters and Enums into runtime classes.
It adds the binary pack/unpack methods, data validation and human-readable formating functions to each class.
Startup time is minimal due to the llrpdef.py pre-processing, and this augementation is only done once.

Unlike other LLRP interfaces which sometimes combine messages and parameters into one call, pyllrp requires that you follow the LLRP spec accurately.
If in doubt, check the LLRP spec and follow it exactly.

## Future work:

Because the classes are created dynamically, python linters (eg. flake8) create lots of warnings for __pyllrp__ calls.
This could be migitated by code generating the full classes in llrpdef.py.
But, this is likely slower and less memory efficient than the current approach.
