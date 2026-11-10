from app.core.mentions import extract_mentions


def test_extracts_unique_lowercase_usernames():
    assert extract_mentions("Hi @Sam_01 and @bob, ping @sam_01 again") == {"sam_01", "bob"}


def test_ignores_email_addresses():
    assert extract_mentions("write to sam@example.com") == set()


def test_ignores_too_short_or_too_long_handles():
    assert extract_mentions("@ab") == set()
    assert extract_mentions("@" + "a" * 51) == set()


def test_mentions_next_to_punctuation():
    assert extract_mentions("@alice, please check (@bob)!") == {"alice", "bob"}


def test_no_mentions():
    assert extract_mentions("nothing to see here") == set()