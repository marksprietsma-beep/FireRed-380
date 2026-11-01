-- ============================================================
-- FireRed-380  minimal socket bridge (mGBA scripting console)
-- Version: 0.1  (2026-11-01)
-- Transport: TCP socket inside stock mGBA (no fork required).
-- Protocol : text, one command per request, "<|END|>" framing.
--   Request :  "<cmd>,<a1>,<a2>...<|END|>"   (comma separated args)
--   Reply   :  "<payload><|END|>"            (payload = "<|ERROR|>" on failure)
--
-- Command surface (INTENTIONALLY minimal, per spec Phase 0/2):
--   bridge.ping                 ->  "pong"
--   bridge.frame                ->  current frame counter (loop sanity)
--   bridge.screenshot <path>    ->  writes a PNG of the GBA framebuffer to <path>
--   bridge.read8   <addr>       ->  byte value
--   bridge.read16  <addr>       ->  halfword value
--   bridge.read32  <addr>       ->  word value
--   bridge.readRangeHex <addr> <len>  ->  hex string of a memory block (state fallback)
--   bridge.keys                 ->  currently-held key bitmask (control verification)
--   bridge.holdKeys <A;B;...> [frames]  ->  discrete press for N frames (default 12)
--   bridge.clearAll             ->  release every GBA key (safety)
--   bridge.saveStateFile <path> ->  mGBA savestate checkpoint (NOT a save-game cheat)
--
-- SAFETY: this script exposes READ-ONLY observation and discrete button presses.
-- It does NOT modify save RAM, does NOT inject memory, does NOT download anything.
-- ============================================================

local port = 8888
local END_MARKER = "<|END|>"
local OK = "<|OK|>"
local ERR = "<|ERROR|>"

-- GBA key bit indices (standard mGBA keymask)
local KEY_BIT = {
  A = 0, B = 1, Select = 2, Start = 3,
  Right = 4, Left = 5, Up = 6, Down = 7,
  R = 8, L = 9,
}

-- ---------- logging ----------
local function log(msg)
  local prefix = "[firebridge] "
  if console and console.log then
    console.log(prefix .. tostring(msg))
  elseif print then
    print(prefix .. tostring(msg))
  end
end
local function logErr(msg)
  local line = "[firebridge ERROR] " .. tostring(msg)
  if console and console.error then
    console.error(line)
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
  while not server do
    local err
    server, err = socket.bind(nil, port)
    if err then
      if err == socket.ERRORS.ADDRESS_IN_USE then
        log("port " .. port .. " in use, trying " .. (port + 1))
        port = port + 1
      else
        logErr("bind failed: " .. tostring(err))
        break
      end
    else
      local ok, listErr = server:listen()
      if not ok then
        server:close(); server = nil
        logErr("listen failed: " .. tostring(listErr))
        break
      end
      log("READY on port " .. port)
      server:add("received", accept_connection)
    end
  end
end

local function close_connection(id)
  local sock = conns[id]
  conns[id] = nil
  if sock and sock.close then sock:close() end
end

accept_connection = function()
  local sock, err = server:accept()
  if err then
    logErr("accept failed: " .. tostring(err))
    return
  end
  local id = next_id
  next_id = id + 1
  conns[id] = sock
  log("client connected (id " .. id .. ")")
  sock:add("received", function() on_received(id) end)
  sock:add("error", function() close_connection(id) end)
end

on_received = function(id)
  local sock = conns[id]
  if not sock then return end
  sock._buf = sock._buf or ""
  while true do
    local chunk, err = sock:receive(4096)
    if chunk then
      sock._buf = sock._buf .. chunk
      while true do
        local s, e = sock._buf:find(END_MARKER, 1, true)
        if not s then break end
        local msg = sock._buf:sub(1, s - 1)
        sock._buf = sock._buf:sub(e + 1)
        local payload = dispatch(msg)
        sock:send(tostring(payload) .. END_MARKER)
      end
    elseif err then
      if err ~= socket.ERRORS.AGAIN then
        if err == socket.ERRORS.DISCONNECTED then
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
      local idx = KEY_BIT[key] or KEY_BIT[key:upper()]
      if idx then
        mask = mask | (1 << idx); any = true
      else
        log("unknown key ignored: " .. tostring(key))
      end
    end
  end
  return mask, any
end

-- ---------- windowed discrete key presses ----------
local press_queue = {}
local DEFAULT_HOLD_FRAMES = 12
local function enqueue_press(mask, frames)
  local start = emu:currentFrame()
  table.insert(press_queue, { mask = mask, start = start, stop = start + frames + 1, done = false })
end
local function step_presses()
  local now = emu:currentFrame()
  local keep = {}
  for _, p in ipairs(press_queue) do
    if not p.done and now >= p.start and now <= p.stop then
      emu:addKeys(p.mask); p.done = true
    elseif now > p.stop then
      emu:clearKeys(p.mask)
    else
      table.insert(keep, p)
    end
  end
  press_queue = keep
end
local function install_frame_callback()
  if not callbacks then return end
  if callbacks.add then
    callbacks:add("frame", step_presses)
  end
end

-- ---------- command dispatch ----------
dispatch = function(msg)
  -- strip trailing commas / whitespace
  msg = msg:match("^%s*(.-)%s*$")

  if msg == "" then
    return OK .. "(empty)"
  end

  local cmd, args = msg:match("^(%S+)%s+(.*)$")
  local argv = {}
  if cmd then
    for a in args:gmatch("%S+") do table.insert(argv, a) end
  else
    cmd = msg
  end

  local ok, result = pcall(function()
    if cmd == "bridge.ping" then
      return "pong"
    elseif cmd == "bridge.frame" then
      return tostring(emu:currentFrame())
    elseif cmd == "bridge.screenshot" then
      local path = argv[1]
      if not path then return ERR .. " sshot: path required" end
      local ok2 = emu:screenshot(path)
      return (ok2 == true or ok2) and (OK .. " sshot->" .. tostring(path)) or (ERR .. " sshot failed")
    elseif cmd == "bridge.read8" then
      return tostring(emu:read8(parse_addr(argv[1])))
    elseif cmd == "bridge.read16" then
      return tostring(emu:read16(parse_addr(argv[1])))
    elseif cmd == "bridge.read32" then
      return tostring(emu:read32(parse_addr(argv[1])))
    elseif cmd == "bridge.readRangeHex" then
      local a, l = parse_addr(argv[1]), tonumber(argv[2])
      if not a or not l then return ERR .. " readRange needs <addr> <len>" end
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
      local spec = argv[1] or ""
      if argv[2] and not argv[2]:match("^%d+$") then
        spec = (spec ~= "") and (spec .. ";" .. argv[2]) or argv[2]
      end
      local frames = tonumber(argv[2]) or (tonumber(argv[3]) or DEFAULT_HOLD_FRAMES)
      local mask, any = to_bitmask(spec)
      if not any then return ERR .. " holdKeys: unknown key(s): " .. tostring(spec) end
      enqueue_press(mask, frames)
      return OK .. " hold " .. tostring(spec) .. " " .. tostring(frames) .. "f"
    elseif cmd == "bridge.clearAll" then
      emu:clearKeys(0x3FF) -- all 10 GBA keys
      return OK .. " cleared all keys"
    elseif cmd == "bridge.saveStateFile" then
      local path = argv[1]
      if not path then return ERR .. " savestate: path required" end
      return emu:saveStateFile(path) and (OK .. " savestate->" .. tostring(path)) or (ERR .. " savestate failed")
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
install_frame_callback()
bind_and_listen()
log("FireRed-380 bridge installed (minimal observation/control surface).")
