def assert_cassette_empty(cass):
    assert len(cass) == 0
    assert cass.play_count == 0


def assert_cassette_has_one_response(cass):
    assert len(cass) == 1
    assert cass.play_count == 1
