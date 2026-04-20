from localscript.extract import extract_lua_code


def test_extract_lua_fenced():
    s = 'Here:\n```lua\nlocal x = 1\n```\n'
    assert extract_lua_code(s) == "local x = 1"


def test_extract_plain_fenced():
    s = "```\nprint(1)\n```"
    assert extract_lua_code(s) == "print(1)"


def test_extract_no_fence_returns_stripped():
    s = "  print('hi')  "
    assert extract_lua_code(s) == "print('hi')"


def test_extract_json_code_field():
    s = '{"code": "local z = 2\\nreturn z\\n"}'
    assert "local z" in extract_lua_code(s)
