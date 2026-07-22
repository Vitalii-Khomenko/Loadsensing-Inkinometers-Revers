# Validated TIL90 firmware artifact

`LSG_TIL90_v2_81.bin` is the exact G6 TIL90 firmware 2.81 image mapped to product code `0x4E` and physically reinstalled successfully on the tested `LS-G6-TIL90-I` sensor.

The guarded firmware service rejects the file unless all of these immutable properties match:

- filename: `LSG_TIL90_v2_81.bin`;
- size: `124288` bytes;
- SHA-256: `9dba6261df792649b0cebd0db86f1aa459bb93209b8783dad2da020a5f0b227f`;
- target product code: `0x4E`;
- target version: `2.81`.

The image is included so a rebuilt Docker container retains the already validated recovery capability without depending on decompiled APK output. Arbitrary firmware files and other product variants remain unsupported.
