# Historical Data Recovery Protocol

Last updated: 2026-07-15

Status: complete static reconstruction and bounded hardware validation on node `101677`.

## Stored-data interval query

Before choosing a recovery range, the official client can send the one-byte request body `04`. Response AM type `0x02` (`C8926u`) contains two unsigned big-endian 32-bit Unix timestamps: the oldest available record followed by the newest available record. The decoder is `decode_stored_data_interval()`.

## Request

The request is exactly ten unframed bytes:

```text
offset  size  field
0       1     request AM type = 0x03
1       1     recovered data filter: 0x00 all types or 0x56 raw data only
2       4     start Unix timestamp in seconds, unsigned big-endian
6       4     end Unix timestamp in seconds, unsigned big-endian
```

The normal UART DLE envelope is applied afterward. The Android client uses a 40-second response timeout.

## Recovered record wrapper

Each recovered record arrives as outer AM type `0x01` (`C8911n0`):

```text
six-byte protocol-v2 header with AM = 0x01
u8 capture ID
u8 recovered/inner AM type
inner message payload
```

The outer header supplies product code, node ID, and sequence number. The Android parser reconstructs an ordinary inner message by retaining outer header bytes 0–4, replacing header byte 5 with the inner AM type, and appending the inner payload. It then dispatches the reconstructed message through the normal AM registry.

Recovered messages must inherit the timestamped message base class. Fragmented message types are passed through the same defragmenter used for live traffic before being added to the recovery result.

## Completion marker

Recovery ends with outer AM type `0x00` and a 16-bit response code of `0x0080` (`END_OF_RECOVER_DATA`). Smali proves the value is `0x80`; JADX incorrectly rendered it as an unrelated Mapbox constant. LoRa coverage-test completion is separately `0x0081`.

When the end marker arrives, the recovery processor marks its accumulated wrapper finished. If no recovered records arrived, it returns an empty finished wrapper.

There is no explicit pagination or record count in the request. Streaming continues until the end marker or timeout. The independent CLI therefore enforces local span, record, byte and timeout limits. A capture ID is present per outer recovered message, but static code does not use it for ordering or duplicate rejection.

## Physical validation

On 2026-07-15 a bounded two-hour request (`1784125053` through `1784132253`) returned 18 records, 608 received bytes and an immediate `0x0080` completion marker. All wrappers belonged to node `101677`, used capture ID 5, and preserved the same sequence number in outer and reconstructed inner headers. The records comprised 12 regular INC360 readings (`0x4C`) and 6 health records (`0x4F`). The end timestamp was inclusive because a record at exactly `1784132253` was returned; start inclusivity is not yet proven.

The history also confirmed that directly requested live readings and health queries can be stored alongside scheduled readings. Older scheduled readings were 300 seconds apart, while the first post-configuration scheduled interval reflected the official 3600-second setting.

## Local resumable importer

`tools/history_manager.py` converts a long requested range into independently bounded chunks. The default is six hours; the hard maximum remains the protocol client's tested seven-day bound. A SQLite job stores the original range, next cursor, chunk size, counts, status, and last error.

The cursor advances to `chunk_end + 1` only after the chunk returns status `ok` and the `0x0080` completion marker. A serial exception, timeout, size/record limit, or incomplete response leaves the cursor unchanged and the job `paused`. Resuming therefore repeats at most the uncommitted chunk. Records are inserted with unique `(node_id, timestamp)` keys, making a repeated chunk idempotent while the job separately counts received, imported, and duplicate records.

This implementation is synthetic-tested for a disconnect followed by resume across two chunks. The earlier two-hour physical history capture validates the underlying request, wrapper decoder, inclusive end, and completion marker. A deliberately interrupted multi-chunk physical recovery remains a safe follow-up test.

## Ordering and grouping

Timestamped messages compare first by UTC timestamp and then by the one-byte protocol header sequence number. Historic conversion groups records by timestamp before building exported domain objects. Exact duplicate behavior and capture-ID rollover require passive validation.

## Remaining passive checks

- whether the start endpoint is inclusive (the end endpoint is hardware-confirmed inclusive);
- capture-ID start value and rollover;
- ordering when timestamps match;
- behavior after packet loss or duplicated wrappers;
- maximum records returned in one recovery stream;
- timezone behavior displayed by the official app.
