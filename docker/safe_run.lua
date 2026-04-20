-- Isolated execution: load user script with a restricted environment (Lua 5.4).
local path = arg[1]
if not path or path == "" then
  io.stderr:write("usage: lua5.4 safe_run.lua <file>\n")
  os.exit(1)
end

local f, err = io.open(path, "r")
if not f then
  io.stderr:write(tostring(err) .. "\n")
  os.exit(1)
end
local src = f:read("*a")
f:close()

local octapi = {}
function octapi.connect(host)
  print("[octapi.connect stub]", tostring(host))
  return {
    send = function(_, msg) print("[octapi.send stub]", tostring(msg)) end,
    close = function() print("[octapi.close stub]") end,
  }
end
function octapi.version()
  return "1.0.0"
end

local safe_env = {
  print = print,
  error = error,
  assert = assert,
  type = type,
  pairs = pairs,
  ipairs = ipairs,
  next = next,
  select = select,
  tonumber = tonumber,
  tostring = tostring,
  string = string,
  table = table,
  math = math,
  utf8 = utf8,
  octapi = octapi,
}

local fn, lerr = load(src, "@user", "t", safe_env)
if not fn then
  io.stderr:write(tostring(lerr) .. "\n")
  os.exit(1)
end

local ok, run_err = pcall(fn)
if not ok then
  io.stderr:write(tostring(run_err) .. "\n")
  os.exit(1)
end
