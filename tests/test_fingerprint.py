from openloop.fingerprint import fingerprint, similar


def test_same_commitment_same_fp():
    a = fingerprint("Please send the investor deck", "Sarah")
    b = fingerprint("send the investor deck", "sarah")
    assert a == b


def test_different_owners_differ():
    assert fingerprint("send the deck", "Alex") != fingerprint("send the deck", "Priya")


def test_similar():
    assert similar("Please send the deck", "send the deck")
