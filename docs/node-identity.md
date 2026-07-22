# Node ID and Factory Identity

Last updated: 2026-07-22

## Confirmed identity layers

The protocol header carries a 20-bit node ID. The official Android application accepts a replacement value from `0` through `1048575` and calls the library's version-aware `sendSetNodeId()` operation. On sufficiently recent firmware, the library uses the version-2 node-ID command and waits for a health response addressed with the new ID. Older firmware uses a legacy 16-bit command and rejects values above `65535`.

This proves that the normal node ID is intentionally writable by the official software. It does not prove that the command rewrites every factory identity source.

The following values are distinct:

- protocol node ID used to address normal messages;
- device serial number returned by node information;
- product code identifying the hardware family;
- LoRa radio address, network ID, and join identifiers;
- factory calibration offsets, gains, and calibration timestamp;
- any manufacturing or service record used to reconstruct defaults.

The physical factory-reset trial on the current G6 preserved the observed node ID, serial/radio identity, product, firmware, calibration, and enabled axes while resetting operational radio and sampling configuration. Because that trial started with the sensor's existing ID, it does not determine whether an earlier user-assigned ID would revert to a separately stored manufacturing value. The operator separately reports that a user-assigned node ID does revert to the older value after reset. That behavior is evidence that the writable node ID and a factory fallback ID are stored separately, but the fallback storage location is not yet identified.

## Deeper replacement boundary

No reviewed application path exposes a second command for rewriting a manufacturing identity, serial number, product code, or factory fallback ID. A deeper change would therefore require an authorized service/manufacturing interface, a bootloader function not present in the reviewed workflow, or direct flash/debug access. The correct memory location, integrity checks, duplication, and coupling to calibration or radio provisioning are unknown.

Blind EEPROM/flash edits, arbitrary firmware patches, or SWD/JTAG writes are not safe substitutes. They can make the node undiscoverable, create duplicate field identities, invalidate gateway records, or damage factory calibration and recovery state.

The independent tooling consequently keeps `node_identity_write` blocked. A safe implementation requires all of the following before any physical trial:

1. recover the exact official serializer and firmware-version branch;
2. establish the allowed range and site-wide uniqueness of the new ID;
3. preserve a complete backup and both old/new discovery paths;
4. verify acknowledgement and a health response under the new ID;
5. reboot and verify persistence;
6. perform a controlled factory reset and determine the fallback behavior;
7. retain an authorized service/debug recovery method if neither ID responds.

The normal official node-ID operation can be implemented later behind these gates. A permanent manufacturing-identity replacement cannot currently be claimed from the available evidence.
