-- Example pattern: safe print wrapper
local function log(msg)
  print("[app] " .. tostring(msg))
end

return { log = log }
