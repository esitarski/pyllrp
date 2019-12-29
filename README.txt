
======
pyllrp
======

A pure Python implementation of LLRP (Low Level Reader Protocol)
used by LLRP-compliant RFID readers including Impinj, Alien and ThingMagic.
See the LLRP spec (https://www.gs1.org/sites/default/files/docs/epc/llrp_1_0_1-standard-20070813.pdf) for details.

pyllrp enables quick-and-easy scripting in fully portable pure Python to create LLRP applications.

The implementation is 100% complete.  All LLRP features and Impinj extensions are supported.

* Message and Parameters are full Python classes.
* Full validation of all LLRP Messages and Parameters including data types, data values and parameter checking.
* Full support for enumerated values.
* Impossible to pass malformed LLRP messages.

See TinyExample.py for how to use.

A reader connection manager is also included that can connect to a reader, transact commands, then start/stop a thread to listen for tag reads.
A message handler can be configured to respond to any reader message.  See wxExample.py for a simple method to show reader messages in a wxPython application with a Queue (requires wxPython install).

The module also supports reading and writing messages in XML format.

Unlike other implementations, pyllrp is 100% compliant with the LLRP XML specs: it generates the interface from the LLRP XML spec itself.

pyllrp is also 100% pedantic regarding LLRP Messages and Parameters.
For example, pyllrp is strict about bool and ints: passing 1/0 for True/False doesn't work.

How pyllrp Works:

ParseDef.py reads the XML spec files and generates the llrpdef.py file.  During this process, it translates the LLRP field specs into bitstream representation and transforms the representation from XML to Python structures.  ParseDef must be run every time the XML files change.
At run time, pyllrp.py imports llrpdef and "decorates" the Messages, Parameters and Enums as classes adding binary pack/unpack, validation and other human-readable formating functions.