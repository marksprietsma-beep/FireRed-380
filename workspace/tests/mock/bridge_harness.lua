-- Execute the real bridge against deterministic mGBA/socket doubles. No I/O.
local source = assert(arg[1], "bridge source required")
local count = 0
local function test(name, fn)
  local ok, err = pcall(fn)
  if not ok then io.stderr:write("FAIL " .. name .. ": " .. tostring(err) .. "\n"); os.exit(1) end
  count = count + 1
  print("PASS " .. name)
end
local function boot(options)
  options = options or {}
  local b = {keys = 0, frame = 0, cb = {}, nextid = 1, logs = {}, files = {}, paths = {}}
  local env = setmetatable({}, {__index = _G})
  b.env = env
  env.FIRERED_BRIDGE_OUTPUT_DIR = options.no_output and nil or "C:/disposable/output"
  if options.no_output then env.FIRERED_BRIDGE_OUTPUT_DIR = nil end
  env.FIRERED_BRIDGE_ALLOW_STATES = options.states
  env.console = {log = function() end, error = function(_, err) b.logs[#b.logs+1] = err end}
  env.io = {open = function(path) if b.files[path] then return {close=function() end, read=function() return "\137PNG\r\n\26\n" end} end; return nil, "not found", 2 end}
  env.emu = {
    currentFrame = function() if b.frame_error then error("frame failed") end; return b.frame end,
    addKeys = function(_, keys) b.keys = b.keys | keys end,
    clearKeys = function(_, keys)
      if options.clear_fail then error("clearKeys failed") end
      b.keys = b.keys & ~keys
    end,
    setKeys = function(_, keys) b.keys = keys end,
    getKeys = function() return b.keys end,
    read8 = function() return 1 end, read16 = function() return 2 end,
    read32 = function() return 3 end, readRange = function(_, a, n) return string.rep("a", n) end,
    screenshot = function(_, path)
      b.paths[#b.paths+1] = path
      if not options.screenshot_fail then b.files[path] = true end
    end,
    saveStateFile = function(_, path, flags) assert(flags == 0); b.paths[#b.paths+1] = path; return true end,
    loadStateFile = function(_, path, flags) assert(flags == 0); b.paths[#b.paths+1] = path; return true end,
  }
  env.callbacks = {
    add = function(_, event, cb)
      if options.callback_throw then error("register failed") end
      if options.callback_nil then return nil end
      local id = b.nextid; b.nextid = id + 1; b.cb[id] = cb; return id
    end,
    remove = function(_, id, extra)
      assert(type(id) == "number" and extra == nil, "remove takes ONE id")
      if options.remove_throw then error("remove failed") end
      b.cb[id] = nil
    end,
  }
  local function sock(server)
    local s = {handlers = {}, input = {}, output = "", closed = false,
               receive_calls = 0, empty_reads = 0}
    function s:add(event, cb)
      if options.socket_callback_fail then error("socket callback failed") end
      self.handlers[event] = cb; return 1
    end
    function s:listen() if options.listen_fail then return nil, "listen failed" end; return 1 end
    function s:accept() return table.remove(self.input, 1) end
    function s:hasdata()
      if self.readiness_error then return nil, self.readiness_error end
      return #self.input > 0 or self.eof == true or self.receive_error ~= nil
    end
    function s:receive(maxBytes)
      self.receive_calls = self.receive_calls + 1
      if self.receive_error then
        local err = self.receive_error; self.receive_error = nil
        return nil, err
      end
      if #self.input > 0 then
        local chunk = table.remove(self.input, 1)
        if #chunk > maxBytes then
          table.insert(self.input, 1, chunk:sub(maxBytes + 1))
          chunk = chunk:sub(1, maxBytes)
        end
        return chunk
      end
      self.empty_reads = self.empty_reads + 1
      if self.eof then return nil, "disconnected" end
      return nil, options.empty_read_error or "again"
    end
    function s:send(data, i)
      assert(not self.closed, "sent after close")
      if options.send_fail then return nil, "again" end
      i = i or 1
      local last = math.min(#data, i + (options.partial_send or #data) - 1)
      self.output = self.output .. data:sub(i, last)
      return last
    end
    function s:close() self.keys_on_close = b.keys; self.closed = true end
    return s
  end
  env.socket = {ERRORS = {AGAIN = "again"}, bind = function(host, port)
    assert(host == "127.0.0.1" and port == 8888)
    if options.bind_fail then return nil, "bind failed" end
    b.server = sock(true); return b.server
  end}
  b.ok, b.err = pcall(assert(loadfile(source, "t", env)))
  function b:connect()
    local client = sock(false)
    table.insert(self.server.input, client)
    self.server.handlers.received()
    return client
  end
  function b:send(client, text)
    table.insert(client.input, text)
    client.handlers.received()
    return client.output
  end
  function b:cmd(text)
    local c = self:connect()
    self:send(c, text .. "<|END|>")
    return c.output:gsub("<|END|>$", ""), c
  end
  function b:tick(frame)
    self.frame = frame
    local copy = {}; for id, cb in pairs(self.cb) do copy[id] = cb end
    for _, cb in pairs(copy) do cb() end
  end
  return b
end
local function good(b) assert(b.ok, b.err); return b end
local function is_error(reply) assert(reply:match("^<|ERROR|>"), reply) end

test("bootstrap/version/endpoint and legacy commands", function()
  local b = good(boot())
  assert(b:cmd("bridge.version") == "0.3.1")
  assert(b:cmd("bridge.ping") == "pong")
  assert(b:cmd("bridge.info"):find("host=127.0.0.1;port=8888;callbacks=ready", 1, true))
  assert(b:cmd("bridge.read8 0x0") == "1")
  assert(b:cmd("bridge.read16,0x3007000") == "2")
  assert(b:cmd("bridge.read32,0x3007000") == "3")
  assert(b:cmd("bridge.readRangeHex,0,2") == "6161")
  assert(b:cmd("bridge.keys") == "0x00000000")
  assert(b:cmd("bridge.holdKeys A Down 12"):match("^<|OK|>"))
  b:tick(1); assert(b.keys == 0x81)
  b:cmd("bridge.clearAll"); assert(b.keys == 0)
end)
test("partial requests, combined replies and partial sends", function()
  local b = good(boot({partial_send=2}))
  local c = b:connect()
  assert(b:send(c, "bridge.pi") == "")
  local reply = b:send(c, "ng<|END|>bridge.unknown<|END|>bridge.ping<|END|>")
  assert(reply == "pong<|END|><|ERROR|> unknown cmd: bridge.unknown<|END|>pong<|END|>")
end)
test("Windows unknown error on idle receive is avoided across version/info/ping/frame", function()
  local b = good(boot({empty_read_error="unknown error"}))
  b.frame = 42
  local c = b:connect()
  for _, command in ipairs({"bridge.version", "bridge.info", "bridge.ping", "bridge.frame"}) do
    b:send(c, command .. "<|END|>")
    assert(not c.closed, "an unnecessary idle read closed the connection")
  end
  assert(c.output:sub(-#"pong<|END|>42<|END|>") == "pong<|END|>42<|END|>")
  assert(c.receive_calls == 4 and c.empty_reads == 0)
  assert(#b.logs == 0 and not b.server.closed)
end)
test("stale received event with no readable bytes does not receive or disconnect", function()
  local b = good(boot({empty_read_error="unknown error"})); local c = b:connect()
  c.handlers.received()
  assert(c.receive_calls == 0 and not c.closed and #b.logs == 0)
end)
test("partial command and split marker survive idle callbacks", function()
  local b = good(boot({empty_read_error="unknown error"})); local c = b:connect()
  b.frame = 73
  assert(b:send(c, "bridge.fr") == "")
  c.handlers.received() -- no new bytes: retain partial command
  assert(b:send(c, "ame<|EN") == "")
  c.handlers.received() -- retain partial delimiter too
  assert(b:send(c, "D|>bridge.ping<|END|>") == "73<|END|>pong<|END|>")
  assert(c.receive_calls == 3 and c.empty_reads == 0 and not c.closed)
end)
test("32-read budget leaves readable requests for the next callback", function()
  local b = good(boot({empty_read_error="unknown error"})); local c = b:connect()
  for _ = 1, 33 do table.insert(c.input, "bridge.ping<|END|>") end
  c.handlers.received()
  assert(c.receive_calls == 32 and #c.input == 1 and not c.closed)
  assert(c.output == string.rep("pong<|END|>", 32))
  c.handlers.received()
  assert(c.receive_calls == 33 and c.empty_reads == 0)
  assert(c.output == string.rep("pong<|END|>", 33))
end)
test("message-size limit survives a partial message spanning callback budgets", function()
  local b = good(boot()); local c = b:connect()
  for _ = 1, 32 do table.insert(c.input, string.rep("x", 4096)) end
  table.insert(c.input, "x")
  c.handlers.received()
  assert(c.receive_calls == 32 and #c._buf == 131072 and not c.closed)
  c.handlers.received()
  assert(c.receive_calls == 33 and c.closed and not b.server.closed)
  assert(b:cmd("bridge.ping") == "pong")
end)
test("readiness errors close only the affected client and are logged", function()
  local b = good(boot()); local c = b:connect()
  c.readiness_error = "unknown error"
  c.handlers.received()
  assert(c.closed and c.receive_calls == 0 and #b.logs == 1)
  assert(b.logs[1]:find("unknown error", 1, true))
  assert(not b.server.closed and b:cmd("bridge.ping") == "pong")
end)
test("transient readiness error preserves partial input", function()
  local b = good(boot()); local c = b:connect()
  b:send(c, "bridge.pi")
  local reads = c.receive_calls
  c.readiness_error = "again"; c.handlers.received()
  assert(not c.closed and c.receive_calls == reads and c._buf == "bridge.pi")
  c.readiness_error = nil
  assert(b:send(c, "ng<|END|>") == "pong<|END|>")
end)
test("readiness/read race returning AGAIN preserves connection and buffer", function()
  local b = good(boot()); local c = b:connect()
  b:send(c, "bridge.pi")
  c.receive_error = "again"; c.handlers.received()
  assert(not c.closed and c._buf == "bridge.pi" and #b.logs == 0)
  assert(b:send(c, "ng<|END|>") == "pong<|END|>")
end)
test("readable EOF closes only the peer; genuine receive errors are not ignored", function()
  for _, err in ipairs({"disconnected", "connection reset", "unknown error"}) do
    local b = good(boot()); local c = b:connect()
    if err == "disconnected" then c.eof = true else c.receive_error = err end
    c.handlers.received()
    assert(c.closed and c.receive_calls == 1 and not b.server.closed)
    assert(#b.logs == (err == "disconnected" and 0 or 1))
    assert(b:cmd("bridge.ping") == "pong")
  end
end)
test("single press exact release", function()
  local b = good(boot()); b:cmd("bridge.holdKeys,A,3")
  b:tick(1); assert(b.keys == 1)
  b:tick(3); assert(b.keys == 1)
  b:tick(4); assert(b.keys == 0)
end)
test("overlapping ownership retains shared key", function()
  local b = good(boot()); b:cmd("bridge.holdKeys,A;Down,3"); b:tick(1)
  b:cmd("bridge.holdKeys,A,5"); b:tick(2)
  b:tick(4); assert(b.keys == 1, "first expiry cleared a later owner's key")
  b:tick(7); assert(b.keys == 0)
end)
test("clearAll cancels pending and active holds", function()
  local b = good(boot()); b:cmd("bridge.holdKeys,A,3"); b:tick(1)
  b:cmd("bridge.holdKeys,Down,4"); b:cmd("bridge.clearAll")
  b:tick(2); b:tick(20); assert(b.keys == 0)
end)
test("duration validation and bounds", function()
  local b = good(boot())
  for _, v in ipairs({"0", "-1", "1.5", "301", "nan", "inf", "nope", ""}) do
    is_error(b:cmd("bridge.holdKeys,A," .. v))
  end
  b:tick(1); assert(b.keys == 0)
  assert(b:cmd("bridge.holdKeys,A,300"):match("^<|OK|>"))
  is_error(b:cmd("bridge.holdKeys,A;garbage,12"))
end)
test("frame rewind clears keys", function()
  local b = good(boot()); b:cmd("bridge.holdKeys,A,300"); b:tick(100)
  b:tick(1); assert(b.keys == 0)
end)
test("shutdown releases, acknowledges before disconnect, removes correct callback", function()
  local b = good(boot()); b:cmd("bridge.holdKeys,A;Down,300"); b:tick(1)
  local reply, c = b:cmd("bridge.shutdown")
  assert(reply == "bye"); assert(c.closed and c.keys_on_close == 0)
  assert(b.server.closed and b.keys == 0 and next(b.cb) == nil)
end)
test("shutdown during partial-send failure still releases", function()
  local b = good(boot({send_fail=true})); b:cmd("bridge.holdKeys,A,300"); b:tick(1)
  b:cmd("bridge.shutdown"); assert(b.keys == 0 and b.server.closed)
end)
test("registration nil/exception fails closed", function()
  for _, options in ipairs({{callback_nil=true}, {callback_throw=true}}) do
    local b = boot(options)
    assert(not b.ok and not b.server and b.keys == 0)
  end
end)
test("socket callback and listen/bind failures roll back", function()
  for _, options in ipairs({{socket_callback_fail=true}, {listen_fail=true}, {bind_fail=true}}) do
    local b = boot(options)
    assert(not b.ok and b.keys == 0 and next(b.cb) == nil)
    assert(not b.server or b.server.closed)
  end
end)
test("frame callback failure closes bridge and clears held keys", function()
  local b = good(boot()); b:cmd("bridge.holdKeys,A,300"); b:tick(1)
  b.frame_error = true; b:tick(2)
  assert(b.keys == 0 and b.server.closed and next(b.cb) == nil)
end)
test("callback removal failure logged, holds still released", function()
  local b = good(boot({remove_throw=true})); b:cmd("bridge.holdKeys,A,300"); b:tick(1)
  b:cmd("bridge.shutdown"); assert(b.keys == 0 and #b.logs > 0)
  b:tick(2); assert(b.keys == 0)
end)
test("basename policy, CSV quotes, traversal, protected extensions and overwrite", function()
  local b = good(boot())
  assert(b:cmd([[bridge.screenshot,"capture, O'Brien.png"]]):match("^<|OK|>"))
  assert(b.paths[1] == "C:/disposable/output/capture, O'Brien.png")
  for _, name in ipairs({"../test.png", "C:/test.png", "test.sav", "test.png:foo", "CON.png", "a\\b.png"}) do
    is_error(b:cmd('bridge.screenshot,"' .. name .. '"'))
  end
  b.files["C:/disposable/output/existing.png"] = true
  is_error(b:cmd("bridge.screenshot,existing.png"))
  is_error(b:cmd([[bridge.screenshot,"unterminated.png]]))
  is_error(b:cmd([[bridge.screenshot,"a""b.png"]])) -- valid CSV, unsafe Windows quote
  is_error(b:cmd("bridge.saveStateFile,test.mgbs"))
  is_error(b:cmd("bridge.loadStateFile,test.mgbs"))
end)
test("explicit state opt-in remains sandboxed", function()
  local b = good(boot({states=true}))
  assert(b:cmd("bridge.saveStateFile,test.mgbs"):match("^<|OK|>"))
  b.files["C:/disposable/output/test.mgbs"] = true
  assert(b:cmd("bridge.loadStateFile,test.mgbs"):match("^<|OK|>"))
  is_error(b:cmd("bridge.saveStateFile,test.mgbs"))
  is_error(b:cmd("bridge.loadStateFile,original.sav"))
end)
test("reload rejected and disabled output fails closed", function()
  local b = good(boot())
  local ok = pcall(assert(loadfile(source, "t", b.env))); assert(not ok)
  local c = good(boot()); c.env.FIRERED_BRIDGE_OUTPUT_DIR = nil
  -- Configuration is captured at load; changing the global cannot alter it.
  assert(c:cmd("bridge.outputDir") == "C:/disposable/output")
end)
test("clearKeys failure uses setKeys fallback before ACK", function()
  local b = good(boot({clear_fail=true})); b:cmd("bridge.holdKeys,A,300"); b:tick(1)
  local reply = b:cmd("bridge.shutdown")
  assert(reply == "bye" and b.keys == 0)
end)
test("missing output or silent screenshot failure is reported", function()
  is_error(good(boot({no_output=true})):cmd("bridge.screenshot,test.png"))
  is_error(good(boot({screenshot_fail=true})):cmd("bridge.screenshot,test.png"))
end)
print("Lua bridge mock cases: " .. count)
