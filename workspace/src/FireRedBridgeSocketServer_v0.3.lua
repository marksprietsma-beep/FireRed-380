-- ============================================================
-- FireRed-380  minimal socket bridge (mGBA scripting console)
-- Version: 0.3.1 (reliability hardening; live verification pending)
-- Transport: TCP socket inside stock mGBA (no fork required).
-- Protocol : text, one command per request, "<|END|>" framing.
--   Request :  "<cmd>,<a1>,<a2>...<|END|>"   (comma-separated args)
--              Legacy whitespace-separated arguments are also accepted.
--   Reply   :  "<payload><|END|>"            (payload = "<|ERROR|>" on failure)
--
-- v0.3 changes vs v0.2:
--   * FIX (T5 battery): v0.2's step_presses removed the queue entry on the
--     addKeys frame, so the "now > p.stop"/clearKeys branch was unreachable
--     and held keys were never released. v0.3 uses a two-phase entry
--     (added flag): add on start frame, RELEASE on the frame after stop,
--     then drop the entry.
--   * NEW bridge.version          -> "0.3" (lets the controller verify which
--     bridge generation actually owns port 8888 after a reload)
--   * NEW bridge.loadStateFile <path> (restore an in-session position)
--   * NEW bridge.shutdown         -> close all clients + server, remove the
--     frame callback, so a future reload can rebind the port cleanly
--   * READY log line now includes the bridge version
--
-- v0.3.1: bounded holds, per-key ownership, fail-closed callbacks,
-- ACK-before-close shutdown, CSV quote escaping and opt-in file sandbox.
-- Version 0.3.1 is a candidate: no live emulator pass is claimed.
-- Command surface (existing names retained; file commands accept basenames):
--   bridge.ping                 ->  "pong"
--   bridge.version              ->  "0.3"
--   bridge.frame                ->  current frame counter (loop sanity)
--   bridge.screenshot <path>    ->  writes a PNG of the GBA framebuffer to <path>
--   bridge.read8   <addr>       ->  byte value
--   bridge.read16  <addr>       ->  halfword value
--   bridge.read32  <addr>       ->  word value
--   bridge.readRangeHex <addr> <len>  ->  hex string of a memory block (state fallback)
--   bridge.keys                 ->  currently-held key bitmask (control verification)
--   bridge.holdKeys <A;B;...> [frames]  ->  discrete press for N frames (default 12, auto-release)
--   bridge.clearAll             ->  release every GBA key + cancel queued presses (safety)
--   bridge.saveStateFile <path> ->  mGBA savestate checkpoint (NOT a save-game cheat)
--   bridge.loadStateFile <path> ->  restore a savestate checkpoint position
--   bridge.shutdown             ->  stop the bridge (clients + server + frame cb)
--
-- SAFETY: this script exposes READ-ONLY observation and discrete button presses.
-- It does NOT modify save RAM, does NOT inject memory, does NOT download anything.
-- Its TCP listener is restricted to 127.0.0.1 (this PC only).
-- ============================================================

local port = 8888
local version = "0.3.1"
local END_MARKER = "<|END|>"
local OK = "<|OK|>"
local ERR = "<|ERROR|>"
local MAX_HOLD_FRAMES = 300
local MAX_MESSAGE_BYTES = 131072
-- Set once in the scripting console before loading. No default file access.
-- This must be a new, owner-approved disposable directory, without reparse
-- points/symlinks. Only basenames are accepted over TCP, never arbitrary paths.
local output_dir = FIRERED_BRIDGE_OUTPUT_DIR
local allow_states = FIRERED_BRIDGE_ALLOW_STATES == true
local frameCbId, stop_bridge, clear_keys
local shutting_down, stopped = false, false
local callback_ready = false
if FIRERED_BRIDGE_RUNNING then error("bridge already loaded; shut it down first") end

-- GBA key bit indices (standard mGBA keymask)
local KEY_BIT = {
  A = 0, B = 1, SELECT = 2, START = 3,
  RIGHT = 4, LEFT = 5, UP = 6, DOWN = 7,
  R = 8, L = 9,
}

