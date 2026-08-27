from openloop.owners import normalize_owner


def test_self_maps_to_me():
    assert normalize_owner("I'll", default_self="Bhargav") == "Bhargav"
    assert normalize_owner("me", default_self="Bhargav") == "Bhargav"


def test_alias_and_handle():
    aliases = {"alex k": "Alex", "jk": "Jordan"}
    assert normalize_owner("@alex.k", aliases=aliases) == "Alex"
    assert normalize_owner("jordan", aliases={"jordan": "Jordan"}) == "Jordan"


def test_title_case():
    assert normalize_owner("priya") == "Priya"
