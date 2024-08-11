
======
pyllrp
======

A pure Python implementation of LLRP (Low Level Reader Protocol)
used to communicate with LLRP-compliant RFID readers including Impinj, Alien and ThingMagic.
See the LLRP spec ) for details:
   https://www.gs1.org/sites/default/files/docs/epc/llrp_1_0_1-standard-20070813.pdf

pyllrp enables quick-and-easy scripting in portable pure Python to
create LLRP applications.

It is used extensively in CrossMgr, RaceDB, TagReadWrite for RFID and race timing.

The implementation is 100% complete.  All LLRP features and full Impinj custom extensions are
supported.

* Message and Parameters are full Python classes.
* Full validation of all LLRP Messages and Parameters including data types, data ranges, parameter sequence and count.
* Full support for enumerated values - no hardcoded values.
* "Impossible" to pass incorrect or malformed LLRP messages to the reader.

See TinyExample.py for how to use.

A reader connection manager is also included that can connect to a reader, transact commands,
then start/stop a thread to listen for tag reads.
A message handler can be configured to respond to any reader message.
See wxExample.py for a simple method to show reader messages in
a wxPython application with a Queue (requires wxPython install).

The module also supports reading and writing messages in XML format.

Unlike other implementations, pyllrp generates the interfaces from the LLRP XML spec itself.
It is 100% compliant with the LLRP spec and Impinj extensions.

pyllrp is also 100% pedantic regarding LLRP Messages and Parameters.
For example, pyllrp is strict about bool and ints: passing 1/0 for True/False doesn't work.
The names of all fields must be specified, with the exception of Parameters which have only one field.
In this case, the single parameter is taken to be the value.

How to use it:

The only files you need are pyllrp.py and llrpdef.py.
TinyExample.py shows how to formulate LLRP specs, messages and parameters.
To run TinyExample, from the top pyllrp directory, enter "python3 -m pyllrp.TinyExample".


How it works:

ParseDef.py reads the LLRP XML spec files and generates the llrpdef.py file.
During this process, it translates the LLRP data types into bitstream representation and processes the XML into Python-friendly structures.
ParseDef must be run every time the XML files change.

At run time, pyllrp.py imports llrpdef and does a 1-time augmentation on the Messages, Parameters and Enums into classes.
It adds the binary pack/unpack, validation and human-readable formating functions.
Startup time is minimal due to the llrpdef.py pre-processing.

Stuff to do:

Because the classes are created dynamically, python linters (eg. flake8) do not understand pyllrp classes.
The only way I can think of to migitate this is to code-generate the full signatures for the class functions,
but this would be messier than dynamically creating the classes from the llrpdef.py info.