-- ---------- logging ----------
local function log(msg)
  local prefix = "[firebridge] "
  if console and console.log then
    console:log(prefix .. tostring(msg))
  elseif print then
    print(prefix .. tostring(msg))
  end
end
local function logErr(msg)
  local line = "[firebridge ERROR] " .. tostring(msg)
  if console and console.error then
    console:error(line)
  else
    print(line)
  end
end

-- ---------- socket plumbing ----------
local server = nil
local conns = {}      -- id -> sock
local next_id = 1

-- forward declarations (local functions cross-reference before definition)
local accept_connection, on_received, dispatch

local function bind_and_listen()
  -- The Python controller runs on this same PC, so do not expose the
  -- emulator-control socket to other devices on the network.
  local err
  server, err = socket.bind("127.0.0.1", port)
  if not server then
    logErr("bind failed on 127.0.0.1:" .. port .. ": " .. tostring(err))
    error("bridge bind failed: " .. tostring(err))
  end

  local ok, listErr = server:listen()
  if not ok then
    server:close()
    server = nil
    logErr("listen failed: " .. tostring(listErr))
    error("bridge listen failed: " .. tostring(listErr))
  end

  assert(server:add("received", function()
    local ok, err = pcall(accept_connection)
    if not ok then logErr(err); stop_bridge() end
  end), "server callback registration failed")
  assert(server:add("error", function() stop_bridge() end), "server error callback failed")
  log("READY on 127.0.0.1:" .. port .. " v" .. version)
end

local function close_connection(id)
  local sock = conns[id]
  conns[id] = nil
  if sock and sock.close then sock:close() end
end

local function send_all(sock, data)
  local sent = 0
  while sent < #data do
    -- mGBA returns the last string index written when an offset is supplied.
    local last, err = sock:send(data, sent + 1)
    if not last then return false, err end
    if last <= sent then return false, "socket send made no progress" end
    sent = last
  end
  return true
end

accept_connection = function()
  local sock, err = server:accept()
  if not sock then
    logErr("accept failed: " .. tostring(err))
    return
  end
  local id = next_id
  next_id = id + 1
  conns[id] = sock
  log("client connected (id " .. id .. ")")
  local ok, registerErr = pcall(function()
    assert(sock:add("received", function()
      local success, err = pcall(on_received, id)
      if not success then logErr(err); stop_bridge() end
    end), "receive callback registration failed")
    assert(sock:add("error", function() close_connection(id) end), "error callback registration failed")
  end)
  if not ok then close_connection(id); error(registerErr) end
end

on_received = function(id)
  local sock = conns[id]
  if not sock then return end
  sock._buf = sock._buf or ""
  -- Bound work per emulator frame even if a peer continuously sends data.
  for _ = 1, 32 do
    local chunk, err = sock:receive(4096)
    if chunk and #chunk > 0 then
      sock._buf = sock._buf .. chunk
      if #sock._buf > MAX_MESSAGE_BYTES then close_connection(id); return end
      while true do
        local s, e = sock._buf:find(END_MARKER, 1, true)
        if not s then break end
        local msg = sock._buf:sub(1, s - 1)
        sock._buf = sock._buf:sub(e + 1)
        local payload = dispatch(msg)
        local sent, sendErr = send_all(sock, tostring(payload) .. END_MARKER)
        if not sent then
          logErr("client " .. id .. " send failed: " .. tostring(sendErr))
          if shutting_down then stop_bridge() else close_connection(id) end
          return
        end
        if shutting_down then stop_bridge(); return end
      end
    else
      if err ~= socket.ERRORS.AGAIN then
        if err == "disconnected" then
          log("client " .. id .. " disconnected")
        else
          logErr("client " .. id .. " error: " .. tostring(err))
        end
        close_connection(id)
      end
      return
    end
  end
end

