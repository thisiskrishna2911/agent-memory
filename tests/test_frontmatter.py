from agent_memory.frontmatter import parse, serialize


def test_parse_splits_meta_and_body():
    text = "---\ntype: session\ntags:\n  - a\n  - b\n---\n\nHello body\n"
    meta, body = parse(text)
    assert meta["type"] == "session"
    assert meta["tags"] == ["a", "b"]
    assert body.strip() == "Hello body"


def test_parse_no_frontmatter_returns_empty_meta():
    meta, body = parse("just text, no frontmatter")
    assert meta == {}
    assert body == "just text, no frontmatter"


def test_serialize_roundtrips():
    meta = {"type": "decision", "scope": "project", "tags": ["x"]}
    text = serialize(meta, "Body here")
    meta2, body2 = parse(text)
    assert meta2["type"] == "decision"
    assert meta2["scope"] == "project"
    assert meta2["tags"] == ["x"]
    assert body2.strip() == "Body here"
