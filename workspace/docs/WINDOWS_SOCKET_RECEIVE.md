# Windows/mGBA receive-loop correction

The reported local sequence was version/info/ping success followed by a frame
request reset (Windows 10054), a client `unknown error` log, and a listener that
remained open. No live reproduction was performed in this cloud task.

The old callback read up to 32 times, including after draining all available data.
It relied on an empty read returning `socket.ERRORS.AGAIN`. If that read instead
returns `unknown error`, the existing error path closes the connection. Whether a
reply reaches Python before that close can affect the observed symptom; a frame
reset alone does not establish that frame dispatch is defective.

Checked official mGBA 0.10.5 source commit
`26b7884bc25a5933960f3cdcd98bac1ae14d42e2`:

- [Lua socket adapter](https://github.com/mgba-emu/mgba/blob/26b7884bc25a5933960f3cdcd98bac1ae14d42e2/src/script/engines/lua.c):
  `hasdata()` calls the underlying `select(0)` and returns true/false, or nil/error.
  The built-in poller uses it before dispatching `received`. `receive()` returns
  nil/error on disconnect/failure. Readability also covers EOF.
- [Core socket binding](https://github.com/mgba-emu/mgba/blob/26b7884bc25a5933960f3cdcd98bac1ae14d42e2/src/script/socket.c):
  nonpositive receives inspect the native socket error; native error translation
  includes build-dependent Windows branches. The actual Windows binary's build
  flags and precise native error were not inspected, so this is not a proven
  diagnosis of its error-mapping origin.

The bridge now calls `sock:hasdata()` before every receive, including a potentially
stale first callback. False readiness returns without consuming or clearing the
partial buffer. Transient AGAIN from readiness or a readiness/read race remains
nonfatal. Genuine readiness/receive errors close and log only that client; readable
EOF closes the peer normally. Unknown errors are not reclassified as transient.

The 4096-byte read size, 32-read callback budget, 128 KiB buffer ceiling, framing,
multiple-request handling, version 0.3.1, listener address/port, key ownership,
cleanup, shutdown acknowledgement and file-safety policies are preserved.

Nine new Lua scenarios test idle Windows-style unknown errors, stale callbacks,
partial commands/split markers, continued requests, 32-read continuation, buffer
limits across callbacks, readiness errors, transient races and genuine EOF/errors.
The mock now respects the maximum receive size and counts idle reads. The old
bridge fails the Windows regression; the corrected bridge passes it without an
idle receive.

For subsequent local verification, load the updated script and refresh the
manifest's reviewed Lua SHA-256. Retry the read-only sequence under the selected
existing testing policy before any controller input. Offline passes do not prove
that the reported Windows failure is resolved in the actual emulator.