-- ---------- argument helpers ----------
local function parse_addr(v)
  if not v then return nil end
  local s = v:match("%S+") or ""
  if s:match("^0[xX]") then
    return tonumber(s:sub(3), 16)      -- explicit hex
  end
  if s:match("^%d+$") then
    return tonumber(s, 10)             -- plain decimal
  end
  if s:match("^[0-9a-fA-F]+$") then
    return tonumber(s, 16)             -- bare hex
  end
  return nil
end
local function to_bitmask(spec)
  local mask = 0
  local any = false
  for name in (spec or ""):gmatch("[^%;]+") do
    local key = name:match("%S+")
    if key then
      local idx = KEY_BIT[key:upper()]
      if idx then
        mask = mask | (1 << idx); any = true
      else
        return 0, false
      end
    end
  end
  return mask, any
end

-- ---------- windowed discrete key presses ----------
local press_queue, owners = {}, {}
local DEFAULT_HOLD_FRAMES = 12
local last_frame = nil
clear_keys = function()
  press_queue, owners = {}, {}
  local ok = pcall(function() emu:clearKeys(0x3FF) end)
  if not ok or emu:getKeys() & 0x3FF ~= 0 then
    -- Independent supported key API fallback; still verify rather than assume.
    emu:setKeys(0)
  end
  if emu:getKeys() & 0x3FF ~= 0 then error("key release verification failed") end
end

stop_bridge = function()
  stopped, callback_ready = true, false
  -- Release BEFORE removing callbacks or disconnecting clients. Attempt all
  -- cleanup steps even if one API fails, and surface each failure in the log.
  local released, releaseErr = pcall(clear_keys)
  if not released then logErr("EMERGENCY key release failed: " .. tostring(releaseErr)) end
  for id, _ in pairs(conns) do
    local ok, err = pcall(close_connection, id)
    if not ok then logErr(err) end
  end
  if server then
    local ok, err = pcall(function() server:close() end)
    if not ok then logErr(err) end
    server = nil
  end
  if frameCbId then
    local ok, err = pcall(function() callbacks:remove(frameCbId) end)
    if not ok then logErr("callback removal failed: " .. tostring(err)) end
    frameCbId = nil
  end
  FIRERED_BRIDGE_RUNNING = false
end

local function enqueue_press(mask, frames)
  if stopped or not callback_ready then error("frame callback unavailable") end
  if #press_queue >= 32 then error("hold queue full") end
  table.insert(press_queue, { mask = mask, frames = frames, added = false })
end

