-- ============================================================
-- FireRed-380  minimal socket bridge (mGBA scripting console)
-- Version: 0.2 (2026-11-01; historical live-tested version)
-- Transport: TCP socket inside stock mGBA (no fork required).
-- Protocol : text, one command per request, "<|END|>" framing.
--   Request :  "<cmd>,<a1>,<a2>...<|END|>"   (comma-separated args)
--              Legacy whitespace-separated arguments are also accepted.
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
-- Its TCP listener is restricted to 127.0.0.1 (this PC only).
-- ============================================================

local port = 8888
local END_MARKER = "<|END|>"
local OK = "<|OK|>"
local ERR = "<|ERROR|>"

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
    return
  end

  local ok, listErr = server:listen()
  if not ok then
    server:close()
    server = nil
    logErr("listen failed: " .. tostring(listErr))
    return
  end

  log("READY on 127.0.0.1:" .. port)
  server:add("received", accept_connection)
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
        local sent, sendErr = send_all(sock, tostring(payload) .. END_MARKER)
        if not sent then
          logErr("client " .. id .. " send failed: " .. tostring(sendErr))
          close_connection(id)
          return
        end
      end
    elseif err then
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
  table.insert(press_queue, { mask = mask, start = start, stop = start + frames, done = false })
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

  local function trim(s)
    return (s:match("^%s*(.-)%s*$"))
  end

  local function split_csv(s)
    local out, buf = {}, {}
    local quote = nil
    for i = 1, #s do
      local ch = s:sub(i, i)
      if quote then
        if ch == quote then
          quote = nil
        else
          buf[#buf + 1] = ch
        end
      elseif ch == "'" or ch == '"' then
        quote = ch
      elseif ch == "," then
        out[#out + 1] = trim(table.concat(buf))
        buf = {}
      else
        buf[#buf + 1] = ch
      end
    end
    out[#out + 1] = trim(table.concat(buf))
    return out
  end

  local cmd, rest = msg:match("^%s*([^,%s]+)%s*(.*)$")
  local argv = {}
  if not cmd then
    cmd = msg
  elseif rest and rest ~= "" then
    if rest:sub(1, 1) == "," then
      argv = split_csv(rest:sub(2))
    elseif cmd == "bridge.screenshot" or cmd == "bridge.saveStateFile" then
      -- Preserve spaces in a Windows file path when using legacy syntax.
      argv[1] = trim(rest)
    else
      for a in rest:gmatch("%S+") do argv[#argv + 1] = a end
    end
  end

  local ok, result = pcall(function()
    if cmd == "bridge.ping" then
      return "pong"
    elseif cmd == "bridge.frame" then
      return tostring(emu:currentFrame())
    elseif cmd == "bridge.screenshot" then
      local path = argv[1]
      if not path then return ERR .. " sshot: path required" end
      -- mGBA's screenshot method writes the file and has no success return value.
      -- If it fails, the surrounding pcall catches the runtime error.
      emu:screenshot(path)
      return OK .. " sshot->" .. tostring(path)
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
      press_queue = {}
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
