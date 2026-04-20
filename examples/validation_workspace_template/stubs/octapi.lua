---@meta
--- Fictional **octapi** globals for LuaLS (see examples/rag_corpus/octapi_stub.md).

---@class OctapiHandle
---@field send fun(self, msg: string)
---@field close fun(self)

octapi = {}

---@param host string
---@return OctapiHandle
function octapi.connect(host) end

---@return string
function octapi.version() end
