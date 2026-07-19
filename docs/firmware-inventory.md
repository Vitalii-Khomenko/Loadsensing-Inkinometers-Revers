# Firmware Inventory

Last updated: 2026-07-15

Fifteen files in the APK `firmwares/` directory were found and hashed. The machine-readable inventory is `analysis/firmware/inventory.csv`. This count excludes unrelated `.bin` resources outside that directory and duplicate copies produced by the two decompilers.

The APK explicitly maps the physically relevant families as follows:

- G6 normal TIL90 is represented by node type `LS_G6_INC360` and firmware `LSG_TIL90_v2_81.bin`;
- G6 alarm TIL90 is `LS_G6_INC360_ALARM` with `LSG_TIL90E_v2_67.bin`;
- G6 Laser TIL90 is `LS_G6_LASER_TIL90` with `LSG_LASTIL90_v2_85.bin`;
- G7 TIL90 is `LS_G7_TIL90` with `LS_G7_TIL90_v3_13.bin`.

This explains why `Til90Node.java` is explicitly G7 while G6 TIL90 behavior is routed through INC360 or INC360 Alarm node classes.

Direct hardware response product code `0x4E` maps the connected sensor to `LS-G6-TIL90-I` / `LS_G6_INC360`. Its reported firmware `2.81` matches the inventoried `LSG_TIL90_v2_81.bin` mapping.

The Bluetooth image is a Silicon Labs GBL application image. Other node `.bin` files are reported only as generic data by `file`; their internal headers, signatures, encryption, and compatibility checks remain unconfirmed.

The mapped G6 image was validated at 124288 bytes with SHA-256 `9dba6261df792649b0cebd0db86f1aa459bb93209b8783dad2da020a5f0b227f` and physically reinstalled on node `101677`. The recovered Android sequence sends reboot `09`, waits one second, writes bootloader password `worldsensing`, waits for XMODEM `C`, transfers 971 128-byte XMODEM-CRC blocks with the two expected initial CRC-probe retries, and finishes with acknowledged EOT. Firmware returned as 2.81 and the complete configuration diff was empty.

This validates recovery/reinstallation of the exact current image only. The APK contains no newer normal G6 TIL90 firmware, and arbitrary images remain rejected by filename, size, hash, product, and version checks.