local function step_presses()
  if stopped then return end
  local now = emu:currentFrame()
  if last_frame and now < last_frame then clear_keys() end
  last_frame = now
  local keep = {}
  for _, p in ipairs(press_queue) do
    if not p.added then
      p.added, p.stop = true, now + p.frames
      for bit = 0, 9 do
        local mask = 1 << bit
        if p.mask & mask ~= 0 then owners[bit] = (owners[bit] or 0) + 1 end
      end
      emu:addKeys(p.mask)
      keep[#keep + 1] = p
    elseif now >= p.stop then
      for bit = 0, 9 do
        local mask = 1 << bit
        if p.mask & mask ~= 0 then
          owners[bit] = owners[bit] - 1
          if owners[bit] == 0 then emu:clearKeys(mask) end
        end
      end
    else
      keep[#keep + 1] = p
    end
  end
  press_queue = keep
end

local function install_frame_callback()
  assert(callbacks and callbacks.add and callbacks.remove, "callback API unavailable")
  assert(emu and emu.addKeys and emu.clearKeys and emu.setKeys and emu.getKeys and emu.currentFrame,
         "required emulator key/frame API unavailable")
  frameCbId = callbacks:add("frame", function()
    local ok, err = pcall(step_presses)
    if not ok then logErr("frame callback failed: " .. tostring(err)); stop_bridge() end
  end)
  assert(type(frameCbId) == "number" and frameCbId > 0, "frame callback registration failed")
  callback_ready = true
end

local function safe_path(name, extension, writing)
  assert(type(output_dir) == "string" and output_dir:match("^[A-Za-z]:[/\\]"),
         "configure an absolute Windows output directory")
  assert(not output_dir:find("..", 1, true) and not output_dir:find("[^ -~]"), "unsafe output directory")
  assert(type(name) == "string" and #name <= 120 and #name > #extension, "invalid filename")
  -- ASCII-only filenames until Windows Unicode paths have been live-verified.
  assert(not name:find('[%c\\/:*?"<>|]') and not name:find("[^ -~]"), "unsafe filename")
  assert(name:sub(-#extension) == extension and not name:find("..", 1, true), "wrong extension or traversal")
  local stem = name:match("^([^%.]+)"):upper()
  assert(not stem:match("^CON$") and not stem:match("^PRN$") and not stem:match("^AUX$")
         and not stem:match("^NUL$") and not stem:match("^COM[0-9]$")
         and not stem:match("^LPT[0-9]$"), "reserved Windows filename")
  local path = output_dir:gsub("[\\/]$", "") .. "/" .. name
  local file, _, code = io.open(path, "rb")
  assert(file or code == 2, "cannot establish file absence (expected ENOENT)")
  if file then file:close() end
  assert(not writing or not file, "refusing to overwrite existing file")
  assert(writing or file, "state file does not exist")
  return path
end

-- ---------- command dispatch ----------
dispatch = function(msg)
  -- strip trailing commas / whitespace
  msg = msg:match("^%s*(.-)%s*$")

  if msg == "" then
    return OK .. "(empty)"
  end

  local function trim(s)
    return (s:match("^%s*(.-)%s*$"))
  end

  local function split_csv(s)
    local out, i = {}, 1
    while true do
      local buf, quote = {}, nil
      if s:sub(i, i) == '"' or s:sub(i, i) == "'" then
        quote = s:sub(i, i); i = i + 1
      end
      if quote then
        local closed = false
        while i <= #s do
          local ch = s:sub(i, i); i = i + 1
          if ch == quote then
            if s:sub(i, i) == quote then buf[#buf + 1] = quote; i = i + 1
            else closed = true; break end
          else buf[#buf + 1] = ch end
        end
        assert(closed, "unterminated quoted argument")
        assert(i > #s or s:sub(i, i) == ",", "characters after quoted argument")
        out[#out + 1] = table.concat(buf)
      else
        while i <= #s and s:sub(i, i) ~= "," do
          buf[#buf + 1] = s:sub(i, i); i = i + 1
        end
        out[#out + 1] = trim(table.concat(buf))
      end
      if i > #s then break end
      i = i + 1
    end
    return out
  end

  local parsed, cmd, argv = pcall(function()
    local cmd, rest = msg:match("^%s*([^,%s]+)%s*(.*)$")
    local argv = {}
    if not cmd then
      cmd = msg
    elseif rest and rest ~= "" then
      if rest:sub(1, 1) == "," then
        argv = split_csv(rest:sub(2))
      elseif cmd == "bridge.screenshot" or cmd == "bridge.saveStateFile"
            or cmd == "bridge.loadStateFile" then
        -- Preserve spaces in a Windows file path when using legacy syntax.
        argv[1] = trim(rest)
      else
        for a in rest:gmatch("%S+") do argv[#argv + 1] = a end
      end
    end

    return cmd, argv
  end)
  if not parsed then return ERR .. " malformed request: " .. tostring(cmd) end
  local ok, result = pcall(function()
    if stopped or shutting_down then return ERR .. " bridge stopping" end
    if cmd == "bridge.ping" then
      return "pong"
    elseif cmd == "bridge.version" then
      return version
    elseif cmd == "bridge.info" then
      return "version=" .. version .. ";host=127.0.0.1;port=" .. port
          .. ";callbacks=" .. (callback_ready and "ready" or "failed") .. ";maxHold=300;pathPolicy=basename"
    elseif cmd == "bridge.outputDir" then
      return output_dir or ""
    elseif cmd == "bridge.frame" then
      return tostring(emu:currentFrame())
    elseif cmd == "bridge.screenshot" then
      local path = safe_path(argv[1], ".png", true)
      -- 0.10.5 silently returns on open failure; verify the file explicitly.
      emu:screenshot(path)
      local file = assert(io.open(path, "rb"), "screenshot file missing")
      local signature = file:read(8); file:close()
      assert(signature == "\137PNG\r\n\26\n", "invalid screenshot file")
      return OK .. " sshot->" .. tostring(path)
    elseif cmd == "bridge.read8" then
      return tostring(emu:read8(parse_addr(argv[1])))
    elseif cmd == "bridge.read16" then
      return tostring(emu:read16(parse_addr(argv[1])))
    elseif cmd == "bridge.read32" then
      return tostring(emu:read32(parse_addr(argv[1])))
    elseif cmd == "bridge.readRangeHex" then
      local a, l = parse_addr(argv[1]), tonumber(argv[2])
      if not a or not l or l < 1 or l > 4096 or l % 1 ~= 0 then return ERR .. " invalid readRange" end
      local data = emu:readRange(a, l)
      local hex = {}
      for i = 1, #data do hex[i] = string.format("%02x", data:byte(i)) end
      return table.concat(hex)
    elseif cmd == "bridge.keys" then
      if emu.getKeys then
        return string.format("0x%08x", emu:getKeys())
      end
      return "n/a"
    elseif cmd == "bridge.holdKeys" then
      local spec, duration = argv[1] or "", argv[2]
      -- Retain legacy "A Down 12" form. Invalid durations never fall back.
      if argv[3] and KEY_BIT[(argv[2] or ""):upper()] then
        spec, duration = spec .. ";" .. argv[2], argv[3]
      elseif argv[3] then return ERR .. " unexpected hold arguments" end
      if #argv > 3 then return ERR .. " unexpected hold arguments" end
      local frames = duration == nil and DEFAULT_HOLD_FRAMES or tonumber(duration)
      if not frames or frames ~= frames or frames % 1 ~= 0 or frames < 1 or frames > MAX_HOLD_FRAMES then
        return ERR .. " frames must be an integer in 1..300"
      end
      local mask, any = to_bitmask(spec)
      if not any then return ERR .. " holdKeys: unknown key(s): " .. tostring(spec) end
      enqueue_press(mask, frames)
      return OK .. " hold " .. tostring(spec) .. " " .. tostring(frames) .. "f"
    elseif cmd == "bridge.clearAll" then
      clear_keys()
      return OK .. " cleared all keys"
    elseif cmd == "bridge.saveStateFile" then
      assert(allow_states, "savestate commands disabled")
      local path = safe_path(argv[1], ".mgbs", true)
      return emu:saveStateFile(path, 0) and (OK .. " savestate->" .. tostring(path)) or (ERR .. " savestate failed")
    elseif cmd == "bridge.loadStateFile" then
      assert(allow_states, "savestate commands disabled")
      local path = safe_path(argv[1], ".mgbs", false)
      clear_keys()
      local okLoad = emu:loadStateFile(path, 0)
      clear_keys() -- savestate core state must not restore an active input
      return okLoad and (OK .. " loaded->" .. tostring(path)) or (ERR .. " loadState failed: " .. tostring(path))
    elseif cmd == "bridge.shutdown" then
      clear_keys()
      shutting_down = true -- transport sends ACK before tearing down
      return "bye"
    else
      return ERR .. " unknown cmd: " .. tostring(cmd)
    end
  end)

  if not ok then
    logErr("dispatch error: " .. tostring(result))
    return ERR .. " " .. tostring(result)
  end
  return result
end

-- ---------- bootstrap ----------
local installed, installErr = pcall(function()
  install_frame_callback()
  bind_and_listen()
end)
if not installed then
  stop_bridge()
  error("bridge installation failed: " .. tostring(installErr))
end
FIRERED_BRIDGE_RUNNING = true
log("FireRed-380 bridge installed v" .. version .. " (live verification pending).")
