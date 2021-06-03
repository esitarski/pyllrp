
======
pyllrp
======

A pure Python implementation of LLRP (Low Level Reader Protocol)
used by LLRP-compliant RFID readers including Impinj, Alien and ThingMagic.
See the LLRP spec (https://www.gs1.org/sites/default/files/docs/epc/llrp_1_0_1-standard-20070813.pdf) for details.

pyllrp enables quick-and-easy scripting in fully portable pure Python to create LLRP applications.

The implementation is 100% complete.  All LLRP features and Impinj custom extensions are supported.

* Message and Parameters are full Python classes.
* Full validation of all LLRP Messages and Parameters including data types, data values and parameter sequence and count.
* Full support for enumerated values.
* Impossible to pass malformed LLRP messages.

See TinyExample.py for how to use.

A reader connection manager is also included that can connect to a reader, transact commands, then start/stop a thread to listen for tag reads.
A message handler can be configured to respond to any reader message.  See wxExample.py for a simple method to show reader messages in a wxPython application with a Queue (requires wxPython install).

The module also supports reading and writing messages in XML format.

Unlike other implementations, pyllrp is 100% compliant with the LLRP XML specs: it generates the interface from the LLRP XML spec itself.

pyllrp is also 100% pedantic regarding LLRP Messages and Parameters.
For example, pyllrp is strict about bool and ints: passing 1/0 for True/False doesn't work.
The names of all fields must be specified, with the exception of Parameters which have only one field.  In this case, the single parameter is taken
to be the value.

How to use it:

The only files you need are pyllrp.py and llrpdef.py.  TinyExample.py shows how to formulate LLRP specs, messages and parameters.


How it works:

ParseDef.py reads the XML spec files and generates the llrpdef.py file.  During this process, it translates the LLRP data types into bitstream representation and processes the XML into Python-friendly structures.  ParseDef must be run every time the XML files change.

At run time, pyllrp.py imports llrpdef and "decorates" the Messages, Parameters and Enums as classes adding binary pack/unpack, validation and human-readable formating functions.  This effort is minimal due to the llrpdef.py pre-processing.
