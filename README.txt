
======
pyllrp
======

A pure Python implementation of LLRP (Low Level Reader Protocol)
used by RFID readers including Impinj, Alien and ThingMagic.
See the LLRP spec for details on the messages.

Allows quick-and-easy scripting in fully portable pure Python to create LLRP applications.

All Message and Parameters are full Python classes.
Full validation of all LLRP Messages and Parameters including data type, date values and parameter checking.
Full support for enumerated values.

See TinyExample.py for how to use.

A reader connection manager is also included that can connect to a reader, transact commands, then start/stop a thread to listen for tag reads.  A message handler can be configured to respond to any reader message.  See wxExample.py for a simple method to show reader messages in a wxPython application with a Queue (requires wxPython install).

The module also supports reading and writing messages in XML format.
